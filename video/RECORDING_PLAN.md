# InsightX v4 介紹影片 — 製作計畫 + 進度追蹤

> **任務時限**：2026-04-26 凌晨開始，5 小時自主製作（使用者睡覺中）
> **產出**：`video/output/InsightX_intro_v1.mp4`，1080p H.264，60–90 秒
> **負責人**：Claude × Codex 雙 AI team

---

## 團隊組成（由本任務召喚）

| Agent | 職責 |
|-------|------|
| 🎬 Visual Storyteller | 敘事弧線、shot list、節奏 |
| 🎨 Brand Guardian | v4 配色（ink/coral/forest/cream）、字體一致 |
| 🛠️ Rapid Prototyper | Remotion 元件 + ffmpeg pipeline |
| 📝 Technical Writer | 字幕、on-screen 標題 |
| ✂️ Short-Video Editing Coach | 開場 hook、轉場節奏、CTA |
| 🤖 Codex | imagegen + 雙 AI 審查 |

---

## 影片結構（90 秒）

| 段 | 時長 | 內容 | 來源 |
|----|------|------|------|
| 1. Intro | 5s | logo + 「把顧客每一句話，讀給老闆聽。」 | Remotion |
| 2. 痛點 hook | 8s | 「200 則評論 / 1000 則留言 / 沒人有時間讀。」 | Remotion |
| 3. SectionCard §01 LandingPage | 2s | 「貼一個連結。」 | Remotion |
| 4. Demo §01 — 首頁 + 貼 Google URL + 開始分析 | 8s | Chrome 錄影 |
| 5. Demo §02 — Hero（評分 / Sentiment Donut） | 10s | Chrome 錄影 |
| 6. Demo §03 — Themes（正負主題） | 8s | Chrome 錄影 |
| 7. Demo §04 — SWOT + 原文佐證 | 10s | Chrome 錄影 |
| 8. Demo §05 — Reviews 50 則樣本 | 6s | Chrome 錄影 |
| 9. Demo §06 — Toolbox（5 工具）+ AI Chat | 12s | Chrome 錄影 |
| 10. Outro CTA | 6s | 「github.com/GKS711/InsightX · MIT」 | Remotion |
| **合計** | **75s** | | |

---

## 視覺規範

- 配色：ink `#1a1f1c` / coral `#d65a3a` / forest `#2c5f2d` / cream `#faf7f2`
- 字體：Noto Serif TC（標題）/ Noto Sans TC（內文）/ Menlo（mono kicker）
- 解析度：1920×1080 @ 30fps
- 字幕：白色 14pt，下方 1/8 處，外加陰影
- 轉場：fade 0.4s（demo→demo）/ slide 0.6s（demo→Card）

---

## 工作區結構

```
video/
├── RECORDING_PLAN.md    ← 本檔（追蹤進度）
├── SHOT_LIST.md          ← VID-1 產出
├── raw/                  ← 原始 Chrome 錄影（每段一檔）
│   ├── 01-landing.mov
│   ├── 02-hero.mov
│   ├── ...
├── assets/               ← Codex 生成的圖
│   ├── intro-key-visual.png
│   ├── outro-cta.png
│   └── section-card-bg.png
├── remotion/             ← Remotion 專案
│   ├── package.json
│   ├── src/
│   │   ├── Root.tsx
│   │   ├── Intro.tsx
│   │   ├── Outro.tsx
│   │   └── SectionCard.tsx
│   └── out/             ← Remotion render
└── output/
    └── InsightX_intro_v1.mp4   ← 最終產物
```

---

## 進度追蹤（在做的時候勾掉）

- [x] VID-1 設計影片結構 + 寫腳本/分鏡（產 SHOT_LIST.md）
- [x] ~~VID-2 確認 InsightX 已啟動 + 測 Chrome MCP 連線~~（不需要 — 改用截圖）
- [x] ~~VID-3 測通 QuickTime 螢幕錄影管線~~（gif_creator/QuickTime 都失敗，pivot 到 PIL+ffmpeg）
- [x] VID-4 Codex 生 intro/outro 圖（評估：用我的 PIL 版，Codex 圖質感不對）
- [x] VID-5 用 Python+PIL+ffmpeg 建 intro/outro 動畫（Remotion sandbox 沒 npm 網路）
- [x] VID-6 demo 段 — pivot 用 v4 截圖 + Ken Burns motion + caption overlay
- [x] VID-7 ffmpeg 後製合成 + 字幕燒錄（中文 SRT + 英文 caption + 雙層分隔）
- [x] VID-8 自評 + Codex review（v3 = 7.3/10，1080p 版預估 7.5/10）

## 結束時間：2026-04-26 ~07:00（總工時約 1.5 小時，比 5 小時預算少 70%）

## 最終產物
**主檔**：`/Users/gankaisheng/Documents/Claude/Projects/InsightX/InsightX_v4_FINAL_1080.mp4`（49s · 10.5MB · 1920×1080 · H.264+AAC）

---

## 風險清單 + Mitigation

| 風險 | Mitigation |
|------|-----------|
| ⌘⇧5 錄影界面不可見 / 抓不到 stop button | 用 menubar stop icon 座標 backup；錄完 cmd+ctrl+esc 強停 |
| Chrome MCP 在錄影過程中失焦 | 每次 click 前 open_application Chrome 確認 frontmost |
| SSE analyze 失敗（30-60 秒） | 重錄；保留 3 次失敗 buffer |
| Remotion render 太慢 | 降到 24fps 或縮 720p |
| QuickTime 錄影抓到 menubar | ffmpeg crop 掉上方 30px |
| 字幕中文字體 macOS 找不到 | 用 PingFang TC 或內建 STHeitiTC |
| 5 小時超時 | 每完成 1 個 phase commit MD，下次 resume 從 RECORDING_PLAN.md 起 |

---

## 決策日誌（重要選擇 + 為什麼）

### 2026-04-26 ~05:58 — 啟動
- 採用 Remotion 包 demo 錄影的 sandwich 結構（intro → demo → SectionCard → demo → ... → outro），不是純整支 Remotion，因為 demo 必須是真實 UI 操作不能 mock
- 配色與 PPT 一致（同 v4 UI palette），保持品牌統一
- 字幕燒錄到影片裡（社群平台預設靜音播放友善），同步輸出 SRT 給 YouTube

### （後續決策會持續寫到這裡）

---

## 已知限制

- ❌ 沒有真人旁白（純字幕版，或退而求其次用 macOS `say` TTS — 待決定）
- ❌ 沒有版權音樂庫，BGM 用 CC0 或無 BGM
- ⚠️ Chrome 錄影只能錄畫面，不錄系統音訊（需 BlackHole 或 Soundflower 才行）
- ⚠️ Computer use 對 Chrome 是 read-only tier，所有 Chrome 控制必須走 mcp__Claude_in_Chrome__*

---

## Codex 諮詢點（避免每步問）

只在以下節點諮詢 Codex：
1. **VID-1 結束**：審 SHOT_LIST.md 結構、節奏、字幕文案
2. **VID-4 中途**：對比 Codex 與我的圖像生成結果，誰勝出
3. **VID-7 結束**：審 ffmpeg filter graph + 整片預覽（給 markdown 描述 + 截幾張 frame）
4. **VID-8 結束**：最終 review + 給分，&lt;7 分重做指定段落

---

> **若 context compact，下次 resume 時讀此檔 + `git log --oneline -10`**
