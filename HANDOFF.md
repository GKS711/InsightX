# InsightX 專案交接文件

> 最後更新：2026-04-17（v2.0.0 新增 YouTube 頻道模式）
> 適用對象：下一個接手的 AI agent 或開發者

---

## 專案概述

InsightX 是一個 AI 驅動的評論 / 留言分析平台。**v2.0.0 起支援雙模式**：

1. **店家評論模式**（v1.x 原有，穩定）：Google Maps 店家網址 → Serper 爬評論 → Gemini 生成餐飲／零售向報告
2. **YouTube 頻道模式**（v2.0.0 新增，目標客群是 YouTuber）：單支 YouTube 影片網址 → YouTube Data API 抓留言 → Gemini 生成頻道創作者向報告

兩模式共享 9 個下游 AI 功能（SWOT、回覆、行銷、根源分析、週計畫、培訓劇本、內部信、對話顧問），但每個功能依 `platform` 參數切換 prompt persona。

---

## 架構

```
InsightX/
├── src/
│   ├── main.py                  # FastAPI 入口，掛載路由 + 靜態檔
│   ├── api/routes.py            # 所有 API endpoints（共 11 個，全部支援 platform="google"|"youtube"）
│   ├── services/
│   │   ├── scraper_service.py   # 統一入口；依 URL dispatch 到 Google Maps / YouTube
│   │   ├── youtube_scraper.py   # (v2.0.0) YouTube Data API v3 留言爬蟲
│   │   └── llm_service.py       # Gemini AI 呼叫（9 個方法，全部支援 platform 分支）
│   ├── config/
│   │   ├── prompts.py           # 所有 AI prompt 模板
│   │   └── mock_responses.py    # Gemini 失敗時的 fallback 回應
│   └── static/
│       ├── index.html           # 主分析介面（v2.0.0 加了 Tab 切換）
│       ├── App.tsx              # 決策模擬小遊戲（與主分析無關）
│       └── insightx_game.html   # 互動小遊戲
├── CLAUDE.md                    # 技術架構完整說明（必讀）
├── ISSUES_RESOLVED.md           # 爬蟲歷史問題與解法
├── RESEARCH_google_maps_scraping.md  # 爬蟲研究筆記
├── 自動化規則.md                # 開發時的自動化規則
├── pyproject.toml / requirements.txt # Python 依賴
└── package.json                 # 前端依賴
```

**前端架構重要提醒**：`src/static/index.html` 是 1600+ 行純 HTML + Tailwind CDN + inline JS 的主分析介面，**不是**由 `App.tsx` 編出來的——後者是獨立小遊戲。修改主 UI 直接改 `index.html`。

---

## 目前狀態（v2.0.0）

### 已完成並確認穩定（v1.x 基底，不要動）
- **評論爬蟲 v13.1**：純 Serper API，無瀏覽器依賴，支援分頁
  - 驗證：全家濱海店 151 則，86 則有文字，8 頁分頁 ✅
- **後端 API**：11 個 endpoints（v1 時期全部可用）
- **GitHub**：tag `v1.0.0` 已推上 `GKS711/InsightX`

### v2.0.0 新增（程式碼完成，待端對端驗證）
- **`src/services/youtube_scraper.py`**（新檔）：YouTube Data API v3 留言爬蟲
  - URL 解析：`watch?v=`、`youtu.be/`、`/shorts/`、`/embed/`
  - `commentThreads.list` 分頁、`order="relevance"`、每頁 100 則
  - 回傳 shape 對齊 Google Maps scraper（`store_name`=影片標題、`rating`=like_count、`rating_count`=view_count、`platform="youtube"`）
- **`scraper_service.py`**：加入 `is_youtube_url()` dispatch；URL 為 YouTube 時直接走 YouTubeScraper
- **`llm_service.py`**：9 個方法全部加 `platform: str = "google"` 參數，內部 if/else 分支切換 YouTuber 版 / 餐廳版 prompt
- **`routes.py`**：
  - 7 個 request model 加 `platform` 欄位
  - 新增 `MOCK_ANALYSIS_YOUTUBE` fallback
  - `/analyze` 自動以 URL 偵測平台，並以爬蟲回傳的 platform 為準覆蓋
  - 7 個下游 endpoint 把 `request.platform` 傳下去給 LLM
  - `/analyze-stream` SSE log 文案依平台切換（留言/評論、影片/店家、YouTube Data API/Serper API）
