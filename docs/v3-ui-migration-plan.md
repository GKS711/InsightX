# InsightX v4.0.0 UI 遷移計劃書

> **建立時間**：2026-04-21  
> **最後更新**：2026-04-21（版本號校正為 v4.0.0：Claude Design + SSE breaking change）  
> **負責人**：Claude（Cowork）+ 使用者 GKS  
> **狀態**：P0 待啟動 / 等使用者確認動工

## 版本號說明

此版本由 v3.0.0（蝦皮放棄訂版）升到 **v4.0.0**（非 v3.1.0），理由：

- **Breaking**：SSE 事件格式從自然語言 log 改結構化 event（前端 legacy 相容需 fallback）
- **Breaking**：9 個 endpoint 新增 `yt_role` 欄位 + `platform` 收斂成 enum（Pydantic 驗證行為變化）
- **Breaking**：Prompt 系統從 if/else 分支重寫成 9+2+3+shared block 組合
- **Major**：前端技術棧從 Tailwind HTML 換成 React + Babel standalone（Claude Design 產出）
- **Major**：新增 3 個工具 modal + 1 個 Advisor drawer UI

依 SemVer 2.0.0，backward-incompatible API change = MAJOR bump。舊前端 `src/static/index.html` 降格為 legacy fallback，但 API 端透過 `?include_result=false` 等 flag 保持可用。

---

## 1. 背景

InsightX v3.0.0 於 2026-04-21 完成訂版（蝦皮模組放棄、回到 Google Maps + YouTube 雙模式架構）。使用者接著用 **Claude Design（Anthropic Labs, 2026-04-17 release）** 產出一份新的 React 單檔前端設計，希望取代現有 Tailwind HTML 前端。

本計劃書追蹤「v2-design → 接現有後端」的完整工程範圍，作為 compaction 後的交接文件。

---

## 2. 名詞定義（重要）

| 名詞 | 意義 |
|---|---|
| **`v2.0.0`**（舊名） | git 歷史版本，2026-03 加 YouTube 頻道模式的版本；程式在 `src/static/index.html`，Tailwind CDN 純 HTML |
| **`v2-design`** | Claude Design 產出的新 React 單檔，**本計劃書要接的東西** |
| **`v3.0.0`** | 現行訂版版本（蝦皮已放棄），後端 API 合約基礎 |
| **`v4.0.0`** | 計劃中的遷移目標（UI + API + prompt 重構全含，本計劃書的產出） |

**v2-design 檔案位置**：
- 原始上傳：`/Users/gankaisheng/Library/Application Support/Claude/local-agent-mode-sessions/{session}/local_{id}/uploads/InsightX v2.html`
- 遷入位置（P0 後）：`src/static/v2/index.html`（或等 P3 決定）

---

## 3. 使用者拍板的 5 個決定（不再翻盤）

| # | 主題 | 決定 |
|---|---|---|
| 1 | 前端架構 | **保留 Babel standalone 單檔**（不拆 Vite）；v4.1.0 後若破 3500 行再重估 |
| 2 | YouTube 角色 | **後端 9 個 prompt 加 `yt_role` 參數分支**（creator / shop / brand） |
| 3 | AnalyzingBlock 進度 | **後端調整 SSE log 讓 v2 步驟對齊**（已改進為結構化 event，見 §6） |
| 4 | 9 個 AI 功能 UI | 實測 v2-design **只有 7 個 section**，缺 4 個（見 §5）；需 P3 補 |
| 5 | 資料形狀 | **寫 adapter layer**，保留 v2 組件不動；但分成 4 個 module（見 §6） |

---

## 4. v2-design 現況盤點

### 4.1 技術棧

- React 18.3.1 + `@babel/standalone` 7.29.0（in-browser JSX 編譯）
- OKLCH 色票：coral `oklch(0.68 0.205 30)`、apple-blue `oklch(0.56 0.22 258)`
- 字型：Manrope / Noto Sans TC / JetBrains Mono
- 2776 行單檔，零 `fetch()`、零 `/api/` 呼叫，全部 mock data

### 4.2 狀態機

- App 層：`phase = landing | shop | yt`
- LandingPage 層：`phase = choose | input | analyzing`、`mode = shop | youtube`、`ytRole = creator | shop | brand`
- AnalyzingBlock：`setTimeout(() => setStep(s => s + 1), 550 + Math.random() * 350)` 假進度

