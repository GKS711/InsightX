# InsightX v4.0.0 前端 View Model 合約

> **狀態**：P3.12-R2 後端不 cap 照抓全部 + 前端 §04 ReviewsSection 顯示限制 50 + 「全部」改「精選」+ 三段 caption；P3.11 已鎖定（adapter / reducer / view-model / 9 feature slice 全實作完成，48/48 reducer + adapter terminal action shape regression pass）。
> **目標讀者**：未來修 v4 前端的維護者（reducer / view-model / renderer）。
> **工具鏈**：單檔 React 18 UMD + Babel standalone（`<script type="text/babel">`，**不**用 marked.js／**不**用 markdown render，AI 純文字輸出走 `<pre>` 直出）+ Tailwind CDN，主入口 `src/static/v2/index.html`，core/hooks 為 ES module 經 `bootstrap.js` 橋接成 `window.IX`。**不導入 TypeScript**（使用者不要 build step）。
> **型別描述方式**：JSDoc `@typedef` + `@template` 泛型；VSCode 原生支援 hover 與 autocomplete。
> **路徑歷史**：P0 草稿原本寫 `src/static/index.html`（v3 純 HTML + marked.js），P1-4R 遷入 `src/static/v2/`，P3.11 確立「AI 純文字結構（【】◆　▸ 排版）」原則，徹底移除 marked.js 依賴。

---

## 0. 設計信條

1. **null 不得一個欄位表達兩件事**。v3 坑：`swot === null` 同時代表「沒跑」和「跑了但還沒回來」。v4 所有 async 狀態都走顯性四態。
2. **runId 是一等公民**。平行請求、SSE 斷線重連、平台切換時，stale response 必須能靠 `runId` 比對丟棄。
3. **非法組合由 constructor helper 擋掉**，不靠紀律。
4. **單一 state + 單一 dispatch + RAF batch render**。沒有 event bus、沒有到處 mutate。
5. **停用 persist in-flight stream**。刷新頁面只保留 mode + URL input + 最近一次成功 result（可選）。

---

## 1. 頂層 `AppViewModel`

```js
/**
 * @typedef {Object} AppViewModel
 * @property {ModeState} mode         // 平台 + 當前 URL + yt_role 選擇
 * @property {InputState} input       // URL input 當下輸入框內容（兩平台分開保留）
 * @property {StreamState} stream     // 主 analyze SSE 的即時進度
 * @property {FeatureStatesVM} features // 9 個 AI 功能的結果 state
 * @property {ChatState} chat         // 對話顧問
 * @property {AlertState} alerts      // 全域警示 queue（非任務級錯誤）
 * @property {MetaState} meta         // 靜態常數（版本、功能旗標、可選平台清單）
 */
```

**為什麼 6 個 slot**：`mode` / `input` 分開因為輸入框內容在切平台時需要分別保留；`stream` 獨立是因為進度快照頻繁更新（RAF batch），不該和結果 state 綁一起；`features` 合 9 功能；`alerts` 用 queue 避免新錯蓋舊錯。

---

## 2. `ModeState` / `InputState`

```js
/**
 * @typedef {"google" | "youtube"} Platform
 * @typedef {"creator" | "shop" | "brand"} YtRole
 */

/**
 * @typedef {Object} ModeState
 * @property {Platform} currentPlatform    // 使用者目前在哪個 tab
 * @property {YtRole} ytRoleSelection       // YouTube 模式下的角色選擇；google 模式下保留但不使用
 */

/**
 * @typedef {Object} InputState
 * @property {string} googleUrl    // Google Maps tab 的輸入框內容（保留原值）
 * @property {string} youtubeUrl   // YouTube tab 的輸入框內容（保留原值）
 */
```

**切平台規則**（`action: SWITCH_PLATFORM`）：

| 情境 | 行為 |
|---|---|
| `stream.phase === "idle"` \| `"succeeded"` \| `"failed"` \| `"canceled"` | 直接切，保留兩平台各自 input |
| `stream.phase === "connecting"` \| `"streaming"` | reducer 不自動切。先 dispatch `REQUEST_SWITCH_CONFIRM`，alert UI 彈 confirm；使用者確認後 dispatch `ABORT_STREAM` + `SWITCH_PLATFORM` |