- **`src/static/index.html`**：首頁加 Tab 切換「店家評論 / YouTube 頻道」
  - `currentPlatform` state、`MODE_CONFIG` 文案表、`applyModeUI()` 切換 UI
  - 所有 fetch 呼叫都帶 `platform`
- **`.env.example`**：加 `YOUTUBE_API_KEY` 欄位與申請指引

### 尚未驗證
- **端對端整合測試**：需要使用者在 `.env` 填上 `YOUTUBE_API_KEY`，然後貼一支 YouTube 影片到前端 Tab 跑完整流程。Python `py_compile` + JS 語法已過。

### 尚未開始
- v2.0.0 commit + tag（等測試通過後打）
- `pyproject.toml` / `package.json` 版本號改 2.0.0

---

## 優先任務

1. **（最高）請使用者在 `.env` 填上 `YOUTUBE_API_KEY`**
   - 申請：https://console.cloud.google.com/apis/library/youtube.googleapis.com → 啟用 API → 建立 API Key
   - 免費額度 10,000 units/day，單支影片約 3–10 units

2. **端對端整合測試**
   - 啟動後端：`source .venv/bin/activate && uvicorn src.main:app --reload`
   - 開 http://localhost:8000，點「YouTube 頻道」Tab，貼一支有留言的 YouTube 影片（建議 100+ 留言）
   - 驗證：`/api/analyze` 成功回傳情緒與主題 → SWOT、回覆、行銷等 9 個按鈕都能點，輸出文字帶有 YouTuber 口吻（「觀眾」、「影片」、「剪輯師」、「訂閱」等）
   - 也回頭測一次 Google Maps 模式，確認沒回歸破壞

3. **版本號打到 v2.0.0**
   - `pyproject.toml` 的 `version`
   - `package.json` 的 `version`
   - `git commit -m "feat: v2.0.0 — add YouTube channel mode"` + `git tag v2.0.0` + `git push --tags`

---

## 開發規則（重要）

- **測試爬蟲只用全家便利商店**（固定測試對象，避免浪費 API quota）
- **不開瀏覽器視窗**（爬蟲全程無頭，不需要 Playwright 或 Chrome）
- **問題記錄到 md 檔**（解決的問題記到 `ISSUES_RESOLVED.md`）
- **Serper API 是唯一爬蟲方案**，以下方法已確認無效不要再試：
  - Google Maps 內部 API（需登入 cookies）
  - headless Chrome / Playwright（被 Google 偵測）
  - Direct HTTP requests（短網址 JS redirect 無法跟隨）

---

## 環境設定

| 變數 | 必要 | 說明 |
|------|------|------|
| `GEMINI_API_KEY` | 是 | Google Gemini API Key |
| `SERPER_API_KEY` | 店家模式必填 | Serper API（店家評論爬蟲） |
| `YOUTUBE_API_KEY` | 建議 | YouTube Data API v3 Key；未設定會自動走 youtube-comment-downloader 備用 |
| `YOUTUBE_FALLBACK_MODE` | 否 | `auto`（預設）／`force-ytdlp`（強制走備用 library，值保留舊名以相容）／`off`（關 fallback） |
| `ENVIRONMENT` | 否 | `development` 或 `production` |

---

## 啟動指令

| 任務 | 指令 |
|------|------|
| 啟動後端 | `cd /Users/gankaisheng/VScode/Claude實作/InsightX && source .venv/bin/activate && uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload` |
| 啟動前端開發模式 | `npm run dev` |
| 打包前端 | `npm run build` |
| 測試爬蟲（全家） | `python test_reviews_standalone.py` |

> venv 路徑：`/Users/gankaisheng/VScode/Claude實作/InsightX/.venv/`

---

## 驗證清單（接手後先確認）