### 4.3 既有 UI section 清單

| Section | 位置（行號） | 對應後端 API | 備註 |
|---|---|---|---|
| §01 情感判讀（店家） | 1677 | `/api/analyze` 情感部分 | |
| §02 顧客主題（店家） | 1759 | `/api/analyze` themes | |
| §03 SWOT（店家） | 1818 | `/api/swot` | |
| §04 原始聲音（店家） | 1879 | `/api/analyze` reviews | |
| §05 一週三件事 | 2446 | `/api/weekly-plan` | |
| §06 回覆草稿 | 2499 | `/api/reply` | |
| §07 行銷素材 | 2543 | `/api/marketing` | |
| §01 觀眾反應高峰（YT） | 2109 | `/api/analyze` | |
| §02 留言主題（YT） | 2204 | `/api/analyze` themes | |
| §03 反覆被問的問題（YT） | 2270 | **新概念，無對應 endpoint** | 從 themes 衍生或新增 |
| §04 需要跟進的留言（YT） | 2314 | `/api/reply` | |

### 4.4 缺失的 UI（後端有 endpoint 但 v2-design 沒做）

| 功能 | 後端 endpoint | 現狀 | P3 要做 |
|---|---|---|---|
| 根源問題分析 | `/api/analyze-issue` | 零 UI | ShopToolkit modal |
| 培訓劇本 | `/api/training-script` | 零 UI | ShopToolkit modal |
| 內部信 | `/api/internal-email` | 零 UI | ShopToolkit modal |
| AI 對話顧問 | `/api/chat` | `Advisor = () => null` stub（line 2573）+ DashNav 有「問 AI」按鈕（line 1615、2749） | 補 Advisor 成 persistent drawer |

---

## 5. 現有後端 API 總覽

```
POST /api/analyze           — 主流程：URL → 爬蟲 → AI 分析
GET  /api/analyze-stream    — SSE 即時進度
POST /api/swot              — SWOT 生成
POST /api/reply             — 回覆草稿
POST /api/analyze-issue     — 根源問題分析
POST /api/marketing         — 行銷文案
POST /api/weekly-plan       — 週行動計畫
POST /api/training-script   — 培訓劇本
POST /api/internal-email    — 內部週報
POST /api/chat              — AI 顧問對話
```

所有端點接受 `platform: "google" | "youtube"`（預設 `"google"`）。P0 後將加 `yt_role`。

程式入口：`src/services/llm_service.py`（9 個方法）、`src/api/routes.py`、`src/config/prompts.py`。

---

## 6. Codex 審核後的關鍵改動（⚙ Codex 貢獻）

本節記錄 Codex 審查原計畫後補強的重點。**開工時必須遵守**。

### 6.1 API 契約統一

⚙ **不要「先改一個 endpoint 試水溫 yt_role」**。會導致前端看 creator 視角分析但後續工具是 generic prompt。

**正確做法**：P0 一次把 9 個 endpoint 的 request schema 都加 `yt_role` 欄位（先只傳遞、不實作 prompt 分支）。P1.5 才實作 prompt 語意。

### 6.2 Pydantic schema 規則

- `platform` 收斂成 `Literal["google", "youtube"]`（目前是 str）
- `yt_role: Optional[Literal["creator", "shop", "brand"]]`
- **規則**：`yt_role` 只在 `platform == "youtube"` 時生效；google 請求夾帶 `yt_role` → warning log，不報 422
- **GET `/api/analyze-stream` 的 query string 也要支援 `yt_role`**（否則 role 上下文會在 SSE 斷掉）

### 6.3 prompt 架構：9 + 2 + 3 + shared（不是 27）

⚙ **反模式**：9 task × 3 role = 27 份完整 prompt → 必定失控

**正確架構**：
```
{base_task_prompt}       ← 9 個
Platform context:
{platform_context}       ← 2 個（google / youtube）
Audience / role context:
{yt_role_context}        ← 3 個（creator / shop / brand）
Output schema:
{output_schema}          ← 共用
Tone and constraints:
{style_rules}            ← 共用
```

**role context 必須定義「分析維度」**，不只是「語氣」：
- `creator`：觀眾留存、內容節奏、互動、下集題材
- `shop`：轉換、商品疑問、購買阻力、客服回覆
- `brand`：品牌感知、活動反應、受眾定位、聲量風險

### 6.4 SSE 結構化事件

