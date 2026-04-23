/**
 * InsightX v4 · Layer 1 — Transport
 *
 * 對應合約：
 *   - docs/v4-api-contract.md §1.5 422 body shape
 *   - docs/v4-sse-events.md §3 progress/result/failed event types
 *
 * 兩個 primitive：
 *   - apiFetch(path, opts)      — JSON POST/GET，統一回傳 {ok, data} | {ok:false, error: ErrorVM}
 *   - openSSE(url, handlers)    — EventSource 包裝，把 progress/result/failed event parse 完呼叫 handler
 *                                 並處理 onerror fallback；回傳 {close()} 讓 caller 管理 lifecycle
 *
 * 這層不碰 AsyncState / requestId：呼叫方（adapters.js）自己處理。
 */

import { Err } from "./async.js";

// P3.10-2-R2（Codex R1 peer review 結論）：
// R1 為了修「週計畫 timeout」把預設拉到 120s — Codex 指出這對 /api/meta、/api/chat、/api/reply
// 這些本該秒回的 endpoint 是把「網路真的壞了」的偵測時間從 45s 拖到 120s，UX 很差。
// 正確做法：預設維持 45s（快 endpoint 的健檢時間），**每個 adapter 按實際 LLM 生成時間覆寫 timeoutMs**。
// 後端 llm_service._generate() 也對應配 per-endpoint total_timeout_s（比 frontend 略小 5s），
// 避免 frontend abort 後後端還在燒 gemma quota。
const DEFAULT_FETCH_TIMEOUT_MS = 45_000;

/**
 * @param {string} path                 — "/api/..." 開頭
 * @param {Object} opts
 * @param {"GET"|"POST"} [opts.method]  — 預設 "POST"
 * @param {Object} [opts.body]          — 會被 JSON.stringify
 * @param {number} [opts.timeoutMs]
 * @param {string} [opts.requestId]     — 只用來貼到 ErrorVM
 * @param {AbortSignal} [opts.signal]
 * @returns {Promise<{ok:true, data:any} | {ok:false, error:import("./async.js").ErrorVM}>}
 */
export async function apiFetch(path, opts = {}) {
  const {
    method = "POST",
    body,
    timeoutMs = DEFAULT_FETCH_TIMEOUT_MS,
    requestId = null,
    signal,
  } = opts;

  const controller = new AbortController();
  const onExternalAbort = () => controller.abort(signal?.reason);
  if (signal) {
    if (signal.aborted) controller.abort(signal.reason);
    else signal.addEventListener("abort", onExternalAbort, { once: true });
  }
  const timeoutId = setTimeout(() => controller.abort("timeout"), timeoutMs);

  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (e) {
    const msg = (controller.signal.reason === "timeout")
      ? `Request timed out after ${Math.round(timeoutMs / 1000)}s`
      : (e?.message || "Network request failed");
    return { ok: false, error: Err.network(msg, requestId) };
  } finally {
    clearTimeout(timeoutId);
    if (signal) signal.removeEventListener("abort", onExternalAbort);
  }

  if (res.status === 422) {
    const bodyJson = await safeJson(res);
    return { ok: false, error: Err.fromHttp422(bodyJson, requestId) };
  }

  if (!res.ok) {
    const bodyText = await safeText(res);
    return { ok: false, error: Err.fromHttpError(res.status, bodyText, requestId) };
  }

  const data = await safeJson(res);
  if (data === null) {
    return {
      ok: false,
      error: Err.fromHttpError(res.status, "response body not JSON", requestId),
    };
  }
  // P3.9-5R fix #1：後端 LLM 失敗時會以 200 + `_fallback:true` 回 mock。
  // strict facts / feature slice 不可把 mock 當作真實資料 → 視為 failure，
  // 讓 reducer 走 *_FAILED 路徑（顯示「AI 暫時無法產生」而不是把假資料寫進 ready 狀態）。
  if (data && data._fallback === true) {
    return {
      ok: false,
      error: Err.network("AI 服務暫時無法回應（後端回退至範例內容）", requestId),
    };
  }
  return { ok: true, data };
}

async function safeJson(res) {
  try { return await res.json(); } catch { return null; }
}
async function safeText(res) {
  try { return await res.text(); } catch { return ""; }
}

// ---------------------------------------------------------------------------
// SSE
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} SSEHandlers
 * @property {(payload: object) => void} onProgress
 * @property {(payload: object) => void} onResult
 * @property {(payload: object) => void} onFailed
 * @property {(errorVM: import("./async.js").ErrorVM) => void} onConnectionError
 *   —— 觸發情境：
 *     (a) EventSource.onerror 且未收 terminal event（連線層真壞掉）
 *     (b) terminal event（result/failed）payload JSON parse 失敗（協議層被破壞，視為連線錯誤）
 */

