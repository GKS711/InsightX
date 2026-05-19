# InsightX v4 影片 — Shot List & 字幕腳本

**目標長度**：75-90 秒
**畫面比例**：1920×1080 16:9
**字幕語言**：繁體中文（後續可加英文版）
**配色**：ink #1a1f1c / coral #d65a3a / forest #2c5f2d / cream #faf7f2

---

## 結構總覽

| # | Shot | 時長 | 來源 | 字幕 |
|---|------|------|------|------|
| 1 | INTRO（logo + tagline） | 5s | Remotion | — |
| 2 | 痛點 hook | 7s | Remotion | "200 則評論。 沒人有時間讀。" |
| 3 | SECTION 01 — Landing 貼 URL | 10s | Chrome 錄 | "貼一個 URL，按開始分析。" |
| 4 | SECTION 02 — Hero 評分 + Sentiment Donut | 10s | Chrome 錄 | "目前評分 + 情感分布，一眼看完。" |
| 5 | SECTION 03 — Themes 正負主題 | 10s | Chrome 錄 | "他們實際在談的，不是你以為的。" |
| 6 | SECTION 04 — SWOT + 原文佐證 | 10s | Chrome 錄 | "每條結論都標 evidence-backed。" |
| 7 | SECTION 05 — 50 則原文評論 | 7s | Chrome 錄 | "永遠看得見來源。" |
| 8 | SECTION 06 — Toolbox（5 工具） | 10s | Chrome 錄 | "從洞察到行動：5 件可以今天做的事。" |
| 9 | SECTION 07 — AI Advisor Chat | 8s | Chrome 錄 | "AI 顧問 — context 只有你的資料。" |
| 10 | OUTRO（CTA） | 6s | Remotion | "github.com/GKS711/InsightX" |
| **合計** | | **~83s** | | |

---

## 詳細 shot 規格

### Shot 1 — INTRO (Remotion, 5s)
- 0–0.4s: 黑底淡入
- 0.4–1.5s: coral 圓形 + 白色「i」logo 從中心 scale 0→1，spring 動畫
- 1.5–2.0s: 「insightx」字體從右側淡入（Noto Serif TC bold）
- 2.0–4.0s: 「把顧客每一句話，讀給老闆聽。」字幕從下方淡入
- 4.0–5.0s: hold + 微光（subtle glow）
- 4.5–5.0s: 整體淡出到下一段

### Shot 2 — 痛點 hook (Remotion, 7s)
- cream 背景
- 0–1s: 「200 則」大字（72pt Noto Serif TC，coral）淡入
- 1–2s: 「評論。」續寫（ink）
- 2–3s: 全螢幕白光閃，切到「沒人有時間。」
- 3–5s: 顯示三個 icon row（讀完 / 整理 / 回覆）灰色 ✗
- 5–7s: 切到「但 AI 有。」（淡入 forest 字體）

### Shot 3 — Landing 貼 URL (Chrome, 10s)
**動作序列**：
1. 截 LandingPage 完整畫面（含 hero「AI 管理顧問」H1 + persona buttons + URL input）
2. 模擬使用者：輸入 Google Maps URL（用測試 URL：`https://www.google.com/maps/place/全家便利商店大雅清泉店`）
3. 點「開始分析」按鈕
4. 顯示分析中 SSE 進度條
**字幕**：「貼一個 URL，按開始分析。」（0.5s in / 8s hold / 1.5s out）

### Shot 4 — Hero 評分區 (Chrome, 10s)
**動作**：
1. 顯示 Hero 區（店名 / 地址 / 「目前評分 3.5★」/ 90 天趨勢線 / Sentiment Donut 39% positive）
2. 慢速 scroll 0.5x，停在 donut chart
3. callout 框圈住 donut（Remotion overlay 後製）
**字幕**：「目前評分 + 90 天趨勢 + 情感分布 — 一眼看完。」

