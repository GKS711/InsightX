# InsightX v4.0.0 API 契約

> **狀態**：P0 凍結草案（2026-04-21）
> **配套文件**：`docs/v4-sse-events.md`（SSE 事件型別）、`docs/v4-view-model.md`（前端 view model）
> **計劃總表**：`docs/v3-ui-migration-plan.md`（filename 帶 v3 是歷史，內容是 v4 計劃）
> **審核**：Claude 主答、Codex 審查並補強（teamwork-handbook 1 輪對話）

## 0. 凍結原則

這份契約是後端 Pydantic schema + FastAPI route handler 的唯一真相來源。P1 之後任何欄位增刪都要先改這份 doc、再改程式碼。

前端 adapter layer（`src/static/v2/api/adapters.js`）要對著這份 doc 實作。後端改欄位前必須通知前端 pair。

---

## 1. 全域約定

### 1.1 Platform enum

```python
from typing import Literal
Platform = Literal["google", "youtube"]
```

- 9 個下游 endpoint：`platform` 欄位 required，無預設值**移除 v3 的 `= "google"`** 以避免誤判。
- `/analyze`：`platform` 欄位 **optional hint**（見 §2.1），server 以 URL 偵測為主。
- 不接受大小寫變體、`"Google"`、`"yt"` 等別名，會 422。
- `"platform": null` 與省略欄位等同，視為 hint 未提供。

### 1.2 YouTube role enum

```python
YtRole = Literal["creator", "shop", "brand"]
```

- 所有 endpoint 一律新增 `yt_role: Optional[YtRole] = None` 欄位（P0 先只加欄位，P1.5 才實作 prompt 分支）。
- **canonicalization（server 執行）**：
  - `platform == "youtube"` + `yt_role` 有值 → 照用
  - `platform == "youtube"` + `yt_role` 缺值或 `null` → **server 塗為 `"creator"`**（backward-compat default）
  - `platform == "google"` + `yt_role` 有值 → **忽略**，server 以 `effective_yt_role = None` 處理，並在 response metadata 加 `warnings: ["yt_role ignored when platform=google"]`
  - `platform == "google"` + `yt_role` 缺值 → `effective_yt_role = None`
- **客戶端規範**：
  - **legacy clients** 可以省略 `yt_role`；server 會 canonicalize
  - **v4 UI clients** 在 YouTube 模式下**必須明確送** `yt_role`（UI 有選擇器就要把使用者選的值送出，不能依賴 server default）
- **effective value 暴露規則**：`/analyze` 回傳的 dict 和 SSE `result` event payload **必須**包含 `effective_yt_role` 欄位（值為 `"creator" | "shop" | "brand" | null`），讓前端 adapter 驗證 UI 選擇與 server 實際使用一致。

### 1.3 錯誤語意分層（三層）

契約把錯誤拆三層，**不**統一成單一 envelope：

| 層級 | HTTP status | 使用場景 | Body shape |
|---|---|---|---|
| **Validation / bad request** | 422 | Pydantic schema 驗證失敗、platform vs URL 衝突、yt_role 值不合法 | FastAPI 預設 `{detail: [...]}` |
| **Server error** | 500 | Gemini 爆炸、unhandled exception、爬蟲 service crash | `{detail: str}`（由 FastAPI 自動產生） |
| **Domain-level non-success（HTTP 200）** | 200 | 爬得到但沒評論（`no_reviews`）、YouTube API key 失效（`error`） | **僅限 `/analyze` 和 SSE `result` event**，shape 見 §2.1.2 |

**三層定義不可混用**。下游 9 個 AI endpoint（`/swot` 等）在 Gemini 失敗時 `src/api/routes.py` 目前會退 mock 回傳（HTTP 200），v4.0.0 **保留這個行為**但前端 adapter 必須知道這是「fallback 成功」不是真實分析。後端要在退 mock 時在 response 加 `_fallback: true` metadata，adapter 據此在 UI 標示。

### 1.4 共通 metadata 欄位（v4 新增）

所有 endpoint 回傳的 JSON top-level 新增兩個**可選** metadata 欄位（前端 adapter 讀來判斷狀態，不強制顯示）：

```json
{
  "_fallback": false,           // true = 回 mock 而非真實 AI 輸出
  "warnings": []                // string list；例：["yt_role ignored when platform=google"]
}
```

