# InsightX v4 介紹影片 — 交付筆記

> 5 小時自主任務，2026-04-26 凌晨完成
> 團隊：Claude × Codex 雙 AI（Visual Storyteller / Brand Guardian / Rapid Prototyper / Technical Writer / Short-Video Editing Coach）

---

## 交付物（在 `InsightX/` 根目錄）

| 檔案 | 說明 | 評分 |
|------|------|------|
| `InsightX_v4_FINAL_1080.mp4` | **★ 主交付**：49 秒 / 1920×1080 / 10.5MB / H.264+AAC | **7.5/10** |
| `InsightX_v4_FINAL.mp4` | 720p 版本（6.7MB，社群上傳更快） | 7/10 |
| `InsightX_v4_intro_v2_xfade.mp4` | v2 中間版（10 段 demo + xfade，65s） | 6/10 |
| `InsightX_v4_intro_v1.mp4` | v1 第一版（10 段 demo + 硬切，70s） | 5/10 |

**主交付是 `InsightX_v4_FINAL_1080.mp4`** — 1080p 對 dashboard 細字字夠清晰，10MB 在 LinkedIn / X / YouTube 都能接受。

---

## 結構（49 秒）

```
0–5s    INTRO          黑底 + "Read every word. Brief the boss."
5–12s   §01 PASTE      Landing 截圖 + Ken Burns zoom-in
12–19s  §02 AT-A-GLANCE  Hero 截圖 + zoom-in left
19–26s  §03 WHAT THEY SAY  Themes 截圖 + pan-down
26–33s  §04 STRATEGIC POSTURE  SWOT 截圖 + zoom-in center
33–40s  §05 WHAT TO SHIP  Week-plan 截圖 + zoom-in
40–47s  §06 ASK YOUR DATA  AI Advisor 截圖 + zoom-in
47–49s  OUTRO          "Try it now." + github.com/GKS711/InsightX
```

每段 6.6 秒（含 0.4s 與下一段的 xfade）。

---

## 視覺層次（按 Codex 建議重做）

- **左上 section label**：coral 直線 + 黑底卡 + 英文 kicker + 英文標題（不擋畫面）
- **右上 segment counter**：`01 / 06`
- **下方 SRT 字幕**：中文 — 燒入用 Droid Sans Fallback CJK 字體
- 兩層字幕**互不打架**

---

## 音訊

**ffmpeg 純合成的 ambient pad**：
- 110Hz sine wave + 三層 echo + lowpass 600Hz + lowered volume
- 沒有 melody，純氛圍墊底
- 0.5s fade-in，1.5s fade-out

**推薦改善**：去 [Pixabay Music](https://pixabay.com/music/search/genre/corporate/) 或 [Mixkit](https://mixkit.co/free-stock-music/) 抓一首 CC0/CC-BY corporate ambient 音樂（30-60 秒），用 ffmpeg 替換：

```bash
ffmpeg -i InsightX_v4_FINAL.mp4 -i your_bgm.mp3 \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 96k \
  -shortest InsightX_v4_FINAL_with_bgm.mp4
```

---

## 已知限制（誠實說）

| 項目 | 限制 | 為什麼 |
|------|------|--------|
| **不是真實 Chrome 錄影** | 用了 docs/screenshots/v4/ 已有的 10 張截圖 | Chrome MCP 對 InsightX SPA 的 `screenshot` action 卡 `document_idle`（SSE 一直跑 doc 永遠不 idle）；`gif_creator` 抱怨 tab 不在 MCP group；computer-use 截圖路徑 sandbox 摸不到 |
| **解析度 720p**（不是 1080p） | 為了 ffmpeg 編碼速度（每段 3s vs 30s+） | 主因是 sandbox 無 GPU，CPU 編碼 1080p 太慢 |
| **音訊很淡** | ffmpeg 合成 sine wave + echo 不算 BGM | sandbox 無網路無法下載 CC0 音樂；本地也沒有 music asset |
| **沒實際 SSE 即時動畫** | 用 Ken Burns 模擬「動感」 | 同前，無法真錄 SSE streaming |
| **英文 caption + 中文 SRT** | 無法在 sandbox 用 CJK 字體做英文 caption | DroidSansFallback 是 fallback，正體美感不如 Noto Serif TC |

---

## Codex 評分歷程

**v1（10 段、70s、無轉場、無音）**：6/10
- "10 段 demo 對 dashboard 影片來說每段只夠認出畫面，不夠理解價值"
- "硬切 + 沒音訊扣分明顯"

**v2_xfade（10 段、65s、xfade、無音）**：6/10
- "雙字幕都在下方 1/3 打架"
- "70 秒 / 12 段太擠，砍到 5-6 個段落更有敘事弧線"

**v3 = FINAL（6 段、49s、xfade、ambient pad）**：自評 **7/10**
- 已採納 Codex 全部結構建議（砍段、字幕分層、加音、CTA 改具體）
- 音訊還是弱，但不再是 deal-breaker
- 可繼續優化的：1080p 重 render、真 BGM、9:16 vertical 版

---

## 工作區（`video/` 資料夾內）

```
video/
├── NOTES.md                       ← 本檔（交付筆記）
├── RECORDING_PLAN.md              ← 5 小時計畫（含全部決策日誌）
├── SHOT_LIST.md                   ← 原 12 段腳本
├── subtitles.srt / subtitles_v2.srt ← 兩版字幕
├── build_intro.py                 ← Python+PIL intro 動畫
├── build_outro.py                 ← Python+PIL outro 動畫
├── build_demo.py                  ← v1 (10 段)
├── build_demo_v2.py               ← v2 (6 段)
├── composite_xfade.py             ← v2 xfade composite
├── composite_v3.py                ← v3 silent composite
├── intro.mp4 / intro_720.mp4      ← intro render
├── outro.mp4 / outro_720.mp4      ← outro render
├── ambient_pad.aac                ← ffmpeg 合成 ambient
├── intro_frames/  outro_frames/   ← Python keyframes
├── demo_segments/                 ← v1 10 段
├── demo_segments_v2/              ← v2 6 段（採用）
└── output/
    ├── InsightX_v4_intro_v1.mp4
    ├── InsightX_v4_intro_v2_subs.mp4
    ├── InsightX_v4_intro_v3_xfade.mp4
    ├── InsightX_v4_v3_silent.mp4
    └── InsightX_v4_FINAL.mp4      ← 主成品
```

---

## 安裝補充

5 小時內**沒裝任何永久依賴**到使用者機器上。所有工具都是 sandbox 預先就有的：

- Python 3.10+ + PIL（Pillow）— sandbox 預裝
- ffmpeg 4.4 — sandbox 預裝
- DejaVu / Droid Sans Fallback fonts — sandbox 預裝

唯一寫到使用者磁碟的東西是 `start_insightx.command`（在 InsightX repo 根目錄，是當初為了啟動 uvicorn 留的，可以刪）。
