/**
 * InsightX v4 · Hook — useAppReducer
 *
 * 對應合約：
 *   - docs/v4-view-model.md §1 AppViewModel
 *   - docs/v4-view-model.md §3 AsyncState<T> 四態 invariant
 *   - docs/v4-view-model.md §10 Dispatch / Reducer（slice 拆分）
 *   - docs/v4-view-model.md §11 Persist 白名單
 *
 * 設計信條（摘自合約）：
 *   1. Reducer 純函式，不碰 DOM、不 mutate
 *   2. 所有 AsyncState 只能透過 Async.* helper 建立
 *   3. stale response 用 requestId 比對丟棄（docs §4「平行請求 stale-response 規則」）
 *   4. SWITCH_PLATFORM in-flight stream 時不自動 kill；reducer 在此 slice 無側效，
 *      拒絕/確認流程由 UI + confirm action 帶（REQUEST_SWITCH_CONFIRM / CONFIRM_SWITCH_PLATFORM）
 *
 * 依賴：
 *   - ../core/async.js （Async / Err / isFresh）
 *   - globalThis.React （UMD 18.3.1）
 */

import { Async } from "../core/async.js";
import { writeToStorage, readFromStorage } from "./useLocalStorage.js";

const React = /** @type {any} */ (globalThis.React);

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PERSIST_KEY = "insightx.v4.state";

/** 白名單：只有這些欄位會被 persist（docs §11） */
const PERSIST_WHITELIST = Object.freeze({
  mode: ["currentPlatform", "ytRoleSelection"],
  input: ["googleUrl", "youtubeUrl"],
  // features.analyze.data 可選 persist；P0 先不做，避免 stale 資料跨 session 混淆
});

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

/**
 * @returns {import('./types').AppViewModel}
 */
export function createInitialState() {
  return {
    mode: {
      currentPlatform: "google",
      ytRoleSelection: "creator",
    },
    input: {
      googleUrl: "",
      youtubeUrl: "",
    },
    stream: {
      phase: "idle",
      runId: null,
      step: 0,
      totalSteps: 0,
      label: "",
      progress: 0,
      platform: null,
      effective_yt_role: null,
      error: null,
      startedAt: null,
      endedAt: null,
    },
    features: {
      analyze: Async.idle(),
      swot: Async.idle(),
      reply: Async.idle(),
      marketing: Async.idle(),
      weeklyPlan: Async.idle(),
      trainingScript: Async.idle(),
      internalEmail: Async.idle(),
      rootCause: Async.idle(),
    },
    chat: {
      status: "idle",
      messages: [],
      activeContextRunId: null,
      requestId: null,
      error: null,
    },
    alerts: { items: [] },
    meta: {
      appVersion: "4.0.0",
      availablePlatforms: ["google", "youtube"],
      availableYtRoles: ["creator", "shop", "brand"],
      featureFlags: { sse_v4: true },
    },
  };
}

/**
 * 從 localStorage 水合初始 state：白名單欄位覆蓋 default，其餘保持 default（stream 永遠 idle）。
 * docs §11：「刷新後強制 stream=idle、chat.messages=[]、alerts=[]」
 */
export function hydrateInitialState() {
  const base = createInitialState();
  const saved = readFromStorage(PERSIST_KEY, null);
  if (!saved || typeof saved !== "object") return base;

  // mode
  if (saved.mode) {
    if (saved.mode.currentPlatform === "google" || saved.mode.currentPlatform === "youtube") {
      base.mode.currentPlatform = saved.mode.currentPlatform;
    }
    if (["creator", "shop", "brand"].includes(saved.mode.ytRoleSelection)) {
      base.mode.ytRoleSelection = saved.mode.ytRoleSelection;
    }
  }
  // input
  if (saved.input) {
    if (typeof saved.input.googleUrl === "string") base.input.googleUrl = saved.input.googleUrl;
    if (typeof saved.input.youtubeUrl === "string") base.input.youtubeUrl = saved.input.youtubeUrl;
  }
  return base;
}

/**
 * 從完整 state 抽出白名單子集，for persist。
 */
function projectPersistSubset(state) {
  return {
    mode: {
      currentPlatform: state.mode.currentPlatform,
      ytRoleSelection: state.mode.ytRoleSelection,
    },
    input: {
      googleUrl: state.input.googleUrl,
      youtubeUrl: state.input.youtubeUrl,
    },
  };
}

// ---------------------------------------------------------------------------
// Slice reducers
// ---------------------------------------------------------------------------

/**
 * 8 個 feature endpoint 對應 action prefix → FeatureStatesVM 鍵
 */
