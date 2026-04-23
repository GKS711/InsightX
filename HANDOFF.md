# InsightX 專案交接文件

> 最後更新：2026-04-23（v4.0.0 UI · P3.11 Prompt 純文字結構結案，六輪 Codex 雙 AI 共識）
> 適用對象：下一個接手的 AI agent 或開發者
> **Current state（接手前必讀）**：主 UI = `src/static/v2/index.html`（v4，掛在 `/`），舊 `src/static/index.html` 已退到 `/legacy`。AI 文字輸出走 `<pre>` 純文字結構（【】◆　▸ 排版），**不要** marked.js / 任何 markdown render。SSE 路徑 `/api/v4/analyze-stream`。

---

## 專案概述

InsightX 是一個 AI 驅動的評論 / 留言分析平台（後端 v3.0.0 + UI v4.0.0），**支援 2 個模式**：

1. **店家評論模式**（v1.x 原有，穩定）：Google Maps 店家網址 → Serper 爬評論 → Gemini 生成餐飲／零售向報告
2. **YouTube 頻道模式**（v2.0.0 新增）：單支 YouTube 影片網址 → YouTube Data API 抓留言 → Gemini 生成頻道創作者向報告

兩模式共享 9 個下游 AI 功能（SWOT、回覆、行銷、根源分析、週計畫、培訓劇本、內部信、對話顧問），每個功能依 `platform` 參數切換 prompt persona。

> **v3.0.0 重要決策**：原規劃的蝦皮商品模式於 2026-04-21 正式放棄。WAF 在「免費 + 客戶自架 + 使用者端免人類驗證 + 每天 20+ 商品」四條件下無解。完整評估見 [`docs/archive/shopee_evaluation_2026-04-21.md`](docs/archive/shopee_evaluation_2026-04-21.md)。

---

## 架構

```
InsightX/
├── src/
│   ├── main.py                  # FastAPI 入口
│   ├── api/routes.py            # 所有 API endpoints（全部支援 platform="google"|"youtube"）
│   ├── services/
│   │   ├── scraper_service.py   # 統一入口；依 URL dispatch 到 Google Maps / YouTube
│   │   ├── youtube_scraper.py   # YouTube Data API v3 + youtube-comment-downloader 備用
│   │   └── llm_service.py       # Gemini AI 呼叫（9 個方法全支援 platform 分支；505 行）
│   ├── config/
│   │   ├── prompts.py           # Google 模式 prompt 模板
│   │   └── mock_responses.py    # Gemini 失敗時的 fallback
│   └── static/
│       ├── v2/                  # **v4 UI 主入口（現行 `/`）** — React 18 UMD + Babel + Tailwind CDN
│       │   ├── index.html       # ~3680 行（Babel block 內 3525 行 JSX）；`<pre>` 純文字直出，不用 markdown
│       │   ├── bootstrap.js     # ES module → window.IX 橋接
│       │   ├── core/            # adapters / api / async / ids
│       │   └── hooks/           # useAppReducer / useAnalyzeStream / useLocalStorage
│       ├── index.html           # **舊 v3 UI（現掛 `/legacy`，待退場）**
│       ├── App.tsx              # 獨立的決策模擬小遊戲（非主分析介面）
│       └── insightx_game.html   # 互動小遊戲
├── docs/
│   └── archive/
│       └── shopee_evaluation_2026-04-21.md  # 蝦皮放棄紀錄（tracked，永久保留）
├── CLAUDE.md                    # 技術架構（在 .gitignore，本地開發用）
├── HANDOFF.md                   # 本檔（tracked）
├── ISSUES_RESOLVED.md           # 爬蟲歷史問題與解法（在 .gitignore）
├── RESEARCH_google_maps_scraping.md  # 爬蟲研究筆記（在 .gitignore）
├── pyproject.toml               # Python 依賴（uv 管理；version=3.0.0）
├── requirements.txt             # Docker 用（對齊 pyproject.toml）
├── package.json                 # 前端依賴（version=3.0.0）
├── Dockerfile / compose.yaml    # 容器部署
└── src/static/App.tsx           # 小遊戲，非主 UI
```

**前端架構重要提醒**（P3.11 更新）：主 UI 是 `src/static/v2/index.html`（v4，掛 `/`，~3546 行 React 18 UMD + Babel single-file）。舊 `src/static/index.html`（v3，純 HTML + marked.js）已退到 `/legacy`，**只用於回退比對，不再開發**。`App.tsx` 是獨立小遊戲不是主 UI。修改主 UI 改 `v2/index.html`，AI 文字輸出走 `<pre>` 純文字結構（【】◆　▸ 排版）— **不要**重新引入 marked.js / markdown render。

---

## 目前狀態（v3.0.0）

### 穩定且已驗證
- **Google Maps 評論爬蟲**（v13.1）：純 Serper API，無瀏覽器依賴，支援分頁
  - 驗證：全家濱海店 151 則評論，86 則有文字，8 頁分頁 ✅
- **YouTube 留言爬蟲**：主路徑 YouTube Data API v3；備用路徑 `youtube-comment-downloader`（無 API key 時自動 fallback）
- **後端 API**：11 個 endpoints，全部支援 `platform` 分支
- **前端 Tab 切換**：店家評論 / YouTube 頻道兩個 Tab，`MODE_CONFIG` 文案表、`applyModeUI()` 切換 UI