---

## 3. `AsyncState<T>` 泛型容器

所有 9 個 AI 功能的 state 都是同一形狀：

```js
/**
 * @template T
 * @typedef {Object} AsyncState
 * @property {"idle" | "loading" | "ready" | "failed"} status
 * @property {T | null} data
 * @property {ErrorVM | null} error
 * @property {string | null} requestId   // 對應 server 發出的 run id / request id
 * @property {number | null} updatedAt   // Date.now() 最後一次寫入
 */
```

### 四態不變式（invariant）

```
idle:    data=null          error=null          requestId=null
loading: data=previous|null error=null          requestId=SET
ready:   data != null       error=null          requestId=SET
failed:  data=previous|null error != null       requestId=SET
```

**「previous」語意**：從 `ready` 進 `loading`（使用者點了「重新生成 swot」），`data` 保留上一次結果；UI 顯示 stale 標記 + spinner，不要閃成空白。`failed` 同理。

### Constructor helpers（P1 必須用這組 helper 建立 state，不得手動 spread）

```js
const Async = {
  idle: () => ({
    status: "idle", data: null, error: null, requestId: null, updatedAt: null,
  }),
  loading: (requestId, prevData = null) => ({
    status: "loading", data: prevData, error: null, requestId, updatedAt: Date.now(),
  }),
  ready: (requestId, data) => ({
    status: "ready", data, error: null, requestId, updatedAt: Date.now(),
  }),
  failed: (requestId, error, prevData = null) => ({
    status: "failed", data: prevData, error, requestId, updatedAt: Date.now(),
  }),
};
```

reducer 只能透過這四個工廠產出新 state。Linter 檢查：`grep -n 'status:\s*"\(ready\|loading\|failed\)"' src/static/js/` 應該只出現在 `Async.*` 定義檔裡。

---

## 4. `FeatureStatesVM`（9 個 AI 功能）

```js
/**
 * @typedef {Object} FeatureStatesVM
 * @property {AsyncState<AnalyzePayload>} analyze
 * @property {AsyncState<SwotPayload>} swot
 * @property {AsyncState<ReplyPayload>} reply
 * @property {AsyncState<MarketingPayload>} marketing
 * @property {AsyncState<WeeklyPlanPayload>} weeklyPlan
 * @property {AsyncState<TrainingScriptPayload>} trainingScript
 * @property {AsyncState<InternalEmailPayload>} internalEmail
 * @property {AsyncState<RootCausePayload>} rootCause
 * // chat 不放這裡，因為 chat 有 multi-turn 語意（見 §6）
 */
```

各 Payload 型別 **一一對應** `docs/v4-api-contract.md` §3 的 response body shape。例如：

```js
/**
 * @typedef {Object} ReplyPayload
 * @property {string} reply
 * @property {Platform} platform
 * @property {YtRole | null} effective_yt_role
 */
```

**這份文件不重抄 payload**；以 `v4-api-contract.md` 為準。

### 平行請求 stale-response 規則

使用者可能快速點「swot」兩次，第一個請求還沒回第二個就已送出。adapter 必須：

```
送第二次時：features.swot = Async.loading(newRequestId, prev=features.swot.data)
第一個 response / SSE event 回來時：
  if (event.requestId !== features.swot.requestId) → 丟棄，不更新 state
```

這是為什麼 `AsyncState.requestId` 是 required 欄位。

---

## 5. `StreamState`（主 analyze SSE）

對應 `docs/v4-sse-events.md`。

```js
/**
 * @typedef {Object} StreamState
 * @property {"idle" | "connecting" | "streaming" | "succeeded" | "failed" | "canceled"} phase
 * @property {string | null} runId
 * @property {number} step                // 0..totalSteps
 * @property {number} totalSteps          // SSE 回 4（Google/YouTube 一致，見 v4-sse-events.md §7）
 * @property {string} label
 * @property {number} progress            // 0..1
 * @property {Platform | null} platform       // 偵測前為 null
 * @property {YtRole | null} effective_yt_role // 偵測前為 null
 * @property {ErrorVM | null} error       // phase="failed" 時填
 * @property {number | null} startedAt    // connecting 觸發時
 * @property {number | null} endedAt      // 進 succeeded / failed / canceled 時
 */
```