const FEATURE_MAP = Object.freeze({
  FETCH_ANALYZE: "analyze",
  FETCH_SWOT: "swot",
  FETCH_REPLY: "reply",
  FETCH_MARKETING: "marketing",
  FETCH_WEEKLY_PLAN: "weeklyPlan",
  FETCH_TRAINING_SCRIPT: "trainingScript",
  FETCH_INTERNAL_EMAIL: "internalEmail",
  FETCH_ROOT_CAUSE: "rootCause",
});

function reduceMode(mode, action) {
  switch (action.type) {
    case "SWITCH_PLATFORM":
      // in-flight stream guard 由上層 thunk 做；reducer 只負責值變更
      if (action.platform === "google" || action.platform === "youtube") {
        return { ...mode, currentPlatform: action.platform };
      }
      return mode;
    case "SWITCH_YT_ROLE":
      if (["creator", "shop", "brand"].includes(action.ytRole)) {
        return { ...mode, ytRoleSelection: action.ytRole };
      }
      return mode;
    default:
      return mode;
  }
}

function reduceInput(input, action) {
  switch (action.type) {
    case "INPUT_CHANGE": {
      if (action.platform === "google") return { ...input, googleUrl: action.value ?? "" };
      if (action.platform === "youtube") return { ...input, youtubeUrl: action.value ?? "" };
      return input;
    }
    case "INPUT_CLEAR": {
      if (action.platform === "google") return { ...input, googleUrl: "" };
      if (action.platform === "youtube") return { ...input, youtubeUrl: "" };
      if (!action.platform) return { googleUrl: "", youtubeUrl: "" };
      return input;
    }
    default:
      return input;
  }
}

function reduceStream(stream, action) {
  switch (action.type) {
    case "STREAM_START":
      return {
        phase: "connecting",
        runId: action.runId,
        step: 0,
        totalSteps: 0,
        label: "",
        progress: 0,
        platform: null,
        effective_yt_role: null,
        error: null,
        startedAt: Date.now(),
        endedAt: null,
      };
    case "STREAM_PROGRESS": {
      // stale SSE event（舊 run 的晚到事件）→ 丟棄
      if (stream.runId != null && action.runId !== stream.runId) return stream;
      const p = action.payload || {};
      return {
        ...stream,
        phase: "streaming",
        step: typeof p.step === "number" ? p.step : stream.step,
        totalSteps: typeof p.totalSteps === "number" ? p.totalSteps : stream.totalSteps,
        label: typeof p.label === "string" ? p.label : stream.label,
        progress: typeof p.progress === "number" ? p.progress : stream.progress,
        platform: p.platform ?? stream.platform,
        effective_yt_role: p.effective_yt_role ?? stream.effective_yt_role,
      };
    }
    case "STREAM_RESULT":
      if (stream.runId != null && action.runId !== stream.runId) return stream;
      return { ...stream, phase: "succeeded", progress: 1, endedAt: Date.now() };
    case "STREAM_FAILED":
      if (stream.runId != null && action.runId !== stream.runId) return stream;
      return { ...stream, phase: "failed", error: action.error, endedAt: Date.now() };
    case "STREAM_CONNECTION_LOST":
      if (stream.runId != null && action.runId !== stream.runId) return stream;
      return { ...stream, phase: "failed", error: action.error, endedAt: Date.now() };
    case "ABORT_STREAM":
      if (stream.phase === "connecting" || stream.phase === "streaming") {
        return { ...stream, phase: "canceled", endedAt: Date.now() };
      }
      return stream;
    case "STREAM_RESET":
      return {
        phase: "idle",
        runId: null,
        step: 0,
        totalSteps: 0,
        label: "",
        progress: 0,
        platform: null,
        effective_yt_role: null,
        error: null,
        startedAt: null,
        endedAt: null,
      };
    default:
      return stream;
  }
}

/**
 * 針對 FETCH_<FEATURE>_{START|SUCCEEDED|FAILED} 套一個統一 slice 轉換。
 * stale discard：SUCCEEDED / FAILED 時比對 slice.requestId；對不上就丟。
 */
// P3.9-5R-R3 fix #2：當 analyze 重新跑或 platform/ytRole 切換時，所有下游 feature slice
// 必須一起重置成 idle。否則 useSwotSummary / Marketing / Weekly 等會用上一份分析的 ready
// 資料當輸入，把舊 SWOT/strengths 餵給新分析的下游 endpoint（codex round-3 #2 / #3）。
const DOWNSTREAM_FEATURE_KEYS = [
  "swot", "reply", "marketing", "weeklyPlan",
  "trainingScript", "internalEmail", "rootCause",
];
function resetDownstream(features) {
  const next = { ...features };
  for (const k of DOWNSTREAM_FEATURE_KEYS) next[k] = Async.idle();
  return next;
}