### v3.0.0 變更（相對 v2.0.0）
- 移除蝦皮模組（原規劃的第 3 模式）
- 刪除 `src/services/shopee_scraper.py`、`.shopee_cache/`、所有蝦皮測試檔
- 移除依賴：`playwright`、`apify-client`、`curl_cffi`
- 移除 env vars：`SHOPEE_*`、`SCRAPELESS_*`、`SCRAPERAPI_*`、`SCRAPINGBEE_*`、`APIFY_*`
- `llm_service.py`：9 個方法移除 shopee 分支（702 → 505 行）
- `src/api/routes.py`：移除 shopee 分支 + Chrome Bridge endpoints
- `src/main.py`：移除 CORSMiddleware（原為蝦皮而設）
- `src/static/index.html`：移除第 3 Tab（MODE_CONFIG.shopee、label maps 全清）
- `pyproject.toml` / `package.json` 版本號升到 3.0.0

### Production deploy 前置需完成
- [ ] 使用者本機跑 `uv lock` 重新產生 `uv.lock`（沙盒環境無網路，無法替使用者 lock；`uv.lock` 本已 gitignored，不影響 repo）
- [ ] 在乾淨環境跑 `npm ci && npm run build` 驗證前端 build
- [ ] `docker build` 驗證（`requirements.txt` 已補 `youtube-comment-downloader`，Dockerfile 應能正常跑）

---

## 環境設定

| 變數 | 必要 | 說明 |
|------|------|------|
| `GEMINI_API_KEY` | 是 | Google Gemini API Key |
| `SERPER_API_KEY` | 店家模式必填 | Serper API（店家評論爬蟲） |
| `YOUTUBE_API_KEY` | 建議 | YouTube Data API v3 Key；未設定則自動走備用路徑 |
| `YOUTUBE_FALLBACK_MODE` | 否 | `auto`（預設）／`force-ytdlp`（強制走備用，值保留舊名以相容）／`off`（關 fallback） |
| `ENVIRONMENT` | 否 | `development` 或 `production` |

---

## 啟動指令

| 任務 | 指令 |
|------|------|
| 啟動後端 | `cd /Users/gankaisheng/VScode/Claude實作/InsightX && source .venv/bin/activate && uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload` |
| 啟動前端開發模式 | `npm run dev` |
| 打包前端 | `npm run build` |
| 重 lock Python 依賴 | `uv lock`（清掉舊 playwright/greenlet/pyee 條目） |
| 測試爬蟲（全家） | `python test_reviews_standalone.py`（如仍保留） |

> venv 路徑：`/Users/gankaisheng/VScode/Claude實作/InsightX/.venv/`

---

## 驗證清單（接手後先確認）

- [ ] `.env` 包含 `GEMINI_API_KEY`、`SERPER_API_KEY`、`YOUTUBE_API_KEY`
- [ ] `pyproject.toml` version 為 `3.0.0`，`package.json` version 為 `3.0.0`
- [ ] 本機已跑 `uv lock`（`uv.lock` 應不含 `playwright`）
- [ ] `uvicorn` 啟動無報錯，`http://localhost:8000` 可訪問
- [ ] **店家模式**：用全家便利商店 Google Maps 網址，`/api/analyze` 取得評論
- [ ] **YouTube 模式**：點首頁「YouTube 頻道」Tab，貼影片網址
  - [ ] `/api/analyze` 成功回傳情緒與主題
  - [ ] 報告標題顯示「觀眾留言」而非「顧客評論」
  - [ ] SWOT、回覆、行銷、週計畫、培訓劇本、內部信 6 個功能都能點出結果
  - [ ] AI 對話顧問回應帶 YouTuber 口吻
- [ ] `grep -rni "shopee\|蝦皮" src/` 應為空（除 `llm_service.py:2` docstring 版本註記）

---

## 開發規則（重要）

- **測試爬蟲只用全家便利商店新竹富美二店**（https://maps.app.goo.gl/gd74DaVeN6DY1bps7）—— 固定測試對象，避免浪費 API quota
- **不開瀏覽器視窗**：爬蟲全程無頭，不需要 Playwright 或 Chrome
- **問題記錄到 md 檔**：解決的問題記到 `ISSUES_RESOLVED.md`，研究筆記記到 `RESEARCH_google_maps_scraping.md`
- **Serper API 是唯一 Google Maps 爬蟲方案**，以下方法已確認無效：
  - Google Maps 內部 API（需登入 cookies）
  - headless Chrome / Playwright（被 Google 偵測）
  - Direct HTTP（短網址 JS redirect 無法跟隨）
- **不要重啟蝦皮模組**，除非使用者的四條件鬆動（見 `docs/archive/shopee_evaluation_2026-04-21.md`）

---

## 重要檔案指引

- `CLAUDE.md` — 完整技術架構（本地開發文件，在 .gitignore）
- `docs/archive/shopee_evaluation_2026-04-21.md` — 蝦皮放棄紀錄（repo tracked）
- `src/services/scraper_service.py` — 統一 URL dispatch
- `src/services/youtube_scraper.py` — YouTube Data API 留言爬蟲
- `src/services/llm_service.py` — 所有 Gemini AI 功能
- `src/config/prompts.py` — Google 模式 prompt 模板
- `src/api/routes.py` — 新增 API endpoint 從這裡加
- `src/static/v2/index.html` — **v4 主分析介面（掛 `/`）**；`core/` + `hooks/` 是 ES module 經 `bootstrap.js` 橋接到 `window.IX`
- `src/static/index.html` — 舊 v3 UI，掛 `/legacy`，待退場（修改新功能不要動這裡）