**為什麼 `ended` 拆三態**：「結束」不只一種，UI 要能分別顯示「完成」「失敗」「使用者取消」。合一之後反而要再問一次「到底哪種結束」，等於把狀態機打散。

**phase 轉換圖**：

```
idle
  └─(CONNECT)─► connecting
                  │
                  ├─(SSE open)───► streaming
                  │                  │
                  │                  ├─(SSE event: result)─► succeeded
                  │                  ├─(SSE event: failed)─► failed
                  │                  └─(ABORT_STREAM)─────► canceled
                  │
                  ├─(HTTP 4xx/5xx)────► failed
                  └─(ABORT_STREAM)────► canceled
                  
succeeded / failed / canceled ─(START_NEW_RUN)─► connecting
```

**`platform` / `effective_yt_role` 欄位**：stream 上只是 snapshot，不是 single source of truth。使用者當下的選擇看 `mode.currentPlatform`；最終結果看 `features.analyze.data.platform`。stream 欄位存在只是為了進度條 label 顯示「正在分析 YouTube 影片…」。

---

## 6. `ChatState`

```js
/**
 * @typedef {Object} ChatMessageVM
 * @property {"user" | "ai"} role
 * @property {string} content
 * @property {number} createdAt
 * @property {string | null} requestId  // user 訊息對應的 request id（ai 訊息為 null）
 */

/**
 * @typedef {Object} ChatState
 * @property {"idle" | "loading" | "ready" | "failed"} status  // 最後一次送出訊息的狀態
 * @property {ChatMessageVM[]} messages
 * @property {string | null} activeContextRunId  // 訊息 context 綁定的 analyze runId
 * @property {string | null} requestId           // 當前 in-flight chat request
 * @property {ErrorVM | null} error
 */
```

### `activeContextRunId` 規則

使用者送一則 chat 時：

| `features.analyze.status` | 行為 |
|---|---|
| `ready` | 若 `chat.activeContextRunId !== features.analyze.requestId` → 先 dispatch `CHAT_CONTEXT_SWITCH`（可能彈 confirm：要換 context 嗎？）；確認後 `activeContextRunId = features.analyze.requestId` 並清空 `messages`（或開新 thread） |
| `loading` | chat UI disable，等 analyze ready |
| `failed` / `idle` | 允許 chat，但 `activeContextRunId = null`，payload 不帶 analyze 摘要 |

**不得「偷偷換 context」**：使用者問「剛剛那份分析」時，如果 context 已被新 analyze run 覆蓋，ai 會答錯。這條是強制 invariant。

---

## 7. `AlertState`（全域警示 queue）

```js
/**
 * @typedef {Object} AlertVM
 * @property {string} id                    // 唯一 id，UI dismiss 用
 * @property {"info" | "warning" | "error"} level
 * @property {string} message
 * @property {number} createdAt
 * @property {boolean} dismissible
 * @property {string | null} ttlMs          // 自動消失毫秒數；null = 需手動 dismiss
 */

/**
 * @typedef {Object} AlertState
 * @property {AlertVM[]} items
 */
```

**用途**：非任務級的全域事件——例如「SSE 連線中斷」「Gemini API 配額警告」「網路離線」。**任務級錯誤**（某個功能失敗）走 `AsyncState.error`，不進 alerts。

**為什麼不用單一 error 欄位**：
- 新錯蓋舊錯，使用者看不到完整錯誤歷史
- 不好做「可 dismiss」語意
- 多個 alert 同時出現（例：SSE 斷 + API 配額警告）會互相踩

---

## 8. `ErrorVM`

共用錯誤形狀，`AsyncState.error` / `AlertVM` 上游都用這個：

```js
/**
 * @typedef {Object} ErrorVM
 * @property {"VALIDATION_ERROR" | "SCRAPER_ERROR" | "LLM_ERROR" | "UNKNOWN_ERROR" | "NETWORK_ERROR"} code
 * @property {string} message
 * @property {boolean} retryable
 * @property {number | null} retryAfterSecs
 * @property {string | null} requestId  // 對應的 API / SSE request id
 * @property {number} capturedAt
 */
```

