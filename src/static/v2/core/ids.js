/**
 * InsightX v4 · Layer 2 — Request ID / Run ID machinery
 *
 * 目的：
 *   - 每次 API call / SSE stream 都配唯一 ID
 *   - adapter 用 ID 比對 stale response（docs/v4-view-model.md §0 設計信條 2）
 *
 * 為什麼不用 crypto.randomUUID / Date.now()：
 *   - randomUUID 在舊瀏覽器 / http context 沒有
 *   - Date.now() 同一 frame 多次調用會撞
 *   - 單調遞增 counter 足夠當 session 內 key，清晰好除錯
 */

let _reqSeq = 0;
let _runSeq = 0;

/**
 * @returns {string} e.g. "req-1", "req-2" ...
 */
export function nextRequestId() {
  _reqSeq += 1;
  return `req-${_reqSeq}`;
}

/**
 * @returns {string} e.g. "run-1" ...
 */
export function nextRunId() {
  _runSeq += 1;
  return `run-${_runSeq}`;
}

// 測試 / session reset 用；production code 不該調用
export function _resetIds() {
  _reqSeq = 0;
  _runSeq = 0;
}