底線前綴表示 "internal metadata, not user-facing content"。前端 schemas.js 驗證時要讀但不顯示。

### 1.5 422 body shape 統一規範

**所有 422 response 統一使用 list-of-dict 格式**（不得出現裸字串 `detail`）：

```json
{
  "detail": [
    {
      "loc": ["body", "platform"],
      "msg": "platform hint 'google' conflicts with detected 'youtube' from url",
      "type": "value_error.platform_conflict"
    }
  ]
}
```

| 情境 | 如何產生 |
|---|---|
| Pydantic schema 驗證失敗（欄位缺、型別錯、enum 不合法） | FastAPI 自動產生 list-of-dict；不需要額外程式碼 |
| Route handler 自己偵測的衝突（platform vs URL、其他業務規則） | 必須寫 `raise HTTPException(status_code=422, detail=[{"loc": [...], "msg": "...", "type": "..."}])`，**禁用** `detail="字串"` |

**`loc` 慣例**：
- Query param 錯誤：`["query", "<param_name>"]`
- Body 欄位錯誤：`["body", "<field_name>"]`
- 跨欄位衝突：`["body", "__root__"]`（或 SSE query 的 `["query", "__root__"]`）

**`type` 慣例**：
- Pydantic 原生：`missing` / `value_error` / `type_error.*`
- 自訂衝突：`value_error.platform_conflict` / `value_error.yt_role_invalid`（加 `value_error.` 前綴）

前端 `adapters.js` 寫一個 `parse422(json)` 即可處理所有 422 情境，不需要為每個 endpoint 寫特例。

---

## 2. Endpoint schemas

### 2.1 POST `/api/analyze`

主流程。URL 偵測平台 → 爬蟲 → Gemini 分析。

#### 2.1.1 Request

```python
class AnalyzeRequest(BaseModel):
    url: str                                              # required
    platform: Optional[Literal["google", "youtube"]] = None    # optional hint
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None   # optional
```

**Platform hint 規則**（重要，v4 新增）：
- `platform` 省略或 `null` → server 從 URL 偵測
- `platform` 有值 + 與 URL 偵測一致 → 接受
- `platform` 有值 + 與 URL 偵測**衝突**（例：YouTube URL + `platform: "google"`）→ **422 validation error**，body 遵循 §1.5：`{"detail": [{"loc": ["body", "__root__"], "msg": "platform hint 'google' conflicts with detected 'youtube' from url", "type": "value_error.platform_conflict"}]}`

不允許 client 強制覆蓋 URL 偵測。原因：爬蟲 dispatch、fallback mock 選版本、SSE 文案、adapter mapping 都依賴 platform，放任 client 覆蓋會造成不可預期的 dispatch 錯誤。

#### 2.1.2 Response（成功）

```json
{
  "store_name": "字串（可空）",
  "platform": "google | youtube",
  "effective_yt_role": "creator | shop | brand | null",
  "total_reviews": "共分析 N 則評論/留言",
  "good": [{"label": "主題", "value": 30}, ...],
  "bad": [{"label": "主題", "value": 40}, ...],
  "_fallback": false,
  "warnings": []
}
```

欄位說明：
- `good`、`bad` 是前 3 大正/負面主題的 `{label, value}` tuple 陣列。`value` 是提及比例（整數百分比）。
- `effective_yt_role`：在 `platform="google"` 時為 `null`。

#### 2.1.3 Response（domain-level non-success，HTTP 200）

```json
{
  "store_name": "字串（可空）",
  "platform": "google | youtube",
  "status": "no_reviews" | "error",
  "total_reviews": "0",
  "good": [],
  "bad": [],
  "message": "使用者可讀的錯誤訊息",
  "_fallback": false,
  "warnings": []
}
```

`status` 欄位只在這個分支出現，成功 response **不含** `status` 欄位（這是 adapter 判斷走哪條分支的 discriminator）。

- `status == "no_reviews"`：爬得到店/影片但沒文字評論/留言
- `status == "error"`：爬蟲或 API 明確錯誤（例：YouTube API key 失效）

#### 2.1.4 Fallback mock（HTTP 200）

若爬蟲逾時或 Gemini 分析失敗，退回 mock 數據。shape 同 §2.1.2 但 `_fallback: true`。前端 adapter 讀到這個要在 UI 上標示「Demo 數據」。

