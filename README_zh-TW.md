<div align="center">

# 🔍 InsightX

**AI 驅動的顧客回饋智能分析工具**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2+-61DAFB.svg?logo=react)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2+-3178C6.svg?logo=typescript)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**語言 / Language:** [🇺🇸 English](README.md) | 🇹🇼 繁體中文

[🌟 功能特色](#-功能特色) •
[📸 畫面展示](#-畫面展示) •
[🚀 快速開始](#-快速開始) •
[📖 更多文檔](#-專案結構)

</div>

---

## 📋 目錄

- [專案概述](#-專案概述)
- [功能特色](#-功能特色)
- [畫面展示](#-畫面展示)
- [環境需求](#-環境需求)
- [快速開始](#-快速開始)
  - [給使用者（生產環境）](#給使用者生產環境)
  - [給開發者（開發環境）](#給開發者開發環境)
- [專案結構](#-專案結構)
- [環境變數設定](#-環境變數設定)
- [API 文檔](#-api-文檔)
- [疑難排解](#-疑難排解)
- [貢獻指南](#-貢獻指南)
- [授權條款](#-授權條款)

---

## 🎯 專案概述

**InsightX** 是一款 AI 驅動的顧客回饋分析平台，能將散落在 Google 地圖、Facebook、LINE 的評論轉化為可執行的商業洞察。使用 Google Gemini 2.0，InsightX 為餐廳經營者提供：

- 📊 **跨平台綜合情緒分析**
- 🎯 **基於 SWOT 的策略建議**
- 💬 **AI 自動生成評論回覆模板**
- 📝 **基於顧客反饋的行銷文案**
- 🎮 **互動式決策模擬遊戲**訓練管理技能

---

## ✨ 功能特色

### 🔥 核心功能

- **多平台整合**：自動抓取並分析以下平台的評論：
  - 🗺️ Google 地圖
  - 📘 Facebook 粉絲專頁
  - 💚 LINE 官方帳號

- **AI 智能分析**：
  - 情緒分類（正面/負面/中性）
  - 關鍵痛點與亮點提取
  - SWOT 分析生成
  - 可執行的改善建議

- **經營者工具**：
  - 一鍵生成評論回覆
  - 社群媒體行銷內容創作
  - 數據驅動的決策支援

### 🎮 額外功能：店長決策模擬室

互動式培訓遊戲，包含：
- 10 個真實餐廳經營情境
- 顧客數據 vs 直覺判斷的對比
- AI 即時回饋決策結果
- 個人化改進建議

---

## 📸 畫面展示

### 主介面 - AI 分析儀表板

![首頁展示](docs/screenshots/hero-section.png)

*簡潔現代的 UI 設計，展示 AI 驅動的分析引擎*

---

### 輸入介面 - 多平台數據收集

![輸入區展示](docs/screenshots/input-section.png)

*簡單的 URL 輸入介面，支援 Google 地圖、Facebook 和 LINE 評論來源*

---

### 店長決策模擬室

<table>
  <tr>
    <td width="50%">
      <img src="docs/screenshots/game-start.png" alt="遊戲開始"/>
      <p align="center"><em>引人入勝的開始畫面設計</em></p>
    </td>
    <td width="50%">
      <img src="docs/screenshots/game-question.png" alt="遊戲題目"/>
      <p align="center"><em>搭配真實顧客數據的互動情境</em></p>
    </td>
  </tr>
</table>

---

## 📦 環境需求

開始之前，請確保已安裝以下工具：

| 工具              | 版本   | 用途                        |
| ----------------- | ------ | --------------------------- |
| **Python**        | 3.10+  | 後端執行環境                |
| **Node.js**       | 18+    | 前端建構工具                |
| **npm**           | 9+     | JavaScript 套件管理器       |
| **uv**            | 最新版 | Python 套件與虛擬環境管理器 |
| **Docker** (選用) | 最新版 | 容器化部署                  |

### 安裝 UV

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 🚀 快速開始

### 給使用者（生產環境）

#### 方法一：Docker Compose（推薦）

最快速啟動 InsightX 的方式：

```bash
# 1. 複製專案
git clone https://github.com/yourusername/InsightX.git
cd InsightX

# 2. 設定環境變數
cp .env.example .env
# 編輯 .env 並添加你的 GEMINI_API_KEY

# 3. 啟動應用程式
docker compose up -d

# 4. 開啟瀏覽器
# 前往 http://localhost:8000
```

完成！🎉 應用程式現在已經在運行。

停止服務：
```bash
docker compose down
```

---

#### 方法二：手動建置與執行

如果你不想使用 Docker：

```bash
# 1. 複製專案
git clone https://github.com/yourusername/InsightX.git
cd InsightX

# 2. 設定環境變數
cp .env.example .env
# 編輯 .env 並添加你的 GEMINI_API_KEY

# 3. 安裝 Python 依賴
uv sync --frozen

# 4. 安裝並建置前端
npm ci
npm run build

# 5. 安裝 Playwright 瀏覽器（用於網頁爬蟲）
uv run playwright install chromium

# 6. 啟動伺服器
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

# 7. 開啟瀏覽器
# 前往 http://localhost:8000
```

---

### 給開發者（開發環境）

#### 設置開發環境

```bash
# 1. 複製專案
git clone https://github.com/yourusername/InsightX.git
cd InsightX

# 2. 設定環境變數
cp .env.example .env
# 編輯 .env 並添加你的 GEMINI_API_KEY
# 設定 ENVIRONMENT=development

# 3. 安裝 Python 依賴
uv sync

# 4. 安裝前端依賴
npm install

# 5. 安裝 Playwright 瀏覽器
uv run playwright install chromium
```

---

#### 執行開發伺服器

你需要**兩個終端機視窗**：

**終端機 1 - 後端（FastAPI 熱重載）：**
```bash
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**終端機 2 - 前端（Vite 熱模組替換）：**
```bash
npm run dev
```

現在你可以：
- 訪問 Vite 開發伺服器：`http://localhost:5173`（支援 HMR）
- 訪問 FastAPI 後端：`http://localhost:8000`
- 查看 API 文檔：`http://localhost:8000/docs`

> **💡 提示**：開發時使用 `localhost:5173` 可獲得更快的前端開發體驗與熱模組替換。前端會自動將 API 請求代理到 8000 埠。

---

## 📁 專案結構

```
InsightX/
├── 📂 src/
│   ├── 📂 api/              # FastAPI 路由與端點
│   ├── 📂 config/           # 設定檔
│   ├── 📂 services/         # 業務邏輯（爬蟲、AI 分析）
│   ├── 📂 static/           # 前端原始碼
│   │   ├── App.tsx          # 主分析應用
│   │   ├── main.tsx         # 遊戲應用入口
│   │   └── index.html       # 分析頁面
│   └── main.py              # FastAPI 應用程式入口
├── 📂 public/               # 靜態資源（圖片、圖示）
│   └── 📂 pictures/         # 遊戲素材
├── 📂 docs/                 # 文檔與截圖
│   └── 📂 screenshots/      # README 截圖
├── 📂 dist/                 # 生產環境建置輸出（自動生成）
├── 📂 tests/                # 測試套件
├── 🐳 Dockerfile            # Docker 映像定義
├── 🐳 compose.yaml          # Docker Compose 設定
├── 📦 pyproject.toml        # Python 依賴（uv）
├── 📦 package.json          # Node.js 依賴
├── ⚙️ vite.config.ts        # Vite 建置設定
└── 📄 .env.example          # 環境變數範本
```

---

## 🔧 環境變數設定

### 必要的環境變數

在專案根目錄建立 `.env` 檔案（從 `.env.example` 複製）：

```bash
# Google Gemini API 金鑰（必填）
# 從這裡取得你的 API 金鑰：https://aistudio.google.com/app/apikey
GEMINI_API_KEY=你的實際api金鑰

# 應用程式環境
ENVIRONMENT=production  # 或 'development'
```

### 取得 Gemini API 金鑰

1. 前往 [Google AI Studio](https://aistudio.google.com/app/apikey)
2. 使用 Google 帳號登入
3. 點擊「建立 API 金鑰」
4. 複製金鑰並貼到你的 `.env` 檔案

> ⚠️ **安全警告**：絕對不要將 `.env` 檔案提交到版本控制。`.gitignore` 已設定排除此檔案。

---

## 📚 API 文檔

伺服器啟動後，可以訪問：

- **互動式 API 文檔（Swagger UI）**：`http://localhost:8000/docs`
- **備用 API 文檔（ReDoc）**：`http://localhost:8000/redoc`

### 主要端點

| 方法   | 端點           | 說明                  |
| ------ | -------------- | --------------------- |
| `POST` | `/api/analyze` | 提交 URL 進行 AI 分析 |
| `GET`  | `/api/health`  | 健康檢查端點          |

---

## 🔍 疑難排解

### 常見問題

#### 1. 埠號 8000 已被佔用

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:8000 | xargs kill -9
```

#### 2. Playwright 安裝問題

```bash
# 重新安裝 Playwright 瀏覽器
uv run playwright install --force chromium
```

#### 3. 前端建置錯誤

```bash
# 清除快取並重新安裝
rm -rf node_modules dist
npm install
npm run build
```

#### 4. API 金鑰無效

- 確保 `.env` 檔案在專案根目錄
- 檢查 `GEMINI_API_KEY` 沒有引號或多餘空格
- 在 [Google AI Studio](https://aistudio.google.com/app/apikey) 驗證金鑰有效性

#### 5. Docker 問題

```bash
# 從頭重新建置
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

---

## 🛠️ 開發指令

### 後端

```bash
# 執行後端（自動重載）
uv run uvicorn src.main:app --reload

# 執行測試
uv run pytest

# 型別檢查
uv run pyright

# 格式化程式碼
uv run black src/
```

### 前端

```bash
# 啟動開發伺服器
npm run dev

# 建置生產版本
npm run build

# 預覽生產版本
npm run preview

# 型別檢查
npm run type-check
```

---

## 🤝 貢獻指南

我們歡迎貢獻！請遵循以下步驟：

1. Fork 此專案
2. 建立功能分支（`git checkout -b feature/amazing-feature`）
3. 提交你的修改（`git commit -m 'Add amazing feature'`）
4. 推送到分支（`git push origin feature/amazing-feature`）
5. 開啟 Pull Request

---

## 📄 授權條款

本專案採用 MIT 授權條款 - 詳見 [LICENSE](LICENSE) 檔案。

---

## 🙏 致謝

- **Google Gemini 2.0 Flash** - AI 分析引擎
- **FastAPI** - 高效能 Python 網頁框架
- **React + Vite** - 現代化前端技術棧
- **Playwright** - 可靠的網頁爬蟲工具
- **Tailwind CSS** - 優雅的實用優先 CSS 框架

---

<div align="center">

**由 InsightX 團隊用 ❤️ 打造**

⭐ 如果這個專案對你有幫助，請在 GitHub 上給我們一顆星！

</div>