---

## 使用者偏好與習慣

### 溝通方式
- **一律用繁體中文**回答，不管問題用什麼語言
- 安裝任何套件或工具，完成後要說明安裝了什麼、裝在哪裡
- 測試瀏覽器一律用 Chrome

### 開發規則
- **測試爬蟲只用全家便利商店**（固定對象，省 API quota）
- **最終方案不能開瀏覽器視窗**（產品給客戶用，不是 POC）
- **問題記錄到 md 檔**（`ISSUES_RESOLVED.md` / `RESEARCH_google_maps_scraping.md`）
- 方法失敗就自動嘗試下一個，不要停下來問
- 重視效率，不想浪費 token 重複研究同樣的問題

### 已試過且無效的方法
- **Google Maps 內部 API**（listentitiesreviews）：需登入 cookies，匿名無法用
- **headless Chrome / Playwright**：Chrome 147 被 Google 偵測
- **Direct HTTP requests**：短網址 JS redirect 無法跟隨
- **Desktop User-Agent**：maps.app.goo.gl 回傳 200 + JS redirect；要用 Mobile UA 才能拿到 302 redirect
- **YouTube 用 Serper**：Serper 沒有 YouTube 留言 endpoint；改用官方 YouTube Data API v3
- **蝦皮所有免費路徑**：見 `docs/archive/shopee_evaluation_2026-04-21.md`

---

## 給下一個 agent 的備註

- 使用者是 GKS，開發者身份
- 爬蟲歷史很複雜，不要輕易改動 `scraper_service.py` 的核心架構，先讀 `ISSUES_RESOLVED.md` 和 `RESEARCH_google_maps_scraping.md`
- Memory 系統因 space ID 隔離，跨對話無法直接讀取；HANDOFF.md 的「使用者偏好與習慣」區塊就是 memory 的備份，每次交接時應更新此區塊
- **蝦皮模組是有意放棄的決策**，不是未完成——不要嘗試「補完」蝦皮功能

---

## v4.0.0 UI 遷移 P1–P3 已完成（2026-04-22）

P1 為 SemVer MAJOR 的底盤工程，P2 接主分析串流 + dashboard Hero/SWOT，P3 完成全部 feature adapter + chat。