---

### 2.2 SSE routes（legacy + v4 並行）

v4.0.0 採用**雙 route** 策略，避免 solo developer 直接推 git 部署時原地炸掉現有使用者。

| Route | 版本 | 事件格式 | 客戶端 | 生命週期 |
|---|---|---|---|---|
| `GET /api/analyze-stream` | v3 legacy | 自由文字 `data:` + `event: result`/`error`/`done` 混流 | 舊 `src/static/index.html`（掛 `/legacy`，待退場） | 保留至 v4.1.0 刪除 |
| `GET /api/v4/analyze-stream` | v4 | 結構化 `progress` / `result` / `failed` 三 event | **`src/static/v2/index.html`（掛 `/`，現行主 UI）** | v4.0.0 上線起永久支援 |

#### 2.2.1 v4 Query string

```
GET /api/v4/analyze-stream?url=<encoded>&platform=<google|youtube>&yt_role=<creator|shop|brand>
```

- `url`：**required**
- `platform`：**optional**，語意同 §2.1.1 hint。與 URL 偵測衝突 → **HTTP 422**，不進 SSE
- `yt_role`：**optional**，語意同 §1.2

**不存在的 flag**：`include_result`（已砍）。v4 SSE **永遠** 在成功結尾發 `event: result` 帶完整 `AnalyzeResponse`，沒有「只送進度、不送結果」模式。舊前端要這個行為就繼續用 legacy `/api/analyze-stream`。

#### 2.2.2 v4 Response

`text/event-stream`。event types、payload、ordering 定義在 `docs/v4-sse-events.md`。

#### 2.2.3 v3 legacy 契約

不在本文件範圍。legacy route 維持 v3 行為凍結不動，方便 rollback。v4 路線全部走新 route。

---

### 2.3 POST `/api/swot`

從 `good/bad` 數據生成 SWOT 分析（platform-aware）。

#### 2.3.1 Request

```python
class SwotRequest(BaseModel):
    good: list[dict]                                   # [{label, value}]
    bad: list[dict]                                    # [{label, value}]
    platform: Literal["google", "youtube"]             # required, no default
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None
```

⚠ v3 → v4 breaking：`platform` **移除 default `"google"`**。客戶端必須顯式傳。

#### 2.3.2 Response

```json
{
  "strengths": [{"point": "優勢標題", "detail": "含數據說明"}, ...],
  "weaknesses": [{"point": "...", "detail": "..."}, ...],
  "opportunities": [{"point": "...", "detail": "..."}, ...],
  "threats": [{"point": "...", "detail": "..."}, ...],
  "effective_yt_role": "creator | shop | brand | null",
  "_fallback": false,
  "warnings": []
}
```

Gemini parse 失敗時回 fallback mock（`_fallback: true`），shape 同上。

---

### 2.4 POST `/api/reply`

生成負面意見回覆（餐廳抱怨 / YouTube 觀眾留言）。

#### 2.4.1 Request

```python
class ReplyRequest(BaseModel):
    topic: str                                         # required
    platform: Literal["google", "youtube"]             # required
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None
```

#### 2.4.2 Response

```json
{
  "reply": "使用者可直接貼回覆的繁中文字",
  "effective_yt_role": "creator | shop | brand | null",
  "_fallback": false,
  "warnings": []
}
```

---

### 2.5 POST `/api/analyze-issue`

根源問題分析（純文字結構，用【】◆　▸ 排版，不是 Markdown；前端 `<pre>` 直出）。

#### 2.5.1 Request

同 §2.4.1（reuse `ReplyRequest` 或命名為 `IssueRequest`，欄位一樣）。**契約建議**命名為 `IssueRequest` 以語意清晰，不 reuse。

```python
class IssueRequest(BaseModel):
    topic: str
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None
```

#### 2.5.2 Response

```json
{
  "analysis": "純文字結構（【主題】+ ◆ 範疇 +　▸ bullet，前端 <pre> 直出，不渲染 Markdown）",
  "effective_yt_role": "...",
  "_fallback": false,
  "warnings": []
}
```

---

### 2.6 POST `/api/marketing`

行銷文案生成。

#### 2.6.1 Request