⚙ **不要 parse 自然語言 log**（Serper 翻頁次數不固定、錯誤重試會亂）

**Event types**：`status / step / result / error / done`

**payload shape**：
```json
{
  "phase": "crawl|analyze|done",
  "step": 2,
  "totalSteps": 6,
  "label": "擷取評論",
  "message": "已取得 80 則評論",
  "progress": 0.35
}
```

⚙ **關鍵**：`/api/analyze-stream` 的最後一個 `result` event **必須直接回傳完整分析結果**。不要 SSE 跑完後還要再 POST `/api/analyze` 重跑一次（成本翻倍 + 可能結果不一致）。

### 6.5 Adapter 分 4 層（不要一個大雜燴）

| Module | 職責 |
|---|---|
| `apiClient.js` | fetch / SSE / 錯誤處理 / 重試 |
| `adapters.js` | backend DTO → UI view model mapping |
| `schemas.js` | 必要欄位驗證（輕量 validator，不用 zod） |
| `fixtures.js` | v2 原始 mock data 保留，供 fallback / dev mode |

### 6.6 缺 4 UI 的位置（工具型 vs 顧問型）

- **工具型**（一次性生成）：`/api/analyze-issue`、`/api/training-script`、`/api/internal-email` → `ShopToolkit` 加 trigger button，點擊開 modal/drawer
- **顧問型**（多輪對話）：`/api/chat` → 補 `Advisor` stub 成 **persistent drawer**（不是 modal）

### 6.7 Legacy fallback（不要硬換主入口）

- `/` 根據 feature flag 決定載入 v2 或 legacy
- `/?ui=legacy` query override（localStorage 保存使用者偏好）
- 右下角提供「切回舊版」連結
- 環境變數 `INSIGHTX_UI_VERSION=v2|legacy`
- **server-side 判最穩**：因為 v2 首屏 JS 炸了時前端按鈕出不來

### 6.8 Babel standalone 停損點

- **v4.0.0 保留**
- **觸發 v4.1.0 遷 Vite 條件**（任一達成）：
  - 檔案超過 3500 行
  - CSP policy 卡 `@babel/standalone`
  - 企業客戶反應舊機器 runtime 編譯太慢
  - 需要 component-level tests / TypeScript

---

## 7. 最終 Phase 計劃

| Phase | 工時 | 交付物 | 驗收 |
|---|---|---|---|
| **P0 契約凍結** | 0.5 天 | 3 份文件（見 §7.1） | 使用者簽核 |
| **P1 主幹打通** | 1–2 天 | SSE 結構化 + dashboard 接真資料 + adapter 4 層 | 真 URL → 真爬蟲 → dashboard 顯示真**情感/主題/評論**（SWOT 不算） |
| **P1.5 yt_role 架構** | 1 天 | prompt block 9+2+3+shared | 9 個 endpoint 都接受 yt_role；creator/shop/brand 輸出維度有差異 |
| **P2 工具接線** | 2–3 天 | SWOT / weekly / reply / marketing 4 個既有 UI 接通 | 4 個按鈕 → loading → API → 真內容顯示 |
| **P3 補 UI + 收尾** | 2 天 | 3 modal + Advisor drawer + legacy fallback + smoke test | v2 上線、legacy 可切、smoke test 全過 |

**總估**：6.5 – 8.5 天

### 7.1 P0 交付物清單

1. **`docs/v3-api-contract.md`** — Pydantic schema 變更清單（9 個 endpoint + platform enum + yt_role optional + validation rules）
2. **`docs/v3-sse-events.md`** — SSE event 型別定義（status / step / result / error / done 的 payload schema）
3. **`docs/v3-view-model.md`** — 前端 view model 形狀（JSDoc-style 型別，不引入 TypeScript 以保留 Babel standalone）

### 7.2 P1 主幹打通 — 實作順序

1. 後端 `/api/analyze-stream` 改結構化 event（yield `event: status\ndata: {...}`）
2. 最後一個 event 改成 `event: result` 直接帶完整 `AnalyzeResponse`
3. 前端建立 `src/static/v2/api/` 目錄：
   - `apiClient.js`（含 `streamAnalyze(url, yt_role, onEvent)`）
   - `adapters.js`（`toShopDashboardVM(dto)`、`toYtDashboardVM(dto)`）
   - `schemas.js`（`validateAnalyzeResponse(dto)`）
   - `fixtures.js`（搬 v2-design 原本的 mock）
