# InsightX v4.0.0 SSE 事件規格（`/api/v4/analyze-stream`）

> **狀態**：P3.11 已鎖定（合約 + 實作 + 測試三方對齊，validate_jsx + test_reducer 全綠）。
> **範圍**：只適用 `/api/v4/analyze-stream`（GET + SSE）。其他 endpoint 照 `docs/v4-api-contract.md`。
> **路徑歷史**：P0 草稿原本寫 `/api/analyze-stream`，P1-2 實作時加 `/v4` 前綴避免跟 legacy `/api/analyze-stream`（v3 自由文字流）撞名。
> **相對 v3 的變更**：v3 自由文字 `data:` log 與結構化 `result` / `error` 混流造成前端解析混亂，v4 全面結構化、砍掉 log 字串、砍掉 `done` event、砍掉 `include_result` 旗標。

---

## 1. 設計原則

1. **單一進度 event**：v3 把階段轉換與細粒度進度分兩條 stream，前端要自己合併。v4 只有一個 `progress`，所有進度資訊在同一個 payload 裡。
2. **Terminal event 即終點**：`result` 或 `failed` 其一，送完立刻關 TCP。不再補 `done`。
3. **payload 永遠單行 JSON**：多行 JSON 會破壞 SSE 分隔。
4. **空行結尾**：每個 event 的 `data:` 後必須跟一個空行，否則瀏覽器不會派發。
5. **欄位後補只限 `platform` / `effective_yt_role`**：這兩個要等 scraper 偵測完才知道，允許在初期 event 裡為 `null`。其他欄位全部首次出現就定型。

---

## 2. HTTP 介面

### 端點與方法

```
GET /api/v4/analyze-stream?url={url}
```

`EventSource` 原生只能 GET，不能送 JSON body、不能自訂 headers。auth 只能靠 cookie（或省略）。

### 必要 response headers

```
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

`X-Accel-Buffering: no` 是 nginx 關鍵。若 proxy buffering 沒關，前端會一次收到所有 event，SSE 直接報廢。

### Query params

| 欄位 | 必要 | 說明 |
|---|---|---|
| `url` | ✅ | 待分析的 URL（Google Maps 店家 / YouTube 影片）。server 端偵測平台。 |
| `platform` | ❌ | 可選 hint（`"google"` / `"youtube"`）。若與 URL 實際偵測結果衝突 → **HTTP 422，不進 stream**。 |
| `yt_role` | ❌ | 可選（`"creator"` / `"shop"` / `"brand"`）。YouTube 時 server 會 canonicalize 成 `"creator"`。 |

### 兩層 validation 策略

EventSource 拿不到 response body，HTTP 錯誤在前端 `onerror` 裡只有 `readyState=CLOSED`，不會給 JSON。為了讓前端能拿到清楚錯誤訊息：

| 錯誤型態 | 回應方式 |
|---|---|
| 缺 `url` / query 畸形 / URL / `platform` 衝突 | HTTP 422 + JSON body，**不進 stream** |
| URL 可解析但爬蟲 / LLM 分析失敗 | HTTP 200 + SSE `event: failed` + close |

**前端作法**：送請求前自己 pre-validate（URL 非空、格式看起來像 http(s)），SSE `onerror` 出現時自動 fallback 顯示「連線中斷，請重試」，不試著解析 body。

---

## 3. Event 類型（P0 只有 3 個）

| Event | 功能 | 出現次數 |
|---|---|---|
| `progress` | 階段 / 步驟進度快照 | 1..N |
| `result` | 成功終結，帶完整 `AnalyzeResponse` | 0 或 1 |
| `failed` | 失敗終結，帶結構化錯誤 | 0 或 1 |

**為什麼用 `failed` 不用 `error`**：原生 `EventSource.onerror` 就叫 error，代表連線層錯誤。自訂同名 event 會讓前端 handler 命名打架。`failed` 明確是「後端任務失敗」的 application-level terminal。

---

## 4. Event payload schemas

### 4.1 `progress`

```
event: progress
data: {...}

```

```json
{
  "phase": "connected",
  "step": 0,
  "totalSteps": 4,
  "label": "Connected. Waiting for server to start analysis.",
  "progress": 0.0,
  "platform": null,
  "effective_yt_role": null
}
```

| 欄位 | 型別 | 必要 | 說明 |
|---|---|---|---|
| `phase` | string enum | ✅ | `"connected"` \| `"scraping"` \| `"analyzing"` \| `"finalizing"` |
| `step` | int ≥ 0 | ✅ | 目前步驟編號 |
| `totalSteps` | int ≥ 1 | ✅ | 整體步驟總數（server 端固定） |
| `label` | string | ✅ | 給使用者看的一句話描述 |
| `progress` | float 0..1 | ✅ | 整體進度比例（首 event = 0.0，terminal 前最後一個 progress 可以 = 1.0） |
| `platform` | `"google"` \| `"youtube"` \| `null` | ✅ | scraper 偵測出平台之前為 `null`；之後所有 event 必須一致 |
| `effective_yt_role` | `"creator"` \| `"shop"` \| `"brand"` \| `null` | ✅ | platform=youtube 時為 `"creator"`；其他為 `null` |

### 4.2 `result`

```
event: result
data: {...}

