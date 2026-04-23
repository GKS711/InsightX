/**
 * InsightX v4 · Layer 4 — Domain adapters
 *
 * 每一個 adapter 都：
 *   1. 從 ids.js 拿新 requestId（SSE 額外拿 runId）
 *   2. dispatch START action（帶 requestId / runId）
 *   3. 走 api.js 打 server
 *   4. dispatch SUCCEEDED / FAILED action（帶 requestId + 結果）
 *
 * adapter **不做** stale discard — reducer 拿到 action 後靠 slice.requestId 比對自己丟。
 * 這樣 adapter 可以保持 pure promise / callback，測試簡單。
 *
 * Action shape convention（docs/v4-view-model.md §10.2）：
 *   {type: "FETCH_SWOT_START",     requestId, meta?}
 *   {type: "FETCH_SWOT_SUCCEEDED", requestId, data}
 *   {type: "FETCH_SWOT_FAILED",    requestId, error}
 *
 * SSE analyze 特殊：
 *   {type: "STREAM_START",     runId, requestId, meta}
 *   {type: "STREAM_PROGRESS",  runId, payload}
 *   {type: "STREAM_RESULT",    runId, requestId, data}      // 會同時填 features.analyze
 *   {type: "STREAM_FAILED",    runId, requestId, error}
 *   {type: "STREAM_CONNECTION_LOST", runId, requestId, error}
 *
 * NOTE：STREAM_CONNECTION_LOST 必須帶 requestId，否則 reduceFeatures 的
 * stale check（prev.requestId !== action.requestId）會把 action 丟掉，
 * features.analyze 卡在 loading 永遠不 failed（Codex round-2 audit）。
 */

import { apiFetch, openSSE } from "./api.js";
import { nextRequestId, nextRunId } from "./ids.js";
import { Err } from "./async.js";

// ---------------------------------------------------------------------------
// /api/meta — app bootstrap
// ---------------------------------------------------------------------------

export async function fetchMeta({ dispatch }) {
  const requestId = nextRequestId();
  dispatch({ type: "FETCH_META_START", requestId });

  const res = await apiFetch("/api/meta", { method: "GET", requestId });
  if (res.ok) {
    dispatch({ type: "FETCH_META_SUCCEEDED", requestId, data: res.data });
  } else {
    dispatch({ type: "FETCH_META_FAILED", requestId, error: res.error });
  }
  return res;
}

// ---------------------------------------------------------------------------
// /api/v4/analyze-stream — SSE analyze
// ---------------------------------------------------------------------------

/**
 * @param {Object} p
 * @param {string} p.url
 * @param {"google"|"youtube"|null} [p.platform]
 * @param {"creator"|"shop"|"brand"|null} [p.ytRole]
 * @param {(action: object) => void} p.dispatch
 * @returns {{ close: () => void, runId: string, requestId: string }}
 *   caller 應該在 SWITCH_PLATFORM / 使用者取消 / 拆卸時呼叫 close()
 */
export function runAnalyzeStream({ url, platform = null, ytRole = null, dispatch }) {
  const runId = nextRunId();
  const requestId = nextRequestId();

  const q = new URLSearchParams({ url });
  if (platform) q.set("platform", platform);
  if (ytRole) q.set("yt_role", ytRole);
  const streamUrl = `/api/v4/analyze-stream?${q.toString()}`;

  dispatch({
    type: "STREAM_START",
    runId,
    requestId,
    meta: { url, platform, ytRole, streamUrl },
  });

  const handle = openSSE(
    streamUrl,
    {
      onProgress: (payload) => {
        dispatch({ type: "STREAM_PROGRESS", runId, payload });
      },
      onResult: (payload) => {
        dispatch({
          type: "STREAM_RESULT",
          runId,
          requestId,
          // payload 結構：{platform, effective_yt_role, durationMs, data}
          data: payload,
        });
      },
      onFailed: (payload) => {
        dispatch({
          type: "STREAM_FAILED",
          runId,
          requestId,
          error: Err.fromServerFailed(payload, requestId),
        });
      },
      onConnectionError: (errorVM) => {
        // P3.10-3-R3 fix（Codex round-2 leftover）：action 必須帶 requestId，否則 reduceFeatures
        // 的 stale check `prev.requestId !== action.requestId` 會丟掉（undefined vs string）
        // → features.analyze 卡在 loading 永遠不 failed。
        // P3.11-R3 fix（Codex round-3）：openSSE opts 也帶 requestId，errorVM.requestId 才會
        // 是真正的 requestId 而不是 runId，診斷語意對齊。
        dispatch({ type: "STREAM_CONNECTION_LOST", runId, requestId, error: errorVM });
      },
    },
    { runId, requestId }
  );

  return {
    close: handle.close,
    runId,
    requestId,
  };
}

// ---------------------------------------------------------------------------
// POST /api/analyze — non-SSE fallback（MetaState.featureFlags.sse_v4=false 時用）
// ---------------------------------------------------------------------------

export async function fetchAnalyze({ url, platform = null, ytRole = null, dispatch }) {
  const requestId = nextRequestId();
  dispatch({
    type: "FETCH_ANALYZE_START",
    requestId,
    meta: { url, platform, ytRole },
  });

  const body = { url };
  if (platform) body.platform = platform;
  if (ytRole) body.yt_role = ytRole;

  // P3.10-2-R2: /api/analyze 非 SSE fallback = 爬蟲（10-30s） + analyze_content LLM（20-40s）
  // = worst case ~70s，給 90s buffer
  const res = await apiFetch("/api/analyze", { method: "POST", body, requestId, timeoutMs: 90_000 });
  if (res.ok) {
    dispatch({ type: "FETCH_ANALYZE_SUCCEEDED", requestId, data: res.data });
  } else {
    dispatch({ type: "FETCH_ANALYZE_FAILED", requestId, error: res.error });
  }
  return res;
}