function reduceFeatures(features, action) {
  // analyze 特殊：SSE result 也會寫 features.analyze
  if (action.type === "STREAM_RESULT") {
    const prev = features.analyze;
    // STREAM_RESULT 用 adapters 附的 requestId 對比
    if (prev.requestId != null && action.requestId !== prev.requestId) return features;
    // 新一份分析就緒 → 把所有下游 reset，讓 SwotSection / Marketing / Weekly 重新 fetch。
    const reset = resetDownstream(features);
    return { ...reset, analyze: Async.ready(action.requestId, action.data) };
  }
  if (action.type === "STREAM_FAILED" || action.type === "STREAM_CONNECTION_LOST") {
    const prev = features.analyze;
    if (prev.requestId != null && action.requestId !== prev.requestId) return features;
    return { ...features, analyze: Async.failed(action.requestId, action.error, prev.data) };
  }
  if (action.type === "STREAM_START") {
    const prev = features.analyze;
    // 新分析開始 → 同步把下游 reset，避免 loading 期間 UI 還顯示舊 ready 的下游結果。
    const reset = resetDownstream(features);
    return { ...reset, analyze: Async.loading(action.requestId, prev.data) };
  }
  // POST /api/analyze（非 SSE）路徑也算新分析開始 → 一併 reset 下游 + analyze 進入 loading。
  // P3.9-5R-R4 fix #2：先前只 reset 下游、沒把 analyze 設 loading，會導致 SUCCEEDED 被
  // requestId stale check 丟棄（舊 requestId 仍留在 prev），且 UI 不進 loading state。
  // FETCH_ANALYZE_SUCCEEDED / FAILED 維持走下面 FEATURE_MAP 通用迴圈處理。
  if (action.type === "FETCH_ANALYZE_START") {
    const prev = features.analyze;
    const reset = resetDownstream(features);
    return { ...reset, analyze: Async.loading(action.requestId, prev.data) };
  }
  // SWITCH_PLATFORM / SWITCH_YT_ROLE 的下游 reset 在 reduceAppState 處理（要看舊值是否變動）。

  // 8 個一般 feature endpoint
  const match = Object.keys(FEATURE_MAP).find((prefix) =>
    action.type === `${prefix}_START` ||
    action.type === `${prefix}_SUCCEEDED` ||
    action.type === `${prefix}_FAILED`
  );
  if (!match) return features;

  const sliceKey = FEATURE_MAP[match];
  const prev = features[sliceKey];

  if (action.type === `${match}_START`) {
    return { ...features, [sliceKey]: Async.loading(action.requestId, prev.data) };
  }
  if (action.type === `${match}_SUCCEEDED`) {
    if (prev.requestId != null && action.requestId !== prev.requestId) return features;
    return { ...features, [sliceKey]: Async.ready(action.requestId, action.data) };
  }
  if (action.type === `${match}_FAILED`) {
    if (prev.requestId != null && action.requestId !== prev.requestId) return features;
    return { ...features, [sliceKey]: Async.failed(action.requestId, action.error, prev.data) };
  }
  return features;
}

function reduceChat(chat, action) {
  switch (action.type) {
    case "CHAT_SEND_START": {
      const userMsg = {
        role: "user",
        content: action.meta?.userMessage ?? "",
        createdAt: Date.now(),
        requestId: action.requestId,
      };
      return {
        ...chat,
        status: "loading",
        messages: [...chat.messages, userMsg],
        requestId: action.requestId,
        error: null,
      };
    }
    case "CHAT_SEND_SUCCEEDED": {
      // stale：requestId 不符合 → 丟棄
      if (chat.requestId != null && action.requestId !== chat.requestId) return chat;
      const aiMsg = {
        role: "ai",
        content: action.data?.reply ?? "",
        createdAt: Date.now(),
        requestId: null,
      };
      return {
        ...chat,
        status: "ready",
        messages: [...chat.messages, aiMsg],
        error: null,
      };
    }
    case "CHAT_SEND_FAILED": {
      if (chat.requestId != null && action.requestId !== chat.requestId) return chat;
      return { ...chat, status: "failed", error: action.error };
    }
    case "CHAT_CONTEXT_SWITCH":
      return {
        ...chat,
        activeContextRunId: action.runId ?? null,
        messages: [],
        status: "idle",
        requestId: null,
        error: null,
      };
    case "CHAT_RESET":
      return {
        status: "idle",
        messages: [],
        activeContextRunId: null,
        requestId: null,
        error: null,
      };
    default:
      return chat;
  }
}