```

```json
{
  "platform": "youtube",
  "effective_yt_role": "creator",
  "durationMs": 18542,
  "data": { /* 等同 POST /api/analyze 的 response body（見 v4-api-contract.md §3.1） */ }
}
```

| 欄位 | 必要 | 說明 |
|---|---|---|
| `platform` | ✅ | 最終偵測出的平台，與 stream 過程一致 |
| `effective_yt_role` | ✅ | 最終 canonical role（非 YouTube 為 `null`） |
| `durationMs` | ✅ | 從 SSE 連線成功到此 event 的毫秒數 |
| `data` | ✅ | 完整 `AnalyzeResponse` payload |

`data` 內容不在此文件重述，以 `docs/v4-api-contract.md` §3.1 為準。

### 4.3 `failed`

```
event: failed
data: {...}

```

```json
{
  "code": "SCRAPER_ERROR",
  "message": "Failed to fetch target URL after 3 retries.",
  "retryable": true,
  "retry_after_secs": 30,
  "platform": "google",
  "effective_yt_role": null,
  "durationMs": 4210
}
```

| 欄位 | 必要 | 說明 |
|---|---|---|
| `code` | ✅ | `"VALIDATION_ERROR"` \| `"SCRAPER_ERROR"` \| `"LLM_ERROR"` \| `"UNKNOWN_ERROR"` |
| `message` | ✅ | 給使用者看的一句話；不得包含 stack trace / 敏感資訊 |
| `retryable` | ✅ | 產品語意——按同一 URL 立刻重試是否可能成功 |
| `retry_after_secs` | ❌ | 建議等待秒數；`retryable=true` 且有速率限制時才出現 |
| `platform` | ✅ | 偵測到才填；偵測前失敗則為 `null` |
| `effective_yt_role` | ✅ | 同上 |
| `durationMs` | ✅ | 從連線成功到 fail 的毫秒數 |

**前端對 `retryable` 的正確行為**：

- `retryable=true` **只代表 UI 可以顯示「重試」按鈕**，不得自動重試。
- 只在 `retry_after_secs` 有值 + 使用者沒按任何按鈕時才考慮倒數自動重試。
- `retryable=false` → UI 不顯示重試，引導使用者換 URL。

---

## 5. 順序保證

```
progress (phase="connected", platform=null, effective_yt_role=null)
progress (phase="scraping", platform=null|detected, ...)
progress (phase="scraping", platform=detected, ...)
...
progress (phase="analyzing", platform=detected, effective_yt_role=role|null)
...
progress (phase="finalizing", platform=detected, effective_yt_role=role|null, progress=1.0)
(result 或 failed 其中一個，然後 server close)
```

### 硬性規則

1. **首個 event 必為** `progress` with `phase="connected"`。
2. **terminal event** 恰好一個：`result` 或 `failed`。
3. terminal event 後 server 立刻關 TCP，前端必須呼叫 `eventSource.close()`。
4. 一旦 `platform` 從 `null` 變成 `"google"` / `"youtube"`，之後所有 event 的 `platform` 必須等於這個值，**不得再變回 `null`，不得切平台**。
5. `step` 與 `progress` 單調不減。
6. `totalSteps` 在整個 stream 生命週期固定。

### 心跳

server 每 15 秒送一次 SSE comment 避免 proxy / browser timeout：

```
: ping