// ---------------------------------------------------------------------------
// 8 個 AI feature endpoints — 模板化
// ---------------------------------------------------------------------------

/**
 * 9 個下游 feature 的統一 factory。所有 action type 首碼：FETCH_<FEATURE>_*
 *
 * P3.10-2-R2：cfg 新增 timeoutMs。每個 endpoint 按實際 LLM 生成時間配，後端 llm_service
 * _generate() 也有對應的 total_timeout_s（比這裡略小 5s），兩邊對齊避免前端 abort 後後端還在跑。
 *
 * @param {Object} cfg
 * @param {string} cfg.path                 — server path，如 "/api/swot"
 * @param {string} cfg.typePrefix           — action prefix，如 "FETCH_SWOT"
 * @param {number} cfg.timeoutMs            — per-endpoint fetch timeout
 * @param {(input: object) => object} cfg.buildBody — 把 caller params 轉成 request body
 * @returns {(input: object & {platform, ytRole, dispatch}) => Promise<object>}
 */
function makeFeatureAdapter({ path, typePrefix, timeoutMs, buildBody }) {
  return async function adapter(input) {
    const { platform, ytRole = null, dispatch, ...rest } = input;
    const requestId = nextRequestId();
    dispatch({ type: `${typePrefix}_START`, requestId });

    const body = { ...buildBody(rest), platform };
    if (ytRole) body.yt_role = ytRole;

    const res = await apiFetch(path, { method: "POST", body, requestId, timeoutMs });
    if (res.ok) {
      dispatch({ type: `${typePrefix}_SUCCEEDED`, requestId, data: res.data });
    } else {
      dispatch({ type: `${typePrefix}_FAILED`, requestId, error: res.error });
    }
    return res;
  };
}

// P3.10-2-R2 timeoutMs 配法：比後端 llm_service total_timeout_s 多 5s 當 buffer。
// 表格對齊（單位 s）：
//   endpoint           |  frontend timeoutMs  |  backend total_timeout_s
//   ------------------ | -------------------- | ------------------------
//   /api/swot          |  60s                 |  55s
//   /api/reply         |  45s                 |  40s
//   /api/analyze-issue |  75s                 |  70s
//   /api/marketing     |  45s                 |  40s
//   /api/weekly-plan   | 120s                 | 115s  ← 最長
//   /api/training-...  | 110s                 | 105s
//   /api/internal-...  |  75s                 |  70s
//   /api/chat          |  45s                 |  40s

export const fetchSwot = makeFeatureAdapter({
  path: "/api/swot",
  typePrefix: "FETCH_SWOT",
  timeoutMs: 60_000,
  buildBody: ({ good, bad }) => ({ good, bad }),
});

export const fetchReply = makeFeatureAdapter({
  path: "/api/reply",
  typePrefix: "FETCH_REPLY",
  timeoutMs: 45_000,
  buildBody: ({ topic }) => ({ topic }),
});

export const fetchRootCause = makeFeatureAdapter({
  path: "/api/analyze-issue",
  typePrefix: "FETCH_ROOT_CAUSE",
  timeoutMs: 75_000,
  buildBody: ({ topic }) => ({ topic }),
});

export const fetchMarketing = makeFeatureAdapter({
  path: "/api/marketing",
  typePrefix: "FETCH_MARKETING",
  timeoutMs: 45_000,
  buildBody: ({ strengths }) => ({ strengths }),
});

export const fetchWeeklyPlan = makeFeatureAdapter({
  path: "/api/weekly-plan",
  typePrefix: "FETCH_WEEKLY_PLAN",
  timeoutMs: 120_000,
  buildBody: ({ weaknesses }) => ({ weaknesses }),
});

export const fetchTrainingScript = makeFeatureAdapter({
  path: "/api/training-script",
  typePrefix: "FETCH_TRAINING_SCRIPT",
  timeoutMs: 110_000,
  buildBody: ({ issue }) => ({ issue }),
});

export const fetchInternalEmail = makeFeatureAdapter({
  path: "/api/internal-email",
  typePrefix: "FETCH_INTERNAL_EMAIL",
  timeoutMs: 75_000,
  buildBody: ({ strengths, weaknesses }) => ({ strengths, weaknesses }),
});

// ---------------------------------------------------------------------------
// /api/chat — 特殊：會回 AI reply，caller（reducer）負責把它 append 到 chat.messages
// ---------------------------------------------------------------------------

export async function sendChat({
  message, context = "", platform, ytRole = null, dispatch,
}) {
  const requestId = nextRequestId();
  dispatch({
    type: "CHAT_SEND_START",
    requestId,
    meta: { userMessage: message },
  });

  const body = { message, context, platform };
  if (ytRole) body.yt_role = ytRole;

  // P3.10-2-R2: chat 回覆 150 字以內，gemma 實測 5-15s；timeout 45s（backend 40s）
  const res = await apiFetch("/api/chat", { method: "POST", body, requestId, timeoutMs: 45_000 });
  if (res.ok) {
    dispatch({ type: "CHAT_SEND_SUCCEEDED", requestId, data: res.data });
  } else {
    dispatch({ type: "CHAT_SEND_FAILED", requestId, error: res.error });
  }
  return res;
}

// ---------------------------------------------------------------------------
// 一次性匯出表（給 index.v4.html 好用）
// ---------------------------------------------------------------------------

export const Adapters = Object.freeze({
  fetchMeta,
  runAnalyzeStream,
  fetchAnalyze,
  fetchSwot,
  fetchReply,
  fetchRootCause,
  fetchMarketing,
  fetchWeeklyPlan,
  fetchTrainingScript,
  fetchInternalEmail,
  sendChat,
});
