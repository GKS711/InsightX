/**
 * InsightX v4 · Hook — useLocalStorage
 *
 * 對應合約：docs/v4-view-model.md §11 Persist 策略
 *   - key 前綴必統一（"insightx.v4.*"）
 *   - 包 schema version gate：存進去時自動包 {_v: "4.0.0", value}；讀取時 _v 不對就當沒有
 *   - schema 對不上直接清掉（docs §11：「schema version 對不上直接清掉」）
 *
 * 使用情境（白名單）：
 *   - mode.currentPlatform
 *   - mode.ytRoleSelection
 *   - input.googleUrl / input.youtubeUrl
 *   - （可選）features.analyze.data 最後一次成功
 *
 * ❌ 不得 persist：stream / chat.messages / alerts / features.* 其他 8 個
 *   （用 useAppReducer 裡的 PERSIST_WHITELIST 邏輯控制，不是靠 hook 擋）
 *
 * 依賴：globalThis.React（UMD 18.3.1）。ES module 不 import react，讓瀏覽器直接用全域。
 */

const SCHEMA_VERSION = "4.0.0";
const React = /** @type {any} */ (globalThis.React);

/**
 * @template T
 * @param {string} key           — 完整 key（呼叫方負責加 "insightx.v4." 前綴）
 * @param {T} defaultValue       — 當 key 不存在 / schema 版本對不上 / JSON 壞掉時使用
 * @param {Object} [options]
 * @param {string} [options.schemaVersion]  — 預設 SCHEMA_VERSION，測試時可覆寫
 * @param {(raw: unknown) => T | null} [options.validate]
 *        — 讀取後的額外 shape 檢查；回 null 代表無效，fallback 到 default
 * @returns {[T, (next: T | ((prev: T) => T)) => void, () => void]}
 *          [value, setValue, clearValue]
 */
export function useLocalStorage(key, defaultValue, options = {}) {
  const { schemaVersion = SCHEMA_VERSION, validate } = options;

  // ---- lazy initial state：SSR 安全 + 只在 mount 時讀一次 ----
  const [value, setValue] = React.useState(() => {
    return readFromStorage(key, defaultValue, schemaVersion, validate);
  });

  // ---- 寫入 wrapper：支援 functional updater，和 React.useState 一致 ----
  const setValueAndPersist = React.useCallback(
    (next) => {
      setValue((prev) => {
        const resolved = typeof next === "function" ? next(prev) : next;
        writeToStorage(key, resolved, schemaVersion);
        return resolved;
      });
    },
    [key, schemaVersion]
  );

  // ---- clear：清 localStorage 但保留 in-memory state 為 default ----
  const clearValue = React.useCallback(() => {
    removeFromStorage(key);
    setValue(defaultValue);
  }, [key, defaultValue]);

  return [value, setValueAndPersist, clearValue];
}

// ---------------------------------------------------------------------------
// Storage primitives（供 hook 內部 + useAppReducer persist 機制共用）
// ---------------------------------------------------------------------------

/**
 * 同步讀 localStorage，自動解 schema wrapper + validate。
 * 任何錯誤（無 window / JSON 壞 / schema 不符 / validate 失敗）都回 defaultValue。
 */
export function readFromStorage(key, defaultValue, schemaVersion = SCHEMA_VERSION, validate) {
  if (typeof window === "undefined" || !window.localStorage) return defaultValue;
  let raw;
  try {
    raw = window.localStorage.getItem(key);
  } catch {
    return defaultValue;
  }
  if (raw == null) return defaultValue;

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    // JSON 壞了，清掉避免反覆重讀到壞值
    try { window.localStorage.removeItem(key); } catch { /* ignore */ }
    return defaultValue;
  }

  // schema version gate
  if (!parsed || typeof parsed !== "object" || parsed._v !== schemaVersion) {
    try { window.localStorage.removeItem(key); } catch { /* ignore */ }
    return defaultValue;
  }

  const candidate = parsed.value;
  if (validate) {
    const checked = validate(candidate);
    if (checked == null) return defaultValue;
    return checked;
  }
  return candidate ?? defaultValue;
}

/**
 * 寫 localStorage，包 schema wrapper。任何錯誤（quota exceeded / private mode）靜默失敗。
 */
export function writeToStorage(key, value, schemaVersion = SCHEMA_VERSION) {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    const wrapped = { _v: schemaVersion, value };
    window.localStorage.setItem(key, JSON.stringify(wrapped));
  } catch {
    // quota / disabled — 不拋，避免把整個 reducer 搞掛
  }
}

/**
 * 移除 localStorage key。任何錯誤靜默失敗。
 */
export function removeFromStorage(key) {
  if (typeof window === "undefined" || !window.localStorage) return;
  try { window.localStorage.removeItem(key); } catch { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export default useLocalStorage;