/**
 * 開 SSE 連線，parse v4 三種 event。
 *
 * 合約保證（見 docs/v4-sse-events.md §5）：
 *   - 首個 event 一定是 progress(phase=connected)
 *   - terminal 為 result 或 failed 其一；terminal 後呼叫 close() 不再推 event
 *   - onerror 是「連線層」錯誤；application-level failure 走 onFailed
 *
 * @param {string} url               — 已 encode 的 /api/v4/analyze-stream?...
 * @param {SSEHandlers} handlers
 * @param {Object} [opts]
 * @param {string} [opts.runId]      — 用於除錯／log；**絕不**塞進 ErrorVM
 *                                     P3.11-R4 fix（Codex round-4）：原本沒給 requestId
 *                                     會 fallback 成 runId，導致呼叫端誤以為「ErrorVM 帶
 *                                     有 requestId」但實際是 runId，診斷追蹤錯亂。改成
 *                                     沒給就回 null，把契約挑明：caller 沒帶 requestId
 *                                     就沒得用。
 * @param {string} [opts.requestId]  — 塞進 ErrorVM.requestId，給 reducer/UI 對齊用
 *                                     P3.11-R3 fix（Codex round-3）：原本只傳 runId，
 *                                     導致 connection error VM 的 requestId 實際是 runId，
 *                                     違反 ErrorVM 診斷語意。
 * @returns {{ close: () => void, isClosed: () => boolean }}
 */
export function openSSE(url, handlers, opts = {}) {
  const { runId = null, requestId = null } = opts;
  const es = new EventSource(url);
  let terminalReceived = false;
  let closed = false;

  const closeIfOpen = () => {
    if (closed) return;
    closed = true;
    try { es.close(); } catch (_) { /* ignore */ }
  };

  const safeParse = (raw) => {
    try { return JSON.parse(raw); }
    catch (e) { return null; }
  };

  es.addEventListener("progress", (ev) => {
    if (closed) return;
    const payload = safeParse(ev.data);
    if (payload) handlers.onProgress(payload);
  });

  es.addEventListener("result", (ev) => {
    if (closed) return;
    const payload = safeParse(ev.data);
    if (payload === null) {
      // P3.11-R4 fix #5（Codex round-4）：原本先設 terminalReceived=true 再 safeParse，
      // 失敗時靜默 close → features.analyze 永遠卡在 loading。協議層出錯應視為連線錯誤
      // 並 dispatch onConnectionError（仍 close 阻止重連），讓 UI 進 failed 並顯示診斷訊息。
      terminalReceived = true;
      handlers.onConnectionError(
        Err.network("SSE result payload malformed (JSON parse failed)", requestId ?? null)
      );
      closeIfOpen();
      return;
    }
    terminalReceived = true;
    handlers.onResult(payload);
    closeIfOpen();
  });

  es.addEventListener("failed", (ev) => {
    if (closed) return;
    const payload = safeParse(ev.data);
    if (payload === null) {
      // P3.11-R4 fix #5（Codex round-4）：同 result 路徑。failed event 自帶錯誤語意，
      // 但 payload 解不出來就只能用 connection error 表示「SSE 協議層被破壞」。
      terminalReceived = true;
      handlers.onConnectionError(
        Err.network("SSE failed payload malformed (JSON parse failed)", requestId ?? null)
      );
      closeIfOpen();
      return;
    }
    terminalReceived = true;
    handlers.onFailed(payload);
    closeIfOpen();
  });

  es.onerror = (_ev) => {
    // P3.10-3-R2 fix #6（Codex round-2 audit）：原本在 readyState=CONNECTING 時放任
    // 瀏覽器自動重連（30s 間隔），但後端沒 Last-Event-ID resume → 重連會重新跑整套
    // scraper + LLM，等於同一次分析燒兩倍 Gemini quota + Serper credit。改成「第一次
    // onerror 在 terminal 之前」就 close()，永遠不讓 EventSource 自動重連。
    //
    // 兩種觸發情境：
    //   (a) readyState=CLOSED：connection 真的斷了 → connection lost
    //   (b) readyState=CONNECTING：暫時斷線、瀏覽器準備重連 → 我們主動 close 阻止重連
    // 兩者統一視為連線錯誤，由 caller 決定要不要 retry（手動觸發新 EventSource）。
    if (closed) return;
    if (terminalReceived) {
      // terminal 後的 onerror 是 normal close，忽略
      return;
    }
    handlers.onConnectionError(
      Err.network(
        es.readyState === EventSource.CLOSED
          ? "SSE connection closed before terminal event"
          : "SSE connection lost (auto-reconnect blocked to avoid duplicate analysis)",
        // P3.11-R4 fix（Codex round-4）：契約挑明 — caller 必須帶 opts.requestId，
        // 沒帶就明確回 null，絕不偷塞 runId 假裝有 requestId。runId 是 SSE 連線
        // 的 lifecycle id，不是 reducer 用來對齊的 request id；混為一談會讓 UI 顯示
        // 錯誤的 diagnostic context。
        requestId ?? null
      )
    );
    closeIfOpen();
  };

  return {
    close: closeIfOpen,
    isClosed: () => closed,
  };
}
