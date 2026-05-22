<div align="center">

# 🔍 InsightX V2

**給管理者的 AI 顧客意見洞察平台 — 一個 URL 換一份完整報告**

[![Live demo](https://img.shields.io/badge/live--demo-Jordan711--insightx__demo.hf.space-FF9D00.svg)](https://Jordan711-insightx-demo.hf.space)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**語言:** [🇺🇸 English](README.md) | 🇹🇼 繁體中文

</div>

---

## 這是什麼?

貼一個 **Google Maps 店家網址**或 **YouTube 影片網址**。60 秒內,你會拿到一份完整的雜誌風報告:情緒摘要、主題、SWOT、回覆草稿、週行動計畫、行銷文案、培訓劇本,加上一位讀完你所有評論的 AI 顧問。還有一個讓新店長練手的決策模擬遊戲。

🌐 **線上 Demo**: <https://Jordan711-insightx-demo.hf.space>

---

## 為什麼做這個

顧客每天在 Google、YouTube、社群平台留評論,但這些評論很少真的變成決策。

- **太碎** — 意見散在 Google Maps、YouTube、IG、LINE 各處,沒人有時間全部讀完。
- **太多** — 50 則留言已經是負擔,500 則直接放棄。看得到「很多人說好吃」,看不到「冷氣太強客人不想久坐」這種細節。
- **回應壓力大** — 負評上線,店長被情緒帶著走,回覆要嘛太硬要嘛太軟,反而失去挽回客人的機會。
- **新店長沒練習場** — 剛升上來沒處理過危機,學費全部用真實客人賠。

InsightX 想把這四件事在一個下午解掉。

---

## 解決方案

把「讀評論 → 想策略 → 寫回覆 → 練手」串成同一條流水線:

- **跨平台抓料,不用開瀏覽器** — Google Maps 用 Serper API,YouTube 用官方 Data API。速度快、也不容易被反爬擋掉。
- **9 個 AI 功能共用一份資料** — 情緒、SWOT、回覆、行銷、根源分析、週計畫、培訓劇本、內部信、AI 顧問。依平台切換語氣 (餐廳 / 零售 / YouTuber)。
- **多店家工作區** — 每位使用者有自己的工作區,可以新增多個店家、保留完整歷史紀錄。
- **管理者決策模擬遊戲** — 把真實負評倒進小遊戲,AI 當你的虛擬顧問即時給回饋。

---

## 9 個 AI 功能

| # | 功能 | 用途 |
|---|---|---|
| 01 | 情緒分析 | 正負向 + 主題分布 |
| 02 | SWOT | 自動生成戰略矩陣 |
| 03 | 回覆草稿 | 每則負評一個對應草稿 |
| 04 | 行銷文案 | 門市活動 / 影片宣傳 |
| 05 | 根源分析 | 找出真正的痛點 |
| 06 | 週行動計畫 | 一週要做哪些具體事項 |
| 07 | 培訓劇本 | 員工 / 剪輯師訓練教材 |
| 08 | 內部信 | 門市 / 團隊週報 |
| 09 | AI 顧問 | 隨時可問的虛擬導師 |

---

## 管理者決策模擬

新任店長最痛的事 ── 第一次處理客訴。InsightX 內建一個小遊戲,讓你在**真實負評**上練手:

1. **AI 出題** — 把真實負評變成情境問句
2. **你選回應** — 從多個策略選一個你會做的
3. **AI 給回饋** — 評估你的選擇,給情商分數 + 建議

學費,不用拿真客人賠。

---

## 實際樣子長這樣

### 落地頁 — 選你要分析的來源
![落地頁](docs/screenshots/v4/01-landing.png)

### 兩種來源、一鍵分析
![平台選擇](docs/screenshots/v4/02-platforms.png)

### 即時分析進度
![分析中](docs/screenshots/v4/03-analyzing.png)

### Dashboard Hero — 一眼看完核心指標
![Hero](docs/screenshots/v4/04-hero.png)

### 顧客真正在乎什麼
![主題](docs/screenshots/v4/05-themes.png)

### SWOT — 策略姿態,有評論佐證
![SWOT](docs/screenshots/v4/06-swot.png)

### 原文 — 永遠不脫離 source
![評論](docs/screenshots/v4/07-reviews.png)

### 工具箱 — 本週就能動手
![週計畫](docs/screenshots/v4/08-week-plan.png)

### 回覆草稿 — 對症下藥
![回覆](docs/screenshots/v4/09-replies.png)

### AI 顧問 — 跟讀完全部評論的顧問對話
![AI 顧問](docs/screenshots/v4/10-ai-advisor.png)

---

## 3 個設計決定 (背後的考量)

### 多人也能安全使用
最初版本所有人共用一個帳號,任何人打開都看到別人的資料。現在每位訪客一進站,自動拿到一個身分 (用 cookie 記下來),所有資料綁在這身分上。沒有註冊、沒有密碼,但每個人的工作區完全分開。

### 不會因為 AI 抖一下就掛
免費版 Gemini 半夜常常會卡。我做了一個自動換模型的機制:主用快的,失敗就降到大的,再不行換 Google 的旗艦,最後 lite 版兜底。同一次請求一路 fallback,使用者完全感覺不到。

### 雙 AI 寫 code
改動比較大的時候,我習慣讓 Codex (另一個 AI 助手) 幫我看一遍程式碼。一個 AI 寫、另一個 AI 挑毛病。抓出來的問題比自己看更多 ── 等於多了一個免費的 reviewer。

---

## 技術棧

| 層 | 技術 |
|---|---|
| 後端 | FastAPI · Python 3.10+ |
| 資料庫 | Turso · SQLite (libsql) |
| AI | Google Gemini (多模型 fallback) |
| 爬蟲 | Serper API + YouTube Data API v3 |
| 前端 | React 18 + Tailwind CSS |
| 部署 | Docker on Hugging Face Spaces (免費方案) |

---

## 快速啟動

**最簡單** — 直接開 [線上 Demo](https://Jordan711-insightx-demo.hf.space)。不用裝、不用註冊。

**本機跑:**

```bash
git clone https://github.com/GKS711/InsightX.git
cd InsightX

# 環境變數
cp .env.example .env
# 填入 GEMINI_API_KEY、SERPER_API_KEY (YOUTUBE_API_KEY 可選)

# 依賴
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 資料表
alembic upgrade head

# 跑
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

打開 <http://localhost:8000>。

**自架到 Hugging Face Spaces + Turso** — 看 [`docs/DEPLOY_HF.md`](docs/DEPLOY_HF.md)。

---

## License

MIT — 見 [LICENSE](LICENSE)。

---

## 鳴謝

[Google Gemini](https://ai.google.dev/) · [Serper API](https://serper.dev/) · [YouTube Data API v3](https://developers.google.com/youtube/v3) · [FastAPI](https://fastapi.tiangolo.com/) · [SQLAlchemy](https://www.sqlalchemy.org/) · [Turso](https://turso.tech/) · [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces) · [React](https://react.dev/)