前四個 code 對應 `docs/v4-api-contract.md` §2.3 + `docs/v4-sse-events.md` §9；`NETWORK_ERROR` 是前端 adapter 自己產生的（fetch timeout、離線、SSE onerror），server 不會回這個 code。

---

## 9. `MetaState`

```js
/**
 * @typedef {Object} MetaState
 * @property {string} appVersion            // "4.0.0"
 * @property {Platform[]} availablePlatforms
 * @property {YtRole[]} availableYtRoles
 * @property {Object} featureFlags          // 未來旗標用
 */
```

**靜態常數**，app bootstrap 時從 `/api/meta` 或 inline bootstrap script 塞，後續不動。

---

## 10. Dispatch / Reducer 設計

### 單一入口

```js
function dispatch(action) {
  state = reduceAppState(state, action);
  scheduleRender();
}

let _renderScheduled = false;
function scheduleRender() {
  if (_renderScheduled) return;
  _renderScheduled = true;
  requestAnimationFrame(() => {
    _renderScheduled = false;
    renderApp(state);
  });
}
```

SSE progress event 頻率可能每秒 5–10 次，若每個 event 都同步重繪會卡頓。`requestAnimationFrame` 把多個同 frame 的 dispatch 合併成一次重繪。

### Action 命名公約

```
<VERB>_<NOUN>   — 例：SWITCH_PLATFORM、ABORT_STREAM、CHAT_SEND
<VERB>_<NOUN>_<PHASE>  — 非同步：START / SUCCEEDED / FAILED
  例：FETCH_SWOT_START / FETCH_SWOT_SUCCEEDED / FETCH_SWOT_FAILED
```

reducer 按 slice 拆（`reduceMode` / `reduceStream` / `reduceFeatures` / `reduceChat` / `reduceAlerts`），頂層 `reduceAppState` 組合。

### Renderer 分區

```
renderMode(state.mode)       — 渲染 tab 區
renderInput(state.input)     — 渲染 URL input
renderStream(state.stream)   — 渲染進度條 + label
renderFeatures(state.features) — 渲染 9 個結果卡片
renderChat(state.chat)        — 渲染對話 UI
renderAlerts(state.alerts)    — 渲染 alert toast
```

**DOM 操作只能在 renderer 裡**。reducer 純函式，不碰 DOM。

---

## 11. Persist 策略

瀏覽器刷新後能恢復的東西：

| 欄位 | Persist | 理由 |
|---|---|---|
| `mode.currentPlatform` | ✅ | 使用者在哪個 tab，UX 連貫 |
| `mode.ytRoleSelection` | ✅ | 使用者選好的角色不要反覆選 |
| `input.googleUrl` / `input.youtubeUrl` | ✅ | 輸入框內容不要因刷新清空 |
| `features.analyze.data`（最後一次成功） | ⚠️ 可選 | 讓使用者刷新後還能看結果；但 SSE 內的 `run` 不 persist |
| `features.*` 其他 8 個 | ❌ | 子功能結果不 persist（下次登入重跑） |
| `stream` | ❌ | in-flight SSE 絕不 persist；刷新後強制 `idle` |
| `chat.messages` | ❌ | 多輪對話不跨 session 保留（P1 不做 history） |
| `alerts` | ❌ | 警示刷新後重置 |

存儲後端：`localStorage`（key：`insightx.v4.state`），JSON 序列化 + schema version 前綴（`{"_v":"4.0.0", ...}`）。schema version 對不上直接清掉。

---

## 12. 與 SSE / API 合約的對映總表

| View Model 欄位 | 來源 |
|---|---|
| `stream.phase` | SSE connection lifecycle（自己 track） |
| `stream.step / totalSteps / label / progress / platform / effective_yt_role` | SSE `progress` event payload |
| `stream.error` | SSE `failed` event payload |
| `features.analyze.data` | SSE `result` event 的 `data` 欄位 \| POST `/api/analyze` response body |
| `features.swot.data` | POST `/api/swot` response body |
| `features.reply.data` | POST `/api/reply` response body |
| `features.marketing.data` | POST `/api/marketing` response body |
| `features.weeklyPlan.data` | POST `/api/weekly-plan` response body |
| `features.trainingScript.data` | POST `/api/training-script` response body |
| `features.internalEmail.data` | POST `/api/internal-email` response body |
| `features.rootCause.data` | POST `/api/analyze-issue` response body |
| `chat.messages[].content` | POST `/api/chat` response body `{reply}` 或使用者輸入 |
| `alerts.items[]` | 前端 adapter 偵測網路 / 全域事件時自己 push |

