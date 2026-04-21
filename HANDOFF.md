# InsightX 專案交接文件

> 最後更新：2026-04-21（v3.0.0 — 蝦皮模組評估後放棄，回到 2 模式）
> 適用對象：下一個接手的 AI agent 或開發者

---

## 專案概述

InsightX 是一個 AI 驅動的評論 / 留言分析平台，**v3.0.0 支援 2 個模式**：

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
│       ├── index.html           # 主分析介面（純 HTML + Tailwind CDN + inline JS）
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

**前端架構重要提醒**：`src/static/index.html` 是 1500+ 行純 HTML + Tailwind CDN + inline JS 的主分析介面，**不是**由 `App.tsx` 編出來的——後者是獨立小遊戲。修改主 UI 直接改 `index.html`。

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
- `src/static/index.html` — 主分析介面（非 App.tsx）

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