- [ ] `.env` 包含 `GEMINI_API_KEY`、`SERPER_API_KEY`、`YOUTUBE_API_KEY`
- [ ] `uvicorn` 啟動無報錯，`http://localhost:8000` 可訪問
- [ ] **店家模式**：用全家便利商店 Google Maps 網址，前端可觸發 `/api/analyze` 並取得評論（v1.x 回歸測試）
- [ ] **YouTube 模式**（v2.0.0 新）：點首頁「YouTube 頻道」Tab，貼一支 YouTube 影片網址
  - [ ] `/api/analyze` 成功回傳情緒與主題
  - [ ] 報告標題顯示「觀眾留言」而非「顧客評論」
  - [ ] SWOT、回覆、行銷文案、週計畫、培訓劇本、內部信 6 個功能都能點出結果
  - [ ] AI 對話顧問回應帶 YouTuber 口吻（出現「觀眾」「影片」「訂閱」等字眼）
- [ ] 無 `YOUTUBE_API_KEY` 時，YouTube 模式應回傳可讀的錯誤訊息（不爆 500）

---

## 重要檔案指引

- `CLAUDE.md` — 完整技術架構，接手必讀
- `src/services/scraper_service.py` — 統一 URL dispatch（Google Maps / YouTube）
- `src/services/youtube_scraper.py` — (v2.0.0) YouTube Data API 留言爬蟲
- `src/services/llm_service.py` — 所有 Gemini AI 功能，9 個方法全部支援 `platform` 分支
- `src/config/prompts.py` — Google 模式的 prompt 模板（YouTube 模式目前直接 inline 在 llm_service.py 裡）
- `src/api/routes.py` — 新增 API endpoint 從這裡加；所有 request model 都有 `platform: str = "google"`
- `src/static/index.html` — 主分析介面（非 App.tsx）；v2.0.0 的 Tab 切換、`MODE_CONFIG`、`applyModeUI()` 都在這裡
- `ISSUES_RESOLVED.md` — 爬蟲踩過的坑，避免重蹈覆轍

---

## 使用者偏好與習慣

> 此區塊從 memory 系統同步。
> 這裡記錄的是 GKS 親口教給 AI 的規則，比任何文件都重要。

### 溝通方式
- **一律用繁體中文**回答，不管問題用什麼語言
- 如果安裝了任何套件或工具，完成後要說明安裝了什麼、裝在哪裡
- 測試瀏覽器一律用 Chrome

### 開發規則（已確認的習慣）
- **測試爬蟲只用全家便利商店新竹富美二店**（https://maps.app.goo.gl/gd74DaVeN6DY1bps7）——固定測試對象，避免浪費 API quota
- **最終方案不能開瀏覽器視窗**，必須 headless——產品要給客戶用，不是 POC
- **問題記錄到 md 檔**：解決的問題記到 `ISSUES_RESOLVED.md`，研究筆記記到 `RESEARCH_google_maps_scraping.md`
- 遇到 API Error 不要從頭開始，讀 `自動化規則.md` 從中斷點繼續
- 方法失敗就自動嘗試下一個，不要停下來問
- 重視效率，不想浪費 token 重複研究同樣的問題

### 已試過且無效的方法（不要重蹈）
- **Google Maps 內部 API**（listentitiesreviews）：需要登入 cookies，匿名無法用
- **headless Chrome / Playwright**：Chrome 147 被 Google 偵測，頁面不含評論資料
- **Direct HTTP requests**：短網址 JS redirect 無法跟隨
- Desktop User-Agent：maps.app.goo.gl 回傳 200 + JS redirect，跟不到完整網址；要用 Mobile UA 才能拿到 302 redirect
- **YouTube 用 Serper**：Serper 沒有 YouTube 留言 endpoint（曾誤會跟 SerpApi 混淆）；v2.0.0 改用官方 YouTube Data API v3

---

## 給下一個 agent 的備註

- 使用者是 GKS，開發者身份
- 這個專案的爬蟲歷史很複雜，不要輕易改動 `scraper_service.py` 的核心架構，先讀 `ISSUES_RESOLVED.md` 和 `RESEARCH_google_maps_scraping.md`
- Memory 系統因 space ID 隔離，跨對話無法直接讀取；HANDOFF.md 的「使用者偏好與習慣」區塊就是 memory 的備份，每次交接時應更新此區塊