```python
class MarketingRequest(BaseModel):
    strengths: str                                     # required（用 "、" 或換行分隔的主題字串）
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None
```

#### 2.6.2 Response

```json
{
  "copy": "貼文文字（含 emoji + hashtag）",
  "effective_yt_role": "...",
  "_fallback": false,
  "warnings": []
}
```

---

### 2.7 POST `/api/weekly-plan`

週行動計畫（純文字結構，週一–週日純文字排版，不是 Markdown；前端 `<pre>` 直出）。

#### 2.7.1 Request

```python
class WeeklyPlanRequest(BaseModel):
    weaknesses: str                                    # required
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None
```

#### 2.7.2 Response

```json
{
  "plan": "純文字結構（週一–週日，每天 2-3 個任務，用 ◆/　▸ 排版，前端 <pre> 直出）",
  "effective_yt_role": "...",
  "_fallback": false,
  "warnings": []
}
```

---

### 2.8 POST `/api/training-script`

培訓劇本（純文字結構，NG/OK 示範 + 話術清單純文字排版，不是 Markdown；前端 `<pre>` 直出）。

#### 2.8.1 Request

```python
class TrainingScriptRequest(BaseModel):
    issue: str                                         # required
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None
```

#### 2.8.2 Response

```json
{
  "script": "純文字結構（NG/OK 示範 + 話術清單，用 ◆/　▸ 排版，前端 <pre> 直出）",
  "effective_yt_role": "...",
  "_fallback": false,
  "warnings": []
}
```

---

### 2.9 POST `/api/internal-email`

內部週報信（純文字書信格式；前端 `<pre>` 直出）。

#### 2.9.1 Request

```python
class InternalEmailRequest(BaseModel):
    strengths: str                                     # required
    weaknesses: str                                    # required
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None
```

#### 2.9.2 Response

```json
{
  "email": "書信文字（含主旨、問候、主體、署名）",
  "effective_yt_role": "...",
  "_fallback": false,
  "warnings": []
}
```

---

### 2.10 POST `/api/chat`

AI 顧問多輪對話。

#### 2.10.1 Request

```python
class ChatRequest(BaseModel):
    message: str                                       # required
    context: str = ""                                  # 當前分析報告全文（optional）
    platform: Literal["google", "youtube"]
    yt_role: Optional[Literal["creator", "shop", "brand"]] = None
```

`context` 保留為 str 單檔字串（非結構化）。前端自行組 context（把 good/bad/SWOT 等攤平成文字）後傳入。

#### 2.10.2 Response

```json
{
  "reply": "150 字以內繁中回覆",
  "effective_yt_role": "...",
  "_fallback": false,
  "warnings": []
}
```

---

### 2.11 POST `/api/debug-scrape`（開發用）

純爬蟲測試，不呼叫 AI。不在前端使用範圍內，保留既有 shape。

---

### 2.12 GET `/api/meta`（v4 新增 — 前端 bootstrap）

前端在 app 啟動時打一次，取得 view model `MetaState` 的靜態常數。**v4.0.0 新增**，v3 legacy 前端不使用。

#### 2.12.1 Request

```
GET /api/meta
```

無 query、無 body。

#### 2.12.2 Response（HTTP 200）

```json
{
  "appVersion": "4.0.0",
  "availablePlatforms": ["google", "youtube"],
  "availableYtRoles": ["creator", "shop", "brand"],
  "featureFlags": {
    "sse_v4": true,
    "chat_history_persist": false
  },
  "_fallback": false,
  "warnings": []
}
```

| 欄位 | 型別 | 說明 |
|---|---|---|
| `appVersion` | string | 當前後端版本（對應 `package.json` / `pyproject.toml`） |
| `availablePlatforms` | `Platform[]` | 前端 tab 顯示哪些平台；列表為空則隱藏所有 tab |
| `availableYtRoles` | `YtRole[]` | YouTube 模式下可選的角色；列表為空則隱藏角色選擇器 |
| `featureFlags` | `{[key: string]: boolean}` | P1+ 逐步加旗標；P0 先有 `sse_v4`（永遠 true，只是讓前端知道新 SSE 可用） |

**Cache 規則**：
- Response header 加 `Cache-Control: public, max-age=300`（5 分鐘）
- 前端 bootstrap 讀一次即 cache 到 memory，整個 session 不重打

