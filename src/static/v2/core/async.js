/**
 * InsightX v4 · Layer 3 — AsyncState / ErrorVM helpers
 *
 * 對應合約：
 *   - docs/v4-view-model.md §3 AsyncState<T>
 *   - docs/v4-view-model.md §8 ErrorVM
 *
 * 設計信條：
 *   - 4 態顯性（idle / loading / ready / failed），null 不兼任兩件事
 *   - requestId 必備欄位，用來丟棄 stale response
 *   - loading 可帶 prev data（讓 UI skeleton 或 stale overlay 有資料可顯示）
 */

/**
 * @typedef {Object} AsyncState
 * @property {"idle" | "loading" | "ready" | "failed"} status
 * @property {*} data          // ready 時是 T，loading/failed 可為 prev T 或 null
 * @property {ErrorVM | null} error
 * @property {string | null} requestId
 * @property {number | null} updatedAt
 */

/**
 * @typedef {Object} ErrorVM
 * @property {"VALIDATION_ERROR" | "SCRAPER_ERROR" | "LLM_ERROR" | "UNKNOWN_ERROR" | "NETWORK_ERROR"} code
 * @property {string} message
 * @property {boolean} retryable
 * @property {number | null} retryAfterSecs
 * @property {string | null} requestId
 * @property {number} capturedAt
 */

export const Async = Object.freeze({
  idle: () => ({
    status: "idle",
    data: null,
    error: null,
    requestId: null,
    updatedAt: null,
  }),
  loading: (requestId, prevData = null) => ({
    status: "loading",
    data: prevData,
    error: null,
    requestId,
    updatedAt: Date.now(),
  }),
  ready: (requestId, data) => ({
    status: "ready",
    data,
    error: null,
    requestId,
    updatedAt: Date.now(),
  }),
  failed: (requestId, error, prevData = null) => ({
    status: "failed",
    data: prevData,
    error,
    requestId,
    updatedAt: Date.now(),
  }),
});

/**
 * ErrorVM constructor helpers。所有 adapter 的錯誤都走這條，確保 reducer 拿到一致 shape。
 */
export const Err = Object.freeze({
  /**
   * 從後端 SSE failed payload 或 /api/meta._fallback 構造。
   * Server payload 欄位：code, message, retryable, retry_after_secs?
   */
  fromServerFailed: (payload, requestId) => ({
    code: payload.code || "UNKNOWN_ERROR",
    message: payload.message || "Server reported an unspecified failure.",
    retryable: Boolean(payload.retryable),
    retryAfterSecs: payload.retry_after_secs ?? null,
    requestId: requestId ?? null,
    capturedAt: Date.now(),
  }),
  /**
   * 從 HTTP 422 `{detail:[{loc, msg, type}]}` 構造。
   */
  fromHttp422: (body, requestId) => {
    const first = Array.isArray(body?.detail) ? body.detail[0] : null;
    const locStr = first?.loc ? first.loc.join(".") : "(unknown)";
    const msg = first?.msg || "Validation failed";
    return {
      code: "VALIDATION_ERROR",
      message: `${msg} [${locStr}]`,
      retryable: false,
      retryAfterSecs: null,
      requestId: requestId ?? null,
      capturedAt: Date.now(),
    };
  },
  /**
   * 500 / 其他 HTTP error。
   */
  fromHttpError: (status, bodyText, requestId) => ({
    code: status >= 500 ? "UNKNOWN_ERROR" : "VALIDATION_ERROR",
    message: `HTTP ${status}${bodyText ? ": " + String(bodyText).slice(0, 180) : ""}`,
    retryable: status >= 500,
    retryAfterSecs: null,
    requestId: requestId ?? null,
    capturedAt: Date.now(),
  }),
  /**
   * fetch network failure / SSE onerror / 離線。
   */
  network: (message, requestId) => ({
    code: "NETWORK_ERROR",
    message: message || "Network connection lost",
    retryable: true,
    retryAfterSecs: null,
    requestId: requestId ?? null,
    capturedAt: Date.now(),
  }),
});

/**
 * stale discard helper：new state 的 requestId 必須等於 slice 當前 requestId 才寫入。
 * 在 adapter 層使用，避免平行請求污染新 run state。
 *
 * @param {string} incomingRequestId
 * @param {string | null} sliceCurrentRequestId
 * @returns {boolean} true = 該寫入；false = 丟棄
 */
export function isFresh(incomingRequestId, sliceCurrentRequestId) {
  return incomingRequestId != null && incomingRequestId === sliceCurrentRequestId;
}

/**
 * UI 顯示用：把 ErrorVM / 任意 error 值轉成可讀字串。
 *
 * P3.9-7：原本三個 Tool 寫 `String(slice.error || "未知錯誤")` 把 ErrorVM 物件
 * 直接 toString() 渲染成 "[object Object]"。改用這個 helper，未來不論誰寫
 * 失敗 UI 都不會再踩到同一個雷。
 *
 * @param {ErrorVM | string | null | undefined} error
 * @param {string} [fallback="未知錯誤"]
 * @returns {string}
 */
export function formatErrorMessage(error, fallback = "未知錯誤") {
  if (error == null) return fallback;
  if (typeof error === "string") return error;
  if (typeof error === "object") {
    if (typeof error.message === "string" && error.message) return error.message;
  }
  return fallback;
}