4. 改 `InsightX v2.html` 的 AnalyzingBlock：`setTimeout` → `EventSource`
5. 改 ShopDashboard / YouTubeDashboard：props 來源從 constants 改 adapter

### 7.3 P1.5 yt_role 架構 — 實作順序

1. 重構 `src/config/prompts.py`：拆成 `TASK_PROMPTS` / `PLATFORM_CONTEXTS` / `YT_ROLE_CONTEXTS` / `SHARED_BLOCKS`
2. 寫 `compose_prompt(task, platform, yt_role=None) -> str` 組合 function
3. 改 `src/services/llm_service.py` 9 個方法：讀 `yt_role` → `compose_prompt`
4. 改 Pydantic schema：9 個 request model 加 `yt_role`
5. 改 `/api/analyze-stream` query string 支援 yt_role

### 7.4 P2 工具接線 — 實作順序

| 順序 | Endpoint | v2-design 對應 | 補 loading/error |
|---|---|---|---|
| 1 | `/api/swot` | §03 SWOT | spinner + retry |
| 2 | `/api/weekly-plan` | §05 一週三件事 | spinner + retry |
| 3 | `/api/reply` | §06 回覆草稿 + YT §04 | spinner + retry |
| 4 | `/api/marketing` | §07 行銷素材 | spinner + retry |

### 7.5 P3 補 UI + fallback — 實作順序

1. 在 ShopToolkit 加 3 個 trigger button + modal：
   - `RootCauseModal`（`/api/analyze-issue`）
   - `TrainingScriptModal`（`/api/training-script`）
   - `InternalEmailModal`（`/api/internal-email`）
2. 補 `Advisor` stub 成 `AdvisorDrawer`（右側 persistent drawer，支援多輪對話）
3. `src/main.py` 加 feature flag：
   - 環境變數 `INSIGHTX_UI_VERSION`
   - `/?ui=legacy` query override
   - `/` 路由根據 flag 回傳 v2 或 legacy HTML
4. v2 頁面右下角加「切回舊版」連結
5. 寫 smoke test：每個 endpoint POST 一次、SSE 完整流程一次

---

## 8. 風險 & 未決問題

| 風險 | 緩解 |
|---|---|
| Gemini 回傳 JSON 不穩定，adapter 某些欄位缺失 | `schemas.js` 驗證 + UI 顯示「此項資料暫缺」 |
| SSE 長連線在反向代理（nginx、Cloudflare）buffering | P1 驗收加 `X-Accel-Buffering: no` header |
| Babel standalone 在 CSP 嚴格的企業網路被擋 | P3 smoke test 時測 `Content-Security-Policy: script-src 'self'` |
| yt_role brand/shop 分析品質比 creator 差（因為 Gemini 訓練偏 creator 語料） | P1.5 驗收用同一支影片跑 3 role 比對輸出 |
| v2 首屏 JS 炸掉 → 「切回舊版」按鈕也出不來 | 預設 cookie / localStorage 記住上次使用版本；server-side flag 為主 |

**未決問題**（P0 要答）：
- (a) `/api/analyze-stream` 是否應**同時支援**「回傳 result event」和「不回傳」兩種模式？（為了讓舊前端 `src/static/index.html` legacy 模式還能用）→ 決議：是，用 `?include_result=true` 控制
- (b) YT §03「反覆被問的問題」要新增 endpoint 還是從 themes 衍生？→ 決議：P2 先從 themes 衍生；若品質不足，v4.1.0 再新增

---

## 9. Compaction 後恢復用 — 關鍵路徑

**compaction 後 Claude 要重讀**：
1. 本檔 `docs/v3-ui-migration-plan.md`
2. `CLAUDE.md`（v3.0.0 專案現況）
3. `HANDOFF.md`（最後交接狀態）
4. v2-design 原檔（若還在 uploads）或遷入後的路徑

**記憶檔對應**：
- `project_insightx_shopee_dropped.md` — 蝦皮放棄背景（訂版前置）
- （P0 開工後新增）`project_insightx_v3_ui_migration.md` — 本計劃進度快照

**當前進度**：**P0 尚未啟動，等使用者確認動工**。

---

## 10. 變更紀錄

| 日期 | 版本 | 變更 |
|---|---|---|
| 2026-04-21 | v1.0 | 初版，含 Codex 審核後的 5 Phase 計劃 |

