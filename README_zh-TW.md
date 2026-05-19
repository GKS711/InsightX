<div align="center">

# 🔍 InsightX

**把顧客評論——不論是 Google Maps 店家，還是 YouTube 影片——變成 AI 驅動的商業策略**

[![Live demo](https://img.shields.io/badge/live--demo-Jordan711--insightx__demo.hf.space-FF9D00.svg)](https://Jordan711-insightx-demo.hf.space)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+sync-D71F00.svg)](https://www.sqlalchemy.org/)
[![Turso](https://img.shields.io/badge/DB-Turso%20libsql-4FF8D2.svg)](https://turso.tech/)
[![HF Spaces](https://img.shields.io/badge/deploy-HF%20Spaces-FFD21E.svg?logo=huggingface)](https://huggingface.co/spaces/Jordan711/insightx_demo)
[![Version](https://img.shields.io/badge/version-6.0.0--alpha-E25A45.svg)](#更新紀錄)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**語言：** [🇺🇸 English](README.md) | 🇹🇼 繁體中文

</div>

---

## 這是什麼？

InsightX 接受 **Google Maps 店家網址**或 **YouTube 影片網址**，透過官方 API 抓取顧客評論／觀眾留言，然後用 [Google Gemini](https://ai.google.dev/) 生成一份完整的雜誌風報告：情感分析、主題拆解、原文佐證、SWOT、回覆草稿、週行動計畫、培訓劇本、內部信，還有可即時對話的 AI 顧問。

**雙模式運作**，共用同一組 9 個下游 AI 功能：

| 模式 | 來源 | 爬蟲 | 適用對象 |
|------|------|------|---------|
| 🏪 **店家評論** | Google Maps 網址 | [Serper API](https://serper.dev/)（`/maps` + `/reviews`） | 餐廳、零售、服務業 |
| 🎬 **YouTube 留言** | YouTube 影片網址 | [YouTube Data API v3](https://developers.google.com/youtube/v3)（+ `youtube-comment-downloader` 備用） | 創作者、頻道成長、內容調校 |

**零瀏覽器、零 headless Chrome** — 全程 HTTP API。沒有 Playwright，沒有 Selenium。

<div align="center">

### 🚀 線上 demo

# [Jordan711-insightx-demo.hf.space →](https://Jordan711-insightx-demo.hf.space)

*Hugging Face Spaces · Turso (libsql) · Gemini · Serper*

</div>

---

## 實際樣子長這樣

> 截圖是 v4 UI（`src/static/v2/`）。v6 視覺設計延用 v4，唯一不同是 hero 插畫換成 Codex img2 生成的編輯級插圖。

### 1 · 落地頁 — 選你要分析的來源
![落地頁](docs/screenshots/v4/01-landing.png)
雜誌風 hero，配上新的「universal listening post」插圖。一個標題、一個 CTA，沒有多餘介面。

### 2 · 兩種來源、一鍵分析
![平台選擇](docs/screenshots/v4/02-platforms.png)
店家就選 **Google 評論**，創作者就選 **YouTube 留言**。兩條 pipeline 分開跑，挑一個按下去就分析。

### 3 · 即時分析進度
![分析中](docs/screenshots/v4/03-analyzing.png)
Server-Sent Events 串流真實進度 (`ANALYZING 5/6 · 生成報告`) — 不是假的 loading 動畫。

### 4 · Dashboard Hero — 一眼看完核心指標
![Hero](docs/screenshots/v4/04-hero.png)
店名、評分含 90 天趨勢線、情感分布、加上一句「下一步看哪裡」導引。

### 5 · §02 顧客真正在乎什麼
![主題](docs/screenshots/v4/05-themes.png)
正面前 3 主題 + 負面前 3 主題，附真實百分比。

### 6 · §03 SWOT — 策略姿態，有評論佐證
![SWOT](docs/screenshots/v4/06-swot.png)
每個結論標 `evidence-backed`，標出觸發它的評論佔比。

### 7 · §04 原文——永遠不脫離 source
![評論](docs/screenshots/v4/07-reviews.png)
最多 50 則原始評論（含星等；YouTube 改顯示 `♥ N` 讚數），按情感篩選。

### 8 · §07 工具箱 — 本週就能動手
![週計畫](docs/screenshots/v4/08-week-plan.png)
工具箱整合 5 個 LLM 生成器：回覆草稿、行銷文案、**週行動計畫**、員工培訓劇本、內部團隊信。

### 9 · §07 回覆草稿 — 對症下藥
![回覆](docs/screenshots/v4/09-replies.png)
左邊挑一個負面主題，右邊就有完整回覆草稿，附自我批判（「為什麼這樣寫」「要避開的寫法」）。

### 10 · §AI 顧問 — 跟一個讀完全部評論的顧問對話
![AI 顧問](docs/screenshots/v4/10-ai-advisor.png)
店家有什麼問題都能問。顧問只看你的資料 — 不是通用 ChatGPT。

---

## 快速啟動

### 選項 A · 線上 demo（最快體驗）

<https://Jordan711-insightx-demo.hf.space> — 不用裝、不用註冊。貼一個 Google Maps 網址到「Google 評論」卡片，按開始分析就好。

### 選項 B · 本機開發

```bash
# Clone
git clone https://github.com/GKS711/InsightX.git
cd InsightX

# 環境變數
cp .env.example .env
# 編輯 .env：GEMINI_API_KEY、SERPER_API_KEY，可選 YOUTUBE_API_KEY
# DATABASE_URL 留空就用本機 SQLite

# Python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 資料表
alembic upgrade head

# 跑
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

打開 <http://localhost:8000>。前端在 `src/static/v2/`（Babel-standalone React，不用 build）。工作區在 `/workspace/`。API 文件在 `/docs`。

### 選項 C · 自架到 Hugging Face Spaces + Turso

完整 step-by-step：**[`docs/DEPLOY_HF.md`](docs/DEPLOY_HF.md)**。重點：

1. `turso db create insightx-demo --location nrt`（東京）
2. 建 HF Space（Docker SDK、CPU basic free）
3. 設 5 個 secrets
4. `git push` 到 Space repo
5. 第一次 build ~3 分鐘，之後 rebuild ~30 秒

跑在 Gemini 1500 req/day 免費 + Serper 免費 credits 範圍內；HF Spaces Free + Turso Starter Free 提供 hosting + DB。

---

## 你會看到什麼

| 區段 | 內容 |
|------|------|
| §01 Hero | 店名 / 影片名、地址、評分 / 讚數、情緒甜甜圈 |
| §02 主題 | 正面 + 負面前幾大主題附原文 |
| §03 SWOT | 策略姿態（優勢 / 劣勢 / 機會 / 威脅） |
| §04 原文 | 最多 50 則原評論，按情緒上色 |
| §05 週行動計畫 | 7 天具體待辦 |
| §06 行銷 | IG/FB 風文案 |
| §07 工具 | 回覆草稿、根源深挖、培訓劇本、內部團隊信 |
| §08 AI 顧問 | 知道你資料的 AI 顧問 |
| `/workspace/` | 持久多店工作區（v5/v6，需 Turso DB + bridge env flag） |

---

## 怎麼運作的

```
   Google Maps 網址  ───┐
                        ├─▶ 偵測平台 ─▶ 爬蟲 ─▶ Gemini 分析 ─▶ SSE 串流 ─▶ Dashboard
   YouTube 影片網址 ────┘                  │                            │
                                            │                            │
                                  ┌─────────┴──────────────┐             │
                                  │ Serper /maps + /reviews│             ▼
                                  │ YouTube Data API v3    │   IX_ENABLE_V4_WORKSPACE_PERSIST=1
                                  │  (+ library fallback)  │   ─▶ Turso 寫入 + /workspace/
                                  └────────────────────────┘
```

**v6 stack**：FastAPI (sync) + SQLAlchemy 2.0 (sync) + alembic + `sqlalchemy-libsql` + threading.Thread workers + Babel-standalone React。完整架構圖見 [`HANDOFF.md`](HANDOFF.md)。

---

## API 參考

兩個 API 表面：

### v4（stateless 分析 — landing 頁用）

| 方法 | 端點 | 說明 |
|------|------|------|
| `GET` | `/api/meta` | App 元資料 |
| `GET` | `/api/v4/analyze-stream?url=...` | **推薦**。結構化 SSE |
| `POST` | `/api/analyze` | 非 SSE fallback |
| `POST` | `/api/swot`, `/api/reply`, ... 8 個 | 平台感知 LLM 功能端點 |

### v5/v6（持久工作區 — `/workspace/` 用）

| 方法 | 端點 | 說明 |
|------|------|------|
| `POST` `GET` | `/api/v5/workspaces` | 工作區 CRUD |
| `POST` `GET` `DELETE` | `/api/v5/stores`, `/api/v5/stores/{id}` | 店家 CRUD + cascade-delete |
| `POST` | `/api/v5/stores/{id}/scrape`, `/api/v5/stores/{id}/analyze` | 觸發 background job |
| `GET` | `/api/v5/jobs/{id}/stream`, `/api/v5/runs/{id}/stream` | SSE 進度串流 |
| `POST` `GET` `GET` | `/api/v5/stores/{id}/reports`, `/api/v5/reports/{id}`, `/api/v5/reports/{id}/download` | 報告 PDF / DOCX |

---

## 不可違反的不變量（5 條）

1. **Frontend `timeoutMs` ≥ Backend `total_timeout_s` + 5s buffer**
2. **Service 層失敗一律 raise**（不回 fallback dict）
3. **Retry 用 exception type 判斷**，絕不字串比對
4. **Prompt skeleton 對齊 `<pre>` renderer**（不可有 markdown，用 `【】 ◆　▸` 純文字結構）
5. **後端不 cap 爬蟲，前端 UI 才 cap 顯示**（`MAX_REVIEWS_DISPLAY = 50` + 誠實 caption）

完整理由 + 歷史 bug fix：[`HANDOFF.md`](HANDOFF.md)。

---

## 雙平台 — schema 借用注意

| 欄位 | Google 模式 | YouTube 模式 |
|------|------------|-------------|
| `raw.store_name` | 店名 | 影片標題 |
| `raw.review_count` | 抓到的有文字評論數 | 抓到的留言數 |
| `raw.rating` | 1–5 星評分 | 影片讚數 |
| `raw.rating_count` | Google Maps 評分總數 | 觀看數 |
| `raw.address` / `category` | 真值 | 空字串 / "YouTube 影片" |
| `raw.reviews_structured[].rating` | 1–5 星 | 留言讚數 |

---

## 環境變數

| 變數 | 必要 | 說明 |
|------|------|------|
| `GEMINI_API_KEY` | **是** | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| `SERPER_API_KEY` | 店家模式必填 | [serper.dev](https://serper.dev/) |
| `YOUTUBE_API_KEY` | YouTube 模式建議 | [console.cloud.google.com](https://console.cloud.google.com) → 啟用 YouTube Data API v3 |
| `YOUTUBE_FALLBACK_MODE` | 否 | `auto` / `force-ytdlp` / `off` |
| `DATABASE_URL` | 生產環境 | Turso libsql URL；本機預設 `sqlite:///./insightx.db` |
| `TURSO_AUTH_TOKEN` | 生產搭配 Turso | JWT |
| `IX_ENABLE_V4_WORKSPACE_PERSIST` | 否 | self-hosted 單使用者設 `=1`。**公開 demo 請保持未設** |
| `ENVIRONMENT` | 否 | `development` / `production` |

---

## 測試 & 驗證

```bash
# 前端 JSX
node validate_jsx.cjs

# Reducer + adapter（48 cases）
node outputs/test_reducer.mjs

# Python 語法
python3 -m py_compile src/services/*.py src/api/*.py src/main.py

# 線上 deploy
SPACE=https://Jordan711-insightx-demo.hf.space
curl -s $SPACE/api/meta | jq .appVersion       # → "6.0.0-alpha"
```

手動 E2E：見 [`docs/v4-smoke-test.md`](docs/v4-smoke-test.md)。

---

## 開發

```bash
python -m uvicorn src.main:app --reload --port 8000
```

v4 UI 是 **single-file** + Babel standalone，前端編輯瀏覽器硬重整就生效。

---

## 更新紀錄

完整版本歷史見 [`CHANGELOG.md`](CHANGELOG.md)。亮點：

- **v6.0.0-alpha（2026-05-19）** — 全 sync 重寫以相容 Turso/libsql。多 model LLM fallback chain。Codex img2 雜誌封面 hero。HF Spaces 單階段 Dockerfile。v4→v5 工作區 bridge（env-gated）。8 輪 Codex peer review。
- **v5.0.0（2026-05-19）** — 持久多店工作區。9-table v5 schema。async SQLAlchemy 2.0 ORM。Store 刪除含 cascade integrity。
- **v4.0.0（2026-04-23）** — Single-file React 18 + `@babel/standalone` SPA。結構化 `/api/v4/analyze-stream` SSE。9 個 platform-aware LLM endpoint。48-case reducer 回歸測試。
- **v3.0.0** — 整併到 Google Maps + YouTube。蝦皮模組正式放棄。
- **v2.0.0** — YouTube 頻道模式，雙路徑留言爬蟲。
- **v1.x** — 初版 Google Maps 分析器。

---

## License

MIT — 見 [LICENSE](LICENSE)。

---

## 鳴謝

[Google Gemini](https://ai.google.dev/) · [Serper API](https://serper.dev/) · [YouTube Data API v3](https://developers.google.com/youtube/v3) · [youtube-comment-downloader](https://pypi.org/project/youtube-comment-downloader/) · [FastAPI](https://fastapi.tiangolo.com/) · [SQLAlchemy](https://www.sqlalchemy.org/) · [Turso](https://turso.tech/) · [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces) · [React](https://react.dev/) · [@babel/standalone](https://babeljs.io/docs/babel-standalone)