```

comment 不會觸發 `EventSource` 的任何 handler，前端收到即丟。

---

## 6. 無 resume、無 Last-Event-ID

v4 P0 不支援重連續傳：

- server 忽略 `Last-Event-ID` 請求 header。
- 每次連線都開新的 analyze job，完全重跑。
- 任務不是冪等的（爬到的留言、LLM 生成的內容都可能不同）。
- 前端收到 terminal event 後必須 `close()`；即使沒收到 terminal 就斷線，也不得自動 reconnect。

這條定義成合約，是為了避免 P1+ 誤把 SSE 當「可恢復的長任務通道」。真要做 resumable 任務要換 job queue + polling，不是改 SSE。

---

## 7. `totalSteps` 與 `phase` 的固定對照

server 端用固定順序驅動進度，前端能照 step 號畫步驟條。

**Google Maps 路徑**（`totalSteps=4`）

| step | phase | label（範例） |
|---|---|---|
| 0 | connected | Connected. Waiting for server to start analysis. |
| 1 | scraping | Resolving store URL… |
| 2 | scraping | Fetching reviews via Serper… |
| 3 | analyzing | Running Gemini analysis… |
| 4 | finalizing | Packaging result… |

**YouTube 路徑**（`totalSteps=4`）

| step | phase | label（範例） |
|---|---|---|
| 0 | connected | Connected. Waiting for server to start analysis. |
| 1 | scraping | Resolving video metadata… |
| 2 | scraping | Fetching comments… |
| 3 | analyzing | Running Gemini analysis… |
| 4 | finalizing | Packaging result… |

`totalSteps` **兩路徑一致**（都是 4），前端不必因平台差異切換步驟條長度。label 文案可彈性，但 step 號 / phase 不得亂換。

---

## 8. 前端 adapter 層責任（前瞻）

本節不是 server 合約，是給 P1 adapter 實作者的提醒——放這份文件是因為 server 合約設計就是為了讓 adapter 變簡單。

1. 收 `progress` event → 合併成單一 `streamState` object（不要在 UI state 裡分 `statusPhase` / `stepCount` 兩個欄位）
2. 收 `result` event → `close()` → 展開 `data` 欄位進 view model
3. 收 `failed` event → `close()` → 依 `code` 分類顯示；`retryable + retry_after_secs` 決定重試按鈕樣式
4. `onerror` 觸發（非 application terminal）→ 顯示「連線中斷」→ **不得自動重連**
5. 每個 analyze 動作都開新 EventSource，禁用前一個

---

## 9. 錯誤 code 對照

`docs/v4-api-contract.md` §2.3 三層錯誤語意裡，HTTP 200 domain-level 那層對應到 SSE 就是 `failed` event。code 語意一致：

| SSE `failed.code` | 對應 API contract 語意 | 何時出現 |
|---|---|---|
| `VALIDATION_ERROR` | URL 可解析但內容不合法（例：YouTube 影片被刪、Google Maps 店家已關閉） | 爬蟲偵測階段 |
| `SCRAPER_ERROR` | 爬蟲技術性失敗（Serper 超時、YouTube API 配額爆） | 爬蟲執行階段 |
| `LLM_ERROR` | Gemini 回錯 / JSON parse 失敗 / 觸發 safety filter | 分析階段 |
| `UNKNOWN_ERROR` | 其他未分類 | 任何階段 |

**不存在的 code**：`AUTH_ERROR`（stream endpoint 靠 cookie，缺 auth 直接 HTTP 401，不會進 SSE）。

---

## 10. 決策紀錄（Codex 雙 AI 挑毛病後定案）

| 原初稿 | Codex 毒舌點 | 最終決定 |
|---|---|---|
| `status` + `step` 雙 event | 本質是同一個進度快照，分兩條等於 v3 混亂換個漂亮名字 | ✅ 合併為單一 `progress` |
| 用 `event: error` | 和 EventSource 原生 `onerror` 語意打架 | ✅ 改 `event: failed` |
| result / error + `done` 收尾 | `done` 會造成「收到 result 但沒收到 done」邊界 bug | ✅ 砍掉 `done`；terminal event 自己是終點 |
| `include_result=false` 相容 v3 | 把 v3 混亂的逃生門帶進新合約 | ✅ 砍掉；v4.0.0 是 SemVer MAJOR，不保留 v3 後門 |
| `retryable: bool` | 太粗，會逼前端自己決定重試策略 | ✅ 加 `retry_after_secs` + 明寫前端不得自動無腦重試 |
| 平台偵測前用獨立 `platform-detected` event | 多一個前端狀態分支，收益不大 | ✅ 仍用 `progress`，`platform` / `effective_yt_role` allow null 後補，但偵測完不得再變 |
| Last-Event-ID resume | 等於承諾任務冪等 + 事件重放 | ✅ P0 明寫不支援、server 忽略 header |

---

## 11. 尚未決定（P0 之後再議）

1. 多語系 label — 目前 label 是英文模板，P1 要看要不要 i18n。
2. 階段性 partial `result` — 目前只有最終 `result`。若 P1+ 要先送 scraped reviews 再送 AI 分析，會加 `partial_result` event。
3. server 端 tracing id — 目前沒有 event ID。若 P1+ 要接 observability，會加 `id:` 欄位（SSE 原生支援）。

---

**P0 合約版本**：v4.0.0-draft-1
**上游依賴**：`docs/v4-api-contract.md`（共用 AnalyzeResponse schema、platform / yt_role enum、錯誤三層語意）