**錯誤情境**：
- `appVersion` 讀不到 → 500，`{"detail": "Server metadata unavailable"}`
- 不做 422 驗證（無 input）

---

## 3. v3 → v4 Migration

### 3.1 Breaking changes（後端）

| 變更 | 影響面 | 緩解 |
|---|---|---|
| 9 個 endpoint request 加 `yt_role` | 小：optional，向下相容 | 無需緩解 |
| `/analyze` 加 `platform` hint | 小：optional | 無 |
| `platform` 移除 `= "google"` default（8 個下游 endpoint） | 中：舊 client 沒傳 `platform` 會 422 | legacy 前端 (`src/static/index.html`) 已經每次都傳 `platform`，不受影響 |
| Response 加 `effective_yt_role`、`_fallback`、`warnings` | 小：新增欄位，舊 client 忽略即可 | 無 |
| 新增 `/api/v4/analyze-stream` 結構化 SSE（`progress`/`result`/`failed`） | 小：舊路由 `/api/analyze-stream` 凍結保留，v3 前端不受影響 | 雙 route 並行，新前端走新路由 |
| 舊 `/api/analyze-stream` 標記為 legacy，凍結在 v3 行為 | 小：不變就是緩解 | v4.1.0 再考慮刪 |

### 3.2 新增欄位 vs 既有

| Endpoint | 新增 request 欄位 | 新增 response 欄位 |
|---|---|---|
| `/analyze` | `platform?`, `yt_role?` | `effective_yt_role`, `_fallback`, `warnings` |
| `/analyze-stream` (legacy) | — 不變，凍結 | — 不變，凍結 |
| `/api/v4/analyze-stream` (新) | query `url`, `platform?`, `yt_role?` | 結構化事件，見 sse-events doc |
| `/swot` | `yt_role?` | `effective_yt_role`, `_fallback`, `warnings` |
| `/reply`, `/analyze-issue`, `/marketing`, `/weekly-plan`, `/training-script`, `/internal-email`, `/chat` | `yt_role?` | `effective_yt_role`, `_fallback`, `warnings` |

### 3.3 前端 adapter 責任清單

P1 實作 adapter 時必須處理：

1. 讀 `_fallback: true` → UI 打「Demo 數據」標籤
2. 讀 `warnings[]` → console.warn 每條 warning
3. 比對 UI 選的 `yt_role` vs response 的 `effective_yt_role`；不一致時在 devtools 印 mismatch（不打斷使用者）
4. 遇到 `status: "no_reviews" | "error"` → 顯示空狀態 + `message` 文字，不進入 dashboard
5. 遇到 422 → 顯示表單驗證錯誤（不是通用錯誤頁）
6. 遇到 500 → 通用錯誤頁 + retry 按鈕

---

## 4. 驗證規則總表（後端 implementation guide）

1. **platform vs URL 衝突**：422，在 route handler（不是 Pydantic validator）檢查，因為需要先跑 `is_youtube_url(url)` 再比對
2. **yt_role canonicalization**：在 route handler 或 service layer 做，**不要** 在 Pydantic model 做（保持 schema 純淨）
3. **effective_yt_role 回傳**：由 service layer 計算後塞進 response dict
4. **_fallback 標記**：Gemini 失敗退 mock 時設 `True`；正常成功設 `False`
5. **warnings 聚合**：一個 list，canonicalization 過程中 append string

---

## 5. 未解問題（P0 後追蹤）

- **(a)** 何時刪除 legacy `/api/analyze-stream`？目前計畫在 v4.1.0 minor bump 時刪除，前提是 P1-5 驗收後新前端穩定運行至少一週無使用者回報。
- **(b)** `yt_role` 未來要不要擴充成 list（例：`["shop", "brand"]` 雙視角）？v4.0.0 先不做，若 P1.5 驗收時發現 shop/brand 客戶需要 crossover 分析再議。
- **(c)** `_fallback` 和 `warnings` 是否要改成正式欄位（不帶底線）？看 P3 前端實測，若 adapter 穩定用這兩個欄位就正名。

---

## 6. 變更紀錄

| 日期 | 版本 | 變更 |
|---|---|---|
| 2026-04-21 | v1.0 | P0 初版（Claude 主答、Codex 1 輪審查） |