### P1（2026-04-21）— 底盤契約
- **P1-1**：後端共用 canonicalizer（`src/services/canonicalizer.py`）+ 9 個 endpoint（含 /meta）統一 `effective_yt_role / _fallback / warnings` 回傳包。
- **P1-2**：新增 `GET /api/v4/analyze-stream` 結構化 SSE（4 phase：connected → scraping(1,2) → analyzing(3) → finalizing(4)）。Producer-consumer queue + 15s heartbeat + asyncio cancellation points，經 Codex peer review 修過 3 個 race（worker cancel、heartbeat 搶 terminal、cancel-on-sentinel 誤用）。舊 `/api/analyze-stream` 保留做相容期。
- **P1-3**：前端 adapter 4 層（現位於 `src/static/v2/core/`）：`ids.js`（monotonic counter）→ `async.js`（Async / Err / isFresh）→ `api.js`（apiFetch 含 timeout + openSSE）→ `adapters.js`（9 個 domain adapters + Adapters 命名匯出）。15 個 adapter 測試全過。
- **P1-4R**：遷入 v2-design 到 `src/static/v2/index.html`，為**現行 `/` 主入口**；core/ 被 bootstrap.js 橋接到 `window.IX`。舊 v3 HTML 退居 `/legacy`。12 個 reducer + persist 測試全過。
- **P1-5**：前端 SSE 消費器整合完成；靜態驗證（core/*.js node 語法檢查、routes.py AST、SSE lifecycle 純 asyncio 模擬）全過。本機真正 E2E 的步驟見 **[docs/v4-smoke-test.md](docs/v4-smoke-test.md)**。

### P2（2026-04-22）— 主分析 + Hero + SWOT
- LandingPage → `useAnalyzeStream` 連 `/api/v4/analyze-stream`；AnalyzingBlock 吃 phase label + 進度
- `buildShopViewModel` / `buildYouTubeViewModel` + `unwrapAnalyze`：SSE result 的 `{platform, data: {...}}` 正確解包
- ShopHero / ShopThemesSection / YTHero / YTCommentBreakdown 讀真實 `store_name / good / bad`
- ShopSwotSection `useEffect` 自動 fetchSwot 並 normalize `{point, detail}` → `{title, body}`

### P3（2026-04-22）— 全 feature adapter + ChatDock
- ShopRepliesSection：動態 tab 來自 `vm.themesNeg`；per-topic 本地 cache（`useState({topic: text})`）+ `useRef` inflight 追蹤；fetchReply 接上
- ShopWeekPlanSection / ShopMarketingSection：保留 mock 視覺 baseline + 下方加 AI 純文字卡片（fetchWeeklyPlan / fetchMarketing 自動觸發；P3.11 後 prompt skeleton 改用【】◆　▸ 結構，前端 `<pre>` 直出）
- **新元件 AiToolsPanel**（~150 行）：3-tab 切換 培訓劇本 / 內部週報 / 根源分析；`ShopToolkit` §08 與 `YouTubeDashboard` §07 都有
- **新元件 ChatDock**：右下角浮動面板；context 自動帶 `store_name + good/bad` 摘要；Enter 送出；歷史對話存在 reducer；DashNav「問 AI」Btn 連接
- **`<pre>` 純文字直出**（P3.11 後）：v4 不再用 marked.js / tinyMarkdown / MarkdownView 等任何 markdown render，AI 回覆直接 `<pre>` 顯示，prompt skeleton 對齊 renderer（不可有 `**` / `##`）

### 現況驗證
- `node validate_jsx.cjs` → `OK · lines: 3525`（P3.9-7 +4 行 `_fmtErr` helper；P3.12-R2 §04 後端不 cap 照抓 + 前端 slice 50 + 「精選」+ 三段 caption；P3.13 LandingPage prevSucceededRef 防 logo 跳轉；P3.14 HeroStat/Masthead/TopNav YouTube 改「影片讚數」/「次觀看」防「7380 ★」；P3.15 buildReviews + ReviewCard 加 kind="comment"：YouTube 不畫星等改「♥ N」+ §04 篩選只剩「全部」按鈕）
- `node outputs/test_reducer.mjs` → **48 pass / 0 fail**（reducer 轉換、stale discard、SSE 完整路徑、case 8/9/10 stale check + connection-lost split state、case 11a/b/c stub EventSource 真打 onerror/failed/result + adapter terminal action 帶 runId+requestId+errorVM.requestId 對齊、case 11d/11e malformed terminal JSON → STREAM_CONNECTION_LOST 外層+內層 errorVM.requestId 雙鎖、case 11f openSSE 無 opts.requestId → errorVM.requestId === null 不偷塞 runId）
- **`formatErrorMessage` helper 7 cases dynamic import 全過**（null / undefined / string / ErrorVM / empty message / no message field / fallback override）
- **舊 `outputs/smoke_features_p2.mjs` / tinyMarkdown smoke** 已隨 P3.11 退役（v4 改 `<pre>` 純文字直出，不再有 markdown render）— 之後新增 reducer / adapter 回歸統一加進 `outputs/test_reducer.mjs`

### 仍 mock 的區塊（P4+，後端沒吐資料）
- ShopReviewsSection 逐則評論 quote
- TREND_90 時間序列（Sparkline 已在真實 dashboard 隱藏）
- PDF 下載

### 要啟 v4 UI 先做什麼

1. `uvicorn src.main:app --reload` 起後端
2. 瀏覽器開 <http://localhost:8000/>（v2-design）；舊 v3 HTML 在 `/legacy`
3. 跑 [docs/v4-smoke-test.md](docs/v4-smoke-test.md) §5a-§5j checklist

---

## P3.9-5R 急救包（2026-04-22）— 雙 AI 共識結案

P3.9 是針對 P3.5 收尾後第二輪 Chrome MCP E2E 暴露的 mock leak / hardcoded fake metric / prompt-leak prompts / rank-based 假 severity 全面急救。共五輪 Codex peer review，最後 codex 回「批准結案」。

### 核心修補（依輪次）

**R1（11 條 A–K）**：移除 RepliesTool demo leak、Toolkit SWOT fallback 改讀 vm、buildThemes 等差排名、buildReviews `rating || 5`、AiToolsPanel mock prompt、AdvisorChat mock store_name、4 個 tool prompt body 改用 facts、buildAnalyzeFacts strict 二層 VM、useDashboardDisplayVM vs useAnalyzeFactsVM 拆分、Toolkit prompt 不再灌 example placeholder。

**R2（5 條）**：apiFetch 偵測 `_fallback=true`（後端 LLM fallback 200 mock 改判 fail）、buildThemes 假 placeholder label 過濾、buildReviews 缺值 rating 不再灌 5 星、buildAnalyzeFacts unwrap 後 _fallback 漏判、4 個 tool ctxKey + lastCtxRef 重新 fetch。

**R3（8 條）**：rawIn vs raw 兩層 _fallback 都檢查（unwrap 會把 wrapper 剝掉）、`Array.isArray` 防禦、rating cap to [1,5]、`facts.isReady` guard、SENTIMENT mock filter、SwotSection 真分析後不再 fallback `SWOT` mock、**reducer blast radius**（DOWNSTREAM_FEATURE_KEYS + resetDownstream 工廠：STREAM_START/STREAM_RESULT/FETCH_ANALYZE_START 都 reset）、Advisor chat context（標 P4 暫不修）。

**R4（2 條阻斷）**：reduceFeatures 移除 SWITCH_PLATFORM/SWITCH_YT_ROLE 處理時忘記在 reduceAppState 補上條件 reset；FETCH_ANALYZE_START 只 reset 下游、沒把 analyze 設 loading（會被 requestId stale check 丟掉 SUCCEEDED）。

**R5（最終結案）**：`reduceAppState` 加上「比對舊 mode vs 新 mode、真的變動才 reset 下游 + analyze=idle」；`reduceFeatures.FETCH_ANALYZE_START` 補上 `analyze: Async.loading(action.requestId, prev.data)`。Codex 回「批准結案」。

### 兩層 VM 模式（P3.9 後不可違反）

```
useDashboardDisplayVM(rawAnalyze)   → 允許 mock fallback；只給 ShopHero / Sparkline / 漂亮的 landing 預覽用
useAnalyzeFactsVM(rawAnalyze, rid)  → 嚴格零 mock；給所有 Toolkit prompt body 用
```

任何 prompt body 用 facts，任何 dashboard 視覺 baseline 用 display VM。混用是 P3.9 收掉的根因之一，**新加的 feature 必須沿用此切分**。

### 後端 mock 防線（apiFetch）

`src/static/v2/core/api.js` 第 85 行：

```js
if (data && data._fallback === true) {
  return { ok: false, error: Err.network("AI 服務暫時無法回應（後端回退至範例內容）", requestId) };
}
```

後端 LLM 失敗時會 200 + `_fallback:true` 包 mock。前端 strict facts / feature slice 不能把 mock 當 ready，必須走 *_FAILED 路徑。`/api/v4/analyze-stream` 永遠 `fallback=False`，只 POST feature endpoints + POST `/api/analyze` 會出現此情境。

### Reducer 重置規則（P3.9-5R 後鎖定）

新 analyze（`STREAM_START` / `STREAM_RESULT` / `FETCH_ANALYZE_START`）一律 reset 全部下游 7 slice。
SWITCH 真的變動才 reset，同 tab 點兩次保留 in-flight。
新增 reducer 規則前先用 `outputs/test_reducer.mjs` 跑回歸（48 case 模板，P3.11 後鎖定，含 reducer 行為 + adapter terminal action shape + openSSE malformed JSON / opts.requestId 缺值雙重鎖點）。

---

## P3.9-7 ErrorVM UI 修補（2026-04-22）— 雙 AI 共識結案

P3.9-6 在 Chrome MCP E2E smoke 期間發現的真實 bug：MarketingTool / WeekPlanTool / TrainingTool 三個 Tool 的「失敗 UI」直接寫 `String(slice.error || "未知錯誤")`，把 ErrorVM 物件 toString() 成「[object Object]」貼給使用者。Codex R1 → R2 兩輪 peer review，R2 回「批准結案」。

### 修補內容

1. **`src/static/v2/core/async.js`** 新增 export：
   ```js
   export function formatErrorMessage(error, fallback = "未知錯誤") {
     if (error == null) return fallback;
     if (typeof error === "string") return error;
     if (typeof error === "object" && typeof error.message === "string" && error.message) return error.message;
     return fallback;
   }
   ```
2. **`src/static/v2/bootstrap.js`** import 並掛到 `window.IX`（19 keys）。
3. **`src/static/v2/index.html`** Babel block 開頭加 `_fmtErr` fallback；Marketing / WeekPlan / Training 三處 `String(slice.error || ...)` 改 `_fmtErr(slice.error).slice(0, 120)`。
4. **`validate_jsx.cjs`** 移除硬編碼 sandbox 路徑，改 `path.resolve(__dirname, "src/static/v2/index.html")`，從 macOS / sandbox 都能跑。

### Invariant（P3.9-7 後不可違反）

**錯誤 UI 一律走 `_fmtErr(slice.error)` 或 `formatErrorMessage(slice.error)`，禁止 `String(slice.error)`。**
ErrorVM 是 `{code, message, retryable, retryAfterSecs, requestId, capturedAt}` 物件，直接 stringify 就是「[object Object]」。新增任何失敗 UI 用 `{_fmtErr(slice.error).slice(0, 120)}` 一行解決。

### Codex R2 結案點

- `_fmtErr` fallback 跟 `formatErrorMessage(error, fallback)` 分支等價 ✓
- `validate_jsx.cjs` 用 `__dirname` 後不再依賴 cwd ✓
- 不需要加 `Symbol.toPrimitive`（contract 是 `ErrorVM|string|null|undefined`，任意物件 coercion 反而可能引入不可預期輸出）
- 三 Tool 同類問題都改完，沒漏

### P3.9-8 真 E2E smoke 截圖驗證（2026-04-22）

使用者親自啟動 `uvicorn src.main:app --host 0.0.0.0 --port 8000`，Chrome MCP 真打 `http://localhost:8000/?_t=p397smoke` 跑完整流程，全程 `objectObjectHits: 0`：

| 流程 | 結果 | P3.9-7 驗證點 |
|------|------|---------------|
| Landing 頁面 | OK（使用者截圖確認） | — |
| Google URL 注入 + SSE 啟動 | OK，dashboard 真實渲染 | — |
| §01–§04（Hero / Sentiment / Themes / Reviews） | 全綠真資料 | — |
| §05 SWOT | 完成，evidence 帶引用 | — |
| **02 行銷文案** | 真實 AI 輸出 | `objectObjectHits: 0` ✓ |
| **03 週行動計畫** | 後端 `_fallback:true` 觸發 → 顯示「**生成失敗：AI 服務暫時無法回應（後端回退至範例內容）**」 | `objectObjectHits: 0` ✓ — `_fmtErr(ErrorVM)` 直接驗證 |
| **04 員工培訓話術** | LLM timeout → 顯示「**生成失敗：Request timed out after 45s**」 | `objectObjectHits: 0` ✓ — `_fmtErr(ErrorVM)` 直接驗證 |
| 05 內部公告信 | LLM 失敗顯示「AI 撰寫失敗，請重試」（不在 P3.9-7 範圍） | `objectObjectHits: 0` ✓ |
| AI 顧問 ChatDock | 真實回覆，含 markdown 粗體 | `objectObjectHits: 0` ✓ |

**結論**：P3.9-7 修復在真實 LLM 失敗（fallback / timeout）兩種錯誤路徑都驗證成功；ErrorVM 物件不再洩到使用者 UI；`_fmtErr` Babel-block fallback 在 `window.IX` 還沒 ready 之前的時間窗也運作正常。Task #90 完結。

---

## P3.10 LLM Timeout / Budget 重新設計（2026-04-23）— 三輪雙 AI 共識結案

### 觸發原因（P3.10-1 診斷）

P3.9-8 E2E smoke 觀察到「03 週行動計畫」/「04 員工培訓話術」顯示「Request timed out after 45s」。實測後端 `/api/weekly-plan`、`/api/training-script`、`/api/internal-email` 用 gemma-4-31b-it 生成長 markdown（700+ tokens）需要 50-75s，但 `core/api.js` `DEFAULT_FETCH_TIMEOUT_MS = 45_000` 在 LLM 還在生成時就被前端 abort，後端那次的 Gemini quota 卻已經消耗。

### R1 修補（錯）

第一輪粗暴做法：把 frontend default 拉到 120s + 後端加一層字串比對 retry。Codex peer review 挑出 6 個問題：
1. 不是所有 endpoint 都需要 120s，meta / chat / reply 本該秒回
2. retry 次數太多
3. 註解裡「最壞 7s」誤導
4. retry 判斷用字串 `"timed out"` substring 太脆弱
5. 前端 120s 對快 endpoint UX 糟糕
6. SDK 版本沒 check

### R2 修補（被 hold）

依 R1 六點全部重做：
- `llm_service._generate()` 改 `asyncio.wait_for` 控 per-attempt budget + type-based retry（`genai_errors.ServerError` / `ClientError.code==429` / `httpx.NetworkError`）
- 9 個 method 各傳自己的 `total_timeout_s`
- `core/api.js` 預設回 45s，`core/adapters.js` `makeFeatureAdapter` 新增 `timeoutMs` cfg，每個 adapter 按實際 LLM 生成時間配

Codex R2 review 回 **hold**，指出 2 個新問題：
1. `generate_swot` 仍有 try/except 吞錯誤、回「看起來合理」的 fallback dict → silent degradation：SWOT timeout 會被 route 包成成功
2. `/api/analyze` 前端 90s 但後端最壞 scraper 60s + LLM 55s = 115s，違反「backend < frontend」不變量

### R3 修補（closed）

- **`llm_service.generate_swot`**：移除 fallback dict，失敗就 raise → route 既有 except → `_fallback:true` → frontend `apiFetch` 偵測到 → `ErrorVM` → reducer `FETCH_SWOT_FAILED` → UI 正確顯示「AI 暫時無法產生」。
- **`routes.py /api/analyze`**：加 route-level total budget tracking。常數：
  - `ROUTE_ANALYZE_TOTAL_BUDGET_S = 85.0`
  - `ROUTE_ANALYZE_SCRAPER_BUDGET_S = 30.0`（原 60s 收緊）
  - `ROUTE_ANALYZE_LLM_FLOOR_S = 10.0`
- 路由開頭 `route_start = time.monotonic()`，scraper timeout 30s，LLM 用 `min(55, ROUTE_TOTAL - elapsed)`，若 < 10s 直接回 `_fallback:true` mock + warning。
- **`llm_service.analyze_content`**：簽名新增 `total_timeout_s` 參數（預設 55s 向下相容），讓 route 傳動態 budget。
- Worst case 鏈：scraper 30s + LLM 55s = 85s < frontend 90s ✓

### Per-endpoint Timeout 表（鎖定）

| Endpoint | Frontend timeoutMs | Backend total_timeout_s | 實測典型延遲 |
|----------|-------------------:|------------------------:|-------------:|
| `/api/meta` | 45s (default) | n/a | <1s |
| `/api/analyze` (POST) | 90s | route-budget 85s (scraper 30 + LLM ≤55) | ~52s |
| `/api/swot` | 60s | 55s | ~30s |
| `/api/reply` | 45s | 40s | ~10s |
| `/api/marketing` | 45s | 40s | ~15s |
| `/api/analyze-issue` | 75s | 70s | ~35s |
| `/api/weekly-plan` | 120s | 115s | ~70s 🔥 最慢 |
| `/api/training-script` | 110s | 105s | ~48s |
| `/api/internal-email` | 75s | 70s | ~37s |
| `/api/chat` | 45s | 40s | ~10s |

規則：frontend = backend + 5s buffer。5s 給 fastapi 層 overhead + TCP。

### Invariant（P3.10 後不可違反）

1. **Frontend timeoutMs > Backend total_timeout_s**（至少 5s buffer）。違反會讓前端 abort 後後端還在跑，燒 Gemini quota。
2. **Service 層失敗一律 raise，不吞錯回 fallback dict**。所有 mock fallback 只能在 route 層 `try/except` 後 + `_fallback:true` flag。Service 層 silent degradation 會讓 route 當成成功，frontend 收到「像真的」假資料。
3. **Retry 判斷 type-based，不用字串 substring**。`genai_errors.ServerError` / `ClientError.code==429` / `httpx.NetworkError` / `ConnectionError`。asyncio.TimeoutError 表示 budget 用完，不 retry。

### Codex R3 結案點

- Issue 1 修對：`generate_swot` 不再 silent fallback，失敗走完整 ErrorVM 鏈
- Issue 2 修對：`/api/analyze` route-level budget 實作，worst case 85s，frontend 90s
- Scraper 30s 可接受（過去最大案例 151 評論 8 頁 ~16s，Serper hiccup 是 operational risk）
- LLM_FLOOR=10s 合理
- `analyze_content(total_timeout_s=55)` 預設無衝突（route 永遠會傳動態 budget）

### 實測（R3 closed 前）

| Smoke | Status | Elapsed | isFallback | 備註 |
|-------|--------|--------:|-----------:|------|
| POST /api/weekly-plan | 200 | 69.7s | false | budget 115s，margin 40% |
| POST /api/training-script | 200 | 47.8s | false | budget 105s，margin 55% |
| POST /api/internal-email | 200 | 37.3s | false | budget 70s，margin 47% |
| POST /api/swot（happy） | 200 | 29.6s | false | budget 55s |
| POST /api/analyze（真 Google Maps URL） | 200 | 52.0s | false | route budget 85s，57 reviews |

Task #91–#94 完結。

---

## P3.11 Prompt 純文字結構結案（2026-04-23）— 六輪雙 AI 共識結案

### 觸發原因

P3.10 結案後審 prompt 發現 root_cause / weekly-plan / training-script / internal-email 還在輸出 markdown（##/**），但 v4 UI 早就改用 `<pre>` 純文字直出，造成顯示時 ## 變成字面字元。確立第 4 條 invariant：**prompt skeleton 必須對齊前端 renderer**。

### 修補（六輪 Codex peer review）

- `llm_service.py` root_cause / weekly-plan / training-script / internal-email 的 prompt skeleton 全改成「【主題】+ ◆ 範疇 + 　▸ bullet」純文字結構，明確禁 markdown
- `outputs/test_reducer.mjs` 從 15 case 擴到 48 case：加 case 8/9/10 stale check + 補強 case 11 改 stub EventSource capture instance/listener，11a 真打 onerror、11b/11c 真打 failed/result event，鎖死 adapter terminal action 三條路徑都帶 `runId+requestId`；Round-4 再加 case 11d/11e（malformed terminal JSON → STREAM_CONNECTION_LOST，不可 silent close）+ case 11f（openSSE 沒帶 opts.requestId → errorVM.requestId === null，runId 絕不冒充）；**Round-5 再補 11d/11e 內層 `errorVM.requestId` 兩條斷言**，鎖 api.js malformed 分支 `Err.network(..., requestId ?? null)` 不被改塞 runId（外層 action.requestId 由 adapter 從 closure 塞會誤綠，必須鎖內層）
- `core/api.js` `openSSE` opts 加 `requestId`（Codex round-3 抓包：原本只傳 `runId` 導致 `errorVM.requestId` 實際是 `runId`，違反診斷語意）；`core/adapters.js` runAnalyzeStream 三層全帶 `requestId`；Round-4 把 `requestId ?? runId` 改成 `requestId ?? null`、result/failed listener 改成 parse 失敗走 onConnectionError 並 close（不 silent close）
- `docs/v4-api-contract.md` §2.5/2.7/2.8/2.9 把「Markdown 文字」改寫成「純文字結構（用【】◆　▸ 排版，前端 `<pre>` 直出）」
- `docs/v4-sse-events.md` 路由 `/api/analyze-stream` → `/api/v4/analyze-stream`、狀態從「P0 草稿」改 P3.11 鎖定
- `docs/v4-view-model.md` 工具鏈描述移除 marked.js / `src/static/index.html` 舊路徑、改寫成 React 18 UMD + `<pre>` 純文字直出

### 六輪 Codex 雙 AI 結案紀錄

- **Round 1**：找到 5 條（CODEX-1/3/4 立修，CODEX-2/5 P4 延後）
- **Round 2**：找到 4 條（ROUND-2-1/2/3/4 全立修；ROUND-2-1 真回歸點 — sed 拿掉 adapters.js:107 requestId 證明 11a 確實會紅）
- **Round 3**：找到 4 條（ROUND-3-1/2/3/4 全立修；ROUND-3-3 是真 code bug，errorVM 內部 requestId 對齊修補）
- **Round 4**：找到 5 條（ROUND-4-1/2/3 文件收斂；ROUND-4-4 真 code bug — `requestId ?? runId` fallback 把 runId 偽裝成 requestId 偷塞 ErrorVM；ROUND-4-5 真 code bug — result/failed listener 先設 terminalReceived 再 safeParse，malformed JSON 會 silent close 害 features.analyze 永卡 loading）
- **Round 5**：找到 3 條收斂類（HANDOFF.md / docs/v4-smoke-test.md 文件殘留 + test_reducer 11d/11e 沒 assert errorVM.requestId 鎖點不夠）
- **Round 6**：找到 2 條收斂類（HANDOFF.md:423 寫 46 case 沒同步成 48 + line 218 仍提 `outputs/smoke_features_p2.mjs` / tinyMarkdown 但檔已不存在）→ 全收斂後 Round-7 結案
- **P4 backlog**：rootCause 在 v4 UI 沒 tab（B1/CODEX-2）、`mock_responses.py` 還有 markdown（CODEX-5；理由：legacy `/legacy` consumer 仍 fetch `/api/analyze-issue` 並 marked.parse，但 legacy 低流量待退場）

### 鎖定 4 條 invariant

1. frontend `timeoutMs` ≥ backend `total_timeout_s` + 5s buffer
2. service 失敗一律 raise，不回 fallback dict（避免 silent degradation）
3. retry 走 type-based（`genai_errors.ServerError` / `429` / `httpx.NetworkError`），不靠字串比對
4. **prompt skeleton 對齊 UI renderer**：v4 `<pre>` 直出 → 不可有 markdown，要用【】◆　▸ 排版

### 驗證

| 項目 | 結果 |
|------|------|
| `node validate_jsx.cjs` | OK · lines: 3438（P3.12-R2 後端不 cap 照抓全部 + 前端 §04 slice 50 + 「全部」改「精選」+ 三段 caption） |
| `node outputs/test_reducer.mjs` | 48 pass / 0 fail（含 11a errorVM.requestId 對齊、11d/11e malformed→connection lost + errorVM.requestId 對齊、11f 無 opts.requestId → null） |
| `python3 -m py_compile src/services/llm_service.py` | OK |
| 模擬 regression A（api.js `requestId ?? null` 改回 `?? runId`） | 11f 紅 2、還原後綠 |
| 模擬 regression B（result/failed malformed 處理整段刪掉） | 11d/11e 紅 7、還原後綠 |
| 模擬 regression C（adapters.js:107 拔 dispatch action requestId） | case 9 split state + 11a 真回歸點紅、還原後綠 |
| 模擬 regression D（adapters.js openSSE opts 拔 requestId） | 11a errorVM.requestId 對齊紅、還原後綠 |
| 殘留掃描 | llm_service `**` 只剩 `2 ** (attempt-1)` Python power、`##` 只剩 prompt 警告字串、markdown 提及都是 prompt 禁令；docs/v4-smoke-test.md 已無「AI Markdown」字句 |

---

## P3.12 評論抓取「呈現面 cap」UI 收斂（2026-04-23 R1 → R2 重做）

### 動機 + Round 1 誤判
使用者觀察：某店 Google Maps 顯示 57 則評論，UI §04「全部 30」讓店家以為「分析不完整」。

R1 我誤把問題當作「後端少抓了」→ 後端加 `MAX_REVIEWS_TARGET = 50` cap + 前端 caption 顯示「分析 50 則 · Google Maps 共 X 則」。R2 使用者澄清：

> 一樣抓取所有評論！我只是對【04】的 UI 有意見。考量到如果有些店家上千則評論那個 UI 會炸掉，也確實不應該顯示全部，你補充說明：其中的一些評論（上限設 50）。照樣抓所有的 google 評論，只是 04 UI 那邊有問題。

### R2 正解
**LLM 該看到全部評論，UI 才需要顯示限制**：

- 後端 `src/services/scraper_service.py` 撤掉 R1 的 4 處 cap（line 432 / 463 / 488 / 496），保留註解說明「顯示限制改在前端控制」。回傳 `total_reviews: rating_count` 維持，給前端 honest 顯示用。
- 前端 `src/static/v2/index.html` ReviewsSection（line 2436+）：
  - `MAX_REVIEWS_DISPLAY = 50` 常數
  - `displayed = reviews.slice(0, MAX_REVIEWS_DISPLAY)` 顯示限制
  - `truncated = reviews.length > 50` 判斷是否裁切
  - 篩選按鈕「全部」**改成「精選」**（truncated 時）— 讓店家知道這不是真正全部，避免「分析不完整」誤解
  - 4 個 sentiment count 全部用 `displayed`（顯示什麼就統計什麼，按鈕數和按下去看到的數一致）
  - Caption 三段（filter 而成）：
    - **第一句**：「本次分析了 N 則含文字評論」（或 YouTube 留言）— 反映 LLM 看到的真實數
    - **第二句**：truncated 才顯示「下方顯示其中 50 則樣本（避免列表過長）」— 補充為什麼按鈕只有 50
    - **第三句**：店家 + totalReviews > reviews.length 才顯示「Google Maps 共 M 則評分（含未寫文字者）」— 對齊店家 Google Maps 認知

### 鎖定的設計原則（第 5 條 invariant）
**⑤ 抓取邏輯（後端）和呈現限制（前端）要分離；UI 顯示限制必須有 honest 文案說明**
- 後端：抓所有可抓的（max_pages 安全上限），完整餵給 LLM
- 前端：UI 限制顯示量（`MAX_REVIEWS_DISPLAY = 50`，避免上千則炸畫面）
- UI 文案：truncated 時「全部」必須改「精選」/「樣本」，並補一句「畫面顯示其中 N 則」說明
- Why：店家最在意「我所有評論都被分析了嗎」，後端 cap 會直接讓他覺得「漏分析」；UI cap 是合理的，但要 honest 告知
- How to apply：未來任何「列表 + 篩選 + 數字」UI 都同此規則（comments / search hits / 搜尋結果）— 如果有 slice 顯示限制，就要有對應的 caption 說明

### 驗證
- `node validate_jsx.cjs` → `OK · lines: 3438`（+47 行：caption 三段化 + truncated 判斷 + 改 displayed 為基底）
- `node outputs/test_reducer.mjs` → 48 pass / 0 fail（reducer 不受影響）
- `python3 -m py_compile src/services/scraper_service.py` → OK
- 後端 grep：`MAX_REVIEWS_TARGET` 已不存在（只剩註解說明）；line 544 仍回 `total_reviews`
- 前端 grep：line 2436 `MAX_REVIEWS_DISPLAY`、line 2441 slice、line 2445 truncated、line 2463 「全部 / 精選」條件式

### 待真 E2E 驗證（uvicorn + 真 SERPER key）
- §3 §4：某店 ratingCount > 50 → 按鈕「精選 50」+ caption「本次分析了 X 則 · 下方顯示其中 50 則樣本 · Google Maps 共 Y 則評分（含未寫文字者）」
- §3 §4：某店 ratingCount ≤ 30 → 按鈕「全部 N」（N = reviews.length）+ caption 只剩第一句「本次分析了 N 則含文字評論」