### Shot 5 — Themes 主題 (Chrome, 10s)
**動作**：
1. Scroll 到 §02 Themes 區
2. 顯示「正向主題 Top 3」+「負面主題 Top 3」（含 % 數字 + bar）
3. 對「服務態度好」/「等候時間長」這類 quote 做 zoom-in callout
**字幕**：「他們實際在談的，不是你以為的。」

### Shot 6 — SWOT (Chrome, 10s)
**動作**：
1. Scroll 到 §03 SWOT
2. 四象限 fade-in（依序 S→W→O→T）
3. callout 「原文佐證」icon 旁的 evidence 引用
**字幕**：「SWOT 四象限，每條結論都標 evidence-backed。」

### Shot 7 — Reviews 50 則 (Chrome, 7s)
**動作**：
1. Scroll 到 §04 評論列表
2. 顯示 caption「分析了 N 則 · 顯示精選的 50 則」
3. 快速 scroll 過 review cards 顯示量感
**字幕**：「永遠看得見來源 — 50 則原文。」

### Shot 8 — Toolbox (Chrome, 10s)
**動作**：
1. 點頂部「工具箱」tab
2. 顯示 5 個工具卡片（負評回覆 / 行銷 / 週計畫 / 培訓 / 內部信）
3. 點開「行銷文案」展示 AI 生成內容
**字幕**：「從洞察到行動：5 件可以今天做的事。」

### Shot 9 — AI Advisor (Chrome, 8s)
**動作**：
1. 點頂部「AI 顧問」tab
2. 在 chat 輸入框打「我該優先改善哪個負面主題？」
3. 送出，顯示 AI 回應 streaming（前幾秒）
**字幕**：「AI 顧問 — context 只有你的資料。」

### Shot 10 — OUTRO (Remotion, 6s)
- 0–1s: 從上一畫面 fade to 黑
- 1–3s: 「立即試用。」大字（80pt 白）淡入
- 3–4.5s: github.com/GKS711/InsightX URL 在 coral pill 框內出現
- 4.5–6s: 「MIT License · 零瀏覽器 · 雙平台」淡入 + hold

---

## 字幕樣式

- 字體：Noto Sans TC SemiBold 36pt（電腦觀看 / 1080p 適合）
- 顏色：白色 + 半透明黑色描邊（4px）
- 位置：底部 1/8 處，左對齊（離左邊 80px）
- 進場：fade-in 0.3s
- 退場：fade-out 0.3s

---

## 轉場

| 從 → 到 | 轉場 | 時長 |
|---------|------|------|
| INTRO → 痛點 | crossfade | 0.5s |
| 痛點 → Landing | iris 從中心展開 | 0.6s |
| Landing → Hero | slide left | 0.4s |
| Hero ↔ Themes ↔ SWOT ↔ Reviews | fade | 0.3s |
| Reviews → Toolbox | slide up | 0.5s |
| Toolbox → AI Advisor | fade | 0.3s |
| AI Advisor → OUTRO | fade to black | 0.7s |

---

## 音效（如有）

- 啟動 (Shot 1): 短的 "ting" 鈴聲（CC0）
- 章節切換: 微小 swoosh
- OUTRO: 上揚音色

> 若無 BGM 庫，可用 https://freesound.org/ CC0 素材，或保持靜音 + 字幕版本

---

## 測試資料

- 主要 Demo URL: `https://www.google.com/maps/place/全家便利商店大雅清泉店/@24.241,120.617,17z`
  - 已知能跑通 P3.5 之後驗證過
  - 約 57 則評論可分析
- 備用 URL（萬一首選失敗）: `https://maps.app.goo.gl/8mWaXukpwWxnnoBN9`

---

## 失敗 fallback 路徑

1. SSE 卡 → 重錄該段，最多 3 次
2. gif_creator 不出來 → 用 v4 截圖（docs/screenshots/v4/）做 Ken Burns 替代
3. Remotion render 慢 → 降 24fps / 720p
4. 全鏈失敗 → 純 Remotion 動畫版本（A 方案 fallback）
