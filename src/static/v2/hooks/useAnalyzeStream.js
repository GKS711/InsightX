/**
 * InsightX v4 · Hook — useAnalyzeStream
 *
 * 對應合約：
 *   - docs/v4-sse-events.md §3 event types
 *   - docs/v4-view-model.md §5 StreamState phase 狀態機
 *   - docs/v4-view-model.md §15 Adapter 層責任 8：terminal 後立即 close；onerror 不自動重連
 *
 * 封裝 ../core/adapters.js → runAnalyzeStream：
 *   - 幫 caller 管理 handle（useRef）+ unmount cleanup
 *   - 暴露命令式 API {start, stop}；dispatch 由 useAppReducer 提供
 *   - start() 會先 stop 舊的 handle，避免洩漏 EventSource
 *
 * 設計信條：
 *   - 不在 hook 內 useState — 所有進度 / 結果都靠 reducer action 回流，UI 單一 source of truth
 *   - stop() 冪等：多次呼叫安全
 *   - start() 多次：自動替換舊 handle
 *
 * 依賴：
 *   - ../core/adapters.js::runAnalyzeStream
 *   - globalThis.React（UMD 18.3.1）
 */

import { runAnalyzeStream } from "../core/adapters.js";

const React = /** @type {any} */ (globalThis.React);

/**
 * @typedef {Object} AnalyzeStreamController
 * @property {(p: {url: string, platform?: "google"|"youtube"|null, ytRole?: "creator"|"shop"|"brand"|null}) => {runId: string, requestId: string} | null} start
 * @property {() => void} stop
 * @property {() => boolean} isActive
 */

/**
 * @param {(action: object) => void} dispatch  — 從 useAppReducer 來
 * @returns {AnalyzeStreamController}
 */
export function useAnalyzeStream(dispatch) {
  // handle 形狀：{ close, runId, requestId } | null
  const handleRef = React.useRef(null);

  const stop = React.useCallback(() => {
    const h = handleRef.current;
    if (h) {
      try { h.close(); } catch { /* ignore */ }
      handleRef.current = null;
      // 讓 reducer 進 canceled（只有 phase in connecting|streaming 才生效，reducer 會守）
      dispatch({ type: "ABORT_STREAM" });
    }
  }, [dispatch]);

  const start = React.useCallback(
    ({ url, platform = null, ytRole = null }) => {
      if (!url || typeof url !== "string") {
        // 讓 caller 自己驗；hook 不 throw，只拒絕開連線
        return null;
      }
      // 先關舊的（冪等）
      if (handleRef.current) {
        try { handleRef.current.close(); } catch { /* ignore */ }
        handleRef.current = null;
      }
      const handle = runAnalyzeStream({ url, platform, ytRole, dispatch });
      handleRef.current = handle;
      return { runId: handle.runId, requestId: handle.requestId };
    },
    [dispatch]
  );

  const isActive = React.useCallback(() => handleRef.current != null, []);

  // unmount cleanup：不 dispatch ABORT（可能 component 已經要不見了），只關連線
  React.useEffect(() => {
    return () => {
      const h = handleRef.current;
      if (h) {
        try { h.close(); } catch { /* ignore */ }
        handleRef.current = null;
      }
    };
  }, []);

  // useMemo 避免每次 render 新 object reference 觸發下游 re-render
  return React.useMemo(
    () => ({ start, stop, isActive }),
    [start, stop, isActive]
  );
}

export default useAnalyzeStream;