function reduceAlerts(alerts, action) {
  switch (action.type) {
    case "ALERT_PUSH": {
      const item = {
        id: action.id ?? `alert-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        level: action.level ?? "info",
        message: action.message ?? "",
        createdAt: Date.now(),
        dismissible: action.dismissible !== false,
        ttlMs: action.ttlMs ?? null,
      };
      return { items: [...alerts.items, item] };
    }
    case "ALERT_DISMISS":
      return { items: alerts.items.filter((a) => a.id !== action.id) };
    case "ALERTS_CLEAR":
      return { items: [] };
    default:
      return alerts;
  }
}

function reduceMeta(meta, action) {
  switch (action.type) {
    case "FETCH_META_SUCCEEDED":
      if (!action.data) return meta;
      return {
        ...meta,
        appVersion: action.data.version ?? meta.appVersion,
        availablePlatforms: action.data.platforms ?? meta.availablePlatforms,
        availableYtRoles: action.data.yt_roles ?? meta.availableYtRoles,
        featureFlags: { ...meta.featureFlags, ...(action.data.feature_flags || {}) },
      };
    default:
      return meta;
  }
}

/**
 * 頂層 reducer：組合所有 slice。
 * 特殊：HYDRATE 直接覆蓋，RESET 回初始。
 *
 * P3.9-5R-R3 fix #2 後續：SWITCH_PLATFORM / SWITCH_YT_ROLE 的下游 reset 在這層處理。
 * 為什麼不放 reduceFeatures：那邊看不到 mode 舊值，無法區分「值真的變了」vs「點同一個 tab」。
 * 在這裡比對舊 mode 與新 mode，只有「真的變動」才 reset，避免無謂閃爍。
 */
export function reduceAppState(state, action) {
  if (action.type === "HYDRATE_STATE" && action.state) return action.state;
  if (action.type === "RESET_STATE") return createInitialState();

  const newMode = reduceMode(state.mode, action);
  let newFeatures = reduceFeatures(state.features, action);

  // 只有當 SWITCH_* 真的改變了 mode 值，才 reset 所有下游 feature slice。
  // 這樣 user 點同一個 platform tab 不會把 in-flight / ready 的 swot/marketing 等清掉。
  if (
    (action.type === "SWITCH_PLATFORM" || action.type === "SWITCH_YT_ROLE") &&
    (newMode.currentPlatform !== state.mode.currentPlatform ||
      newMode.ytRoleSelection !== state.mode.ytRoleSelection)
  ) {
    // 同步把 analyze 也 reset：切平台/角色後舊的 analyze ready 結果不再代表當前 mode。
    newFeatures = {
      ...resetDownstream(newFeatures),
      analyze: Async.idle(),
    };
  }

  return {
    mode: newMode,
    input: reduceInput(state.input, action),
    stream: reduceStream(state.stream, action),
    features: newFeatures,
    chat: reduceChat(state.chat, action),
    alerts: reduceAlerts(state.alerts, action),
    meta: reduceMeta(state.meta, action),
  };
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * 單一入口 app reducer。
 *
 * Persist 策略（docs §11）：
 *   - mount 時用 hydrateInitialState 讀 localStorage 白名單
 *   - 任何 dispatch 後自動 persist 白名單子集（mode + input）
 *   - stream / chat / alerts 從不進 storage
 *
 * React 18 本身已批次 render，docs §10 的 RAF batch 在 React 環境下不再必要；
 * 若 caller 仍想合併同 frame 多次 dispatch，可透過 action queue（未實作，P1+ 視需要加）。
 *
 * @param {Object} [options]
 * @param {boolean} [options.persist]  — 預設 true；測試可關
 * @returns {{ state: import('./types').AppViewModel, dispatch: (action: object) => void }}
 */
export function useAppReducer(options = {}) {
  const { persist = true } = options;

  const [state, dispatch] = React.useReducer(
    reduceAppState,
    null,
    () => (persist ? hydrateInitialState() : createInitialState())
  );

  // 用 ref 防止 persist 在 effect 順序倒置時讀到舊值（closure 抓 state 本身已足夠，
  // useEffect 會在 state 變動後才跑，所以直接 state 依賴即可）
  React.useEffect(() => {
    if (!persist) return;
    writeToStorage(PERSIST_KEY, projectPersistSubset(state));
  }, [
    persist,
    state.mode.currentPlatform,
    state.mode.ytRoleSelection,
    state.input.googleUrl,
    state.input.youtubeUrl,
  ]);

  return { state, dispatch };
}

export default useAppReducer;