---

## 13. 未決事項（P1+ 再議）

1. **chat history persist**：目前 P0 不 persist。P1 若要做，需加 `chat.threads[]` 結構 + 每個 thread 綁 analyze runId。
2. **skeleton UI vs stale 顯示**：`AsyncState.loading` 帶 prev data 的情況，UI 該顯示 skeleton 還是 stale + overlay，P0 不規定。
3. **多 tab 同步**：使用者開兩個 tab，同一 localStorage。P0 不處理同步；P1 若要做，用 `BroadcastChannel` 或 `storage` event。
4. **JSDoc 泛型 VSCode 邊界 case**：`AsyncState<T>` 某些深度嵌套情況 hover 會失效；P0 接受這個限制。

---

## 14. 決策紀錄（Codex 雙 AI 挑毛病後定案）

| 原初稿問題 | Codex 毒舌點 | 最終決定 |
|---|---|---|
| 方案 A / B 二選一 | A 製造 9 套錯誤工廠；裸用 B 會把 null 帶回來 | ✅ 選 B + 明寫四態 invariant + Constructor helpers |
| 切平台自動 kill stream | UX 粗暴，使用者點錯一下子殺掉 | ✅ 加 confirm guard；stream in-flight 時不自動切 |
| chat 靠「自動帶摘要」 | 新 analyze 偷改舊 conversation context 是陰 bug | ✅ chat 綁 `activeContextRunId`，換 context 要 confirm |
| 四態靠紀律維護 | 會出現 `{status:"ready", data:null}` 非法組合 | ✅ Constructor helpers 強制入口 |
| `render()` 每次粗暴重畫 | SSE 頻繁，會卡頓 | ✅ 單一 dispatch + RAF batch |
| `StreamState.phase = "ended"` | 廢狀態，還要再問哪種結束 | ✅ 拆 `succeeded` / `failed` / `canceled` |
| 全域 `error: ErrorVM \| null` | 新錯蓋舊錯、難 dismiss | ✅ 改 `AlertState.items[]` queue |
| 「AnalyzeResultVM」命名 | 裡面其實是 9 功能，不只 analyze | ✅ 改名 `FeatureStatesVM` |
| 漏 `runId` / `requestId` | SSE 晚到 event 會污染新 run state（v3 鬼故事原因） | ✅ `AsyncState.requestId` + `StreamState.runId` 都是必要欄位；stale response 一律丟棄 |
| 漏持久化策略 | 瀏覽器刷新時 in-flight stream 若 persist 會製造殭屍 state | ✅ §11 白名單清楚列出 persist 哪些不 persist 哪些 |

---

## 15. Adapter 層責任（Checklist for P1 實作者）

1. ✅ `apiClient.js` 所有 fetch / EventSource 呼叫產生唯一 `requestId`（例：`crypto.randomUUID()`），附在 state loading 欄位上
2. ✅ 收到 response / SSE event 時先比對 `requestId`，stale 丟棄
3. ✅ 所有 `AsyncState` 寫入必須透過 `Async.idle / loading / ready / failed` helper
4. ✅ `dispatch()` 是唯一修改 state 入口；reducer 純函式
5. ✅ `renderApp()` 經 `requestAnimationFrame` 合併
6. ✅ Alert queue 自動 TTL：reducer 掛 setTimeout 送 `ALERT_DISMISS`（或 renderer 週期檢查）
7. ✅ `localStorage` 存取用 schema version gate（`"_v": "4.0.0"`）
8. ✅ SSE 連線在 terminal event 收到後立即 `eventSource.close()`；`onerror` 不自動重連
9. ✅ 切平台時若 stream in-flight，走 confirm 流程；不自動 kill
10. ✅ chat context 綁 `activeContextRunId`；換 run 要 confirm

---

**P0 合約版本**：v4.0.0-draft-1
**上游依賴**：`docs/v4-api-contract.md`、`docs/v4-sse-events.md`
