# InsightX v4.0.0 · Smoke Test（本機 E2E 驗證）

> 用途：在本機啟動 FastAPI 後，驗證 v4 後端契約（/api/meta、/api/v4/analyze-stream、8 個 feature endpoints）與新 UI（`/` → `src/static/v2/index.html`）的端到端流程。靜態測試（Python AST、JSX parser、reducer + adapter terminal action shape smoke 共 48 case）已在 repo 內通過；這份文件是「人類親手跑一次」的清單。
>
> **2026-04-23 更新（P3.11 結案）**：v2-design 已接入 SSE + 全部 8 個 feature adapter + ChatDock（P3 完成）。同日 P3.10 重設 LLM timeout/budget；P3.11 把 root_cause / weekly_plan / training_script / internal_email 的 prompt skeleton 改成「【】◆　▸ 純文字結構」，前端走 `<pre>` 直出（**不再用 marked.js / 任何 markdown render**）。reducer 重置規則 + adapter terminal action shape（runId+requestId）已鎖定 — 詳見 HANDOFF.md「P3.11」章節。
>
> **靜態驗證通過項目**（自動化可重跑，不需啟 uvicorn）：
> - `node validate_jsx.cjs` → `OK · lines: 3438`（JSX 可解析；P3.12-R2 後端不 cap 照抓全部 + 前端 §04 ReviewsSection slice(0, 50) 顯示限制 + 「全部」改「精選」字樣 + 三段 caption「本次分析了 N 則 · 下方顯示其中 50 則樣本 · Google Maps 共 M 則評分」）
> - `python3 -c 'import ast; ast.parse(open(f).read())'` 對 main.py / routes.py / services/*.py 全過
> - `node src/static/v2/core/*.js` + `hooks/*.js` + `bootstrap.js` 全過語法檢查
> - **`node outputs/test_reducer.mjs` → 48/48 pass**（P3.11 Round-4/5 起；SWITCH_PLATFORM/SWITCH_YT_ROLE 變動 vs 同值、FETCH_ANALYZE_START loading + 下游 reset、SUCCEEDED 不被 stale 丟、STREAM 完整路徑、case 8/9/10 stale check + connection-lost split state、case 11a/b/c stub EventSource 真打 onerror/failed/result + 鎖死 adapter terminal action 帶 runId+requestId+errorVM.requestId 對齊；**case 11d/11e** malformed terminal JSON → STREAM_CONNECTION_LOST、不可 silent close 卡 loading、action 外層 + errorVM.requestId 兩層都要對齊 START.requestId；**case 11f** openSSE 沒帶 opts.requestId → errorVM.requestId === null，絕不偷塞 runId 冒充）
> - `src/main.py` 的 `/` 掛 v2-design、`/legacy` 掛 v3 HTML 已確認（routes AST 比對）
> - `src/api/routes.py` 的 12 個預期 endpoint（/meta、/v4/analyze-stream、/analyze-stream、/analyze、/swot、/reply、/analyze-issue、/marketing、/weekly-plan、/training-script、/internal-email、/chat）全部存在
>
> **需要人類親跑**：§1–§6 含 curl（需真 GEMINI / SERPER / YOUTUBE key）與瀏覽器 QA。

---

## 0. 先決條件

- Python venv：`/Users/gankaisheng/VScode/Claude實作/InsightX/.venv/`
- `.env` 包含 `GEMINI_API_KEY`、`SERPER_API_KEY`（選用 `YOUTUBE_API_KEY`）
- 瀏覽器：Chrome

## 1. 啟動後端

```bash
cd /Users/gankaisheng/VScode/Claude實作/InsightX
source .venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

應看到 `Application startup complete.`。

## 2. 驗 /api/meta

```bash
curl -s http://localhost:8000/api/meta | python3 -m json.tool
```

預期：

```json
{
  "appVersion": "4.0.0",
  "availablePlatforms": ["google", "youtube"],
  "availableYtRoles": ["creator", "shop", "brand"],
  "featureFlags": {
    "sse_v4": true,
    "chat_history_persist": false
  },
  "_fallback": false,
  "warnings": []
}
```

## 3. 驗 /api/v4/analyze-stream（SSE）

### 3a. 正常流程（Google Maps）

```bash
curl -N "http://localhost:8000/api/v4/analyze-stream?url=https%3A%2F%2Fmaps.app.goo.gl%2FXXXXXXX"
```

預期 event 順序：

```
event: progress
data: {"phase":"connected","step":0,...,"progress":0.0,...}

event: progress
data: {"phase":"scraping","step":1,...,"progress":0.2,...}

event: progress
data: {"phase":"scraping","step":2,...,"progress":0.4,...}

event: progress
data: {"phase":"analyzing","step":3,...,"progress":0.7,...}

event: progress
data: {"phase":"finalizing","step":4,...,"progress":1.0,...}

event: result
data: {"platform":"google","effective_yt_role":null,"durationMs":12345,"data":{...}}
```

### 3b. 422 驗證失敗（不進 stream）

```bash
# platform hint 與 URL 不符
curl -s -o /dev/null -w "%{http_code}\n" \
  "http://localhost:8000/api/v4/analyze-stream?url=https%3A%2F%2Fmaps.app.goo.gl%2Fabc&platform=youtube"
# 預期：422
```

### 3c. 心跳

長時間 LLM 呼叫應看到 `: ping` 行（每 15 秒）。`: ping` 不帶 `event:` 欄位，EventSource 會忽略。

## 4. 驗 8 個 feature endpoints（都回 metadata 包裝）

每個 endpoint 的回應都必含：`effective_yt_role`、`_fallback`、`warnings`。

```bash
# /api/swot 示例
curl -s -X POST http://localhost:8000/api/swot \
  -H "Content-Type: application/json" \
  -d '{
    "good":[{"label":"餐點美味","value":32}],
    "bad":[{"label":"等候時間過長","value":15}],
    "platform":"google"
  }' | python3 -m json.tool
```

預期片段：

```json
{
  "strengths": [...],
  "weaknesses": [...],
  "opportunities": [...],
  "threats": [...],
  "effective_yt_role": null,
  "_fallback": false,
  "warnings": []
}
```

類似可驗：`/api/reply`、`/api/analyze-issue`、`/api/marketing`、`/api/weekly-plan`、`/api/training-script`、`/api/internal-email`、`/api/chat`。

### 4a. yt_role canonicalizer 行為

```bash
# google 平台不該帶 yt_role → 後端會吞掉並塞 warnings
curl -s -X POST http://localhost:8000/api/swot \
  -H "Content-Type: application/json" \
  -d '{"good":[],"bad":[],"platform":"google","yt_role":"creator"}' \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('effective:',d['effective_yt_role']);print('warnings:',d['warnings'])"
# 預期：effective: None
#       warnings: ['yt_role ignored when platform=google']
```

## 5. 驗新前端（v2-design UI）

瀏覽器開 <http://localhost:8000/>（注意：`/` 直接路由到 `src/static/v2/index.html`；舊 v3 HTML 在 `/legacy`）。

### 5a. DevTools Console — bootstrap 就緒

- [ ] 開 DevTools → Console，應看到 `[IX] bootstrap ready · v4.0.0`
- [ ] 在 console 打 `window.IX` 應回 frozen object，含 `Adapters`, `useAppReducer`, `useAnalyzeStream`, `version: "4.0.0"` 等

### 5b. Landing → 分析 → Dashboard 流程

- [ ] 首頁 Hero → scroll 看到 ValueProp 三步驟 SVG、StoryBlock insight SVG
- [ ] 捲到「想看看你的？」區塊 → 點「我是店家」卡片 → 進入 Landing Input 畫面
- [ ] URL 欄位貼一個真的 Google Maps 短網址（例：`https://maps.app.goo.gl/XXXX`）
- [ ] 點「開始分析」→ 看到 AnalyzingBlock：進度條走動、phase label 跟著改（`scraping` → `analyzing` → `finalizing`）
- [ ] DevTools → Network → 有一筆 `analyze-stream?url=...` 的 SSE 連線；Response 欄位看到 `event: progress` / `event: result`
- [ ] 大約 15–25 秒後自動跳進 ShopDashboard（SSE result → phase=succeeded → 延遲 400ms 切換）

### 5c. ShopDashboard — 真實資料顯示（P3.5 後禁止 mock fallback）

- [ ] ShopHero 標題不是「示範小館」而是**真的店家名稱**（例：「全家便利商店 大雅清泉店」）
- [ ] Pill 顯示「本次分析報告」（而非「本週報告 · IX-0001」），證明 `vm.hasRealData=true`
- [ ] Hero 下方地址 / 類型 / 營業時間：backend 有拿到才顯示、沒有就**隱藏整列**；禁止顯示 mock「範例市・示範區・樣板路 100 號」「Casual Dining」「每日 15:30-21:00」
- [ ] Hero stats 第一格「目前評分」：backend 吐 rating 才顯示數字 + 星號 + 「X 則評分」Pill；沒吐就顯示 `—` 且不出星號
- [ ] Hero stats 第一格底下的 90 天 Sparkline：只在 landing demo 顯示，進入真實 dashboard 後**不應出現**（backend 無歷史趨勢）
- [ ] Hero stats 第二格「總評論數」= backend 的 `total_reviews`（例：20）、副標「本次分析」
- [ ] Hero stats 第三格「正向情感」= `Σ good[].value` 後四捨五入；副標「本次留言情感占比」
- [ ] Hero stats 第四格改成「負面情感」= `Σ bad[].value`；副標「本次留言情感占比」（不再是「待回覆 收錄尚未回的負評」那個 magic number）
- [ ] §01 情感判讀標題要用真實數字：「{total_reviews} 則評論，{positive}% 是在說「再來一次」」
- [ ] §01 donut 內圈 % = 真實 `positive`，不再是固定 68
- [ ] §01 LegendRow：count 從 pct × total_reviews 算回；**sample 引言隱藏**（backend 無逐則 quote）
- [ ] §01 顧問觀察文案含「{negative}% 負評，其中以『{最高佔比負評主題}』佔比最高」，非固定 "40% 出餐速度"
- [ ] §02 顧客主題區：「好評主題」列出**真的** good[] 標籤，負評一樣；**每個主題底下的義大利體 quote 隱藏**（backend 無 sample 欄位）
- [ ] §03 SWOT 區 kicker 在載入時顯示「AI 生成中…」→ 幾秒後替換成**真的** SWOT 內容（不是「真材實料的信任感」mock）
- [ ] DevTools Network 可看到 `/api/swot` POST 一次（由 ShopSwotSection 的 useEffect 自動觸發）

### 5d. YouTubeDashboard — 真實資料顯示

- [ ] 回首頁 → 選 YouTube tab → 選角色（例：「我是影片創作者」）→ 貼 YouTube 網址 → 分析
- [ ] 完成後 YTHero 標題 = **真影片標題**（從爬蟲 oEmbed 取得）
- [ ] YTCommentBreakdown §02：標題顯示「X 則留言拆成 N 個主題」，X 是真實留言數、N 是 good+bad 總數
- [ ] 主題列表顯示真的 good / bad 標籤

### 5e. Persist 驗證

- [ ] 重新整理頁面 → URL 與 platform tab 選擇被還原（localStorage HYDRATE 生效）
- [ ] DevTools → Application → Local Storage 看到 key `insightx.v4.state`
- [ ] value 裡有 `"_v":"4.0.0"`；`stream`、`chat`、`alerts`、`meta`、`features` 欄位**不在**（白名單正確）

### 5f. 取消流程

- [ ] 點「開始分析」後立刻點左上角「返回」→ AnalyzingBlock 消失、回到輸入
- [ ] uvicorn log 應看到 task cancelled（不應有未關閉的 child task 警告）

### 5g. ShopRepliesSection — fetchReply 接真資料（P3 新增）

- [ ] 捲到 §05 客訴回覆區（ShopRepliesSection）
- [ ] 左側主題 tab 顯示的不是 mock「餐點口味問題 / 服務態度問題 / ...」，而是 `vm.themesNeg` 的真實負評標籤（例：「等太久」「店員冷淡」）
- [ ] 點任一 tab → 右側顯示 skeleton（灰階動畫 3 列）→ 幾秒後換成 AI 生成的純文字回覆（`<pre>` 直出，使用 【】◆　▸ 結構符號，**禁止**出現 `**` 粗體或 `##` 標題殘留）
- [ ] 切到其他 tab → 觸發另一次 `/api/reply`（Network 可看到）→ 切回已載過的 tab → **不再重打 API**（local cache 生效）
- [ ] 若 API 失敗，顯示紅色錯誤 panel + 「重試」按鈕；點重試可重新 dispatch

### 5h. ShopWeekPlanSection / ShopMarketingSection — 自動 fetch（P3 新增）

- [ ] 進入 dashboard 後 §06 週計畫區下方出現 AI 生成的純文字計畫卡片（`<pre>` 直出，暗色底），載入中顯示「AI 生成中…」小標 + skeleton
- [ ] §07 行銷文案區下方出現 AI 純文字卡片（`<pre>` 直出）+ 右上角「複製」按鈕
- [ ] DevTools → Network 自動觸發 `/api/weekly-plan`、`/api/marketing` 各一次（hasRealData=true 才觸發）
- [ ] 失敗時顯示錯誤訊息 + 重試按鈕

### 5i. AiToolsPanel — 三合一工具（§08 店家模式 / §07 YouTube 模式，P3 新增）

- [ ] 捲到最後的 AiToolsPanel 區塊：左側 3 個 tab（培訓劇本 / 內部週報 / 根源分析）
- [ ] 首次進入自動載入「培訓劇本」→ 顯示 skeleton → 幾秒後出現 AI 純文字內容（`<pre>` 直出，**禁止**出現 `**` 粗體 / `##` 標題殘留）
- [ ] 點「內部週報」tab → 觸發 `/api/internal-email`
- [ ] 點「根源分析」tab → 觸發 `/api/analyze-issue`
- [ ] 切回已載過的 tab → **不再重打 API**（reducer state 保留 ready 結果）
- [ ] 失敗時顯示紅色錯誤 + 重試按鈕

### 5j. ChatDock — 問 AI 對話（P3 新增）

- [ ] 右上角 DashNav 的「問 AI」按鈕點下去 → 右下角彈出對話面板
- [ ] 輸入「這間店最大的問題是什麼？」→ Enter 送出（Shift+Enter 換行）
- [ ] Network 有 `/api/chat` POST，帶 `message + context`（context 內含 store_name + good/bad 摘要）
- [ ] 回覆出現在對話區；user / ai 兩種 bubble 對齊正確
- [ ] 連續對話：第二題 context 仍帶得上
- [ ] 關閉 panel 再打開 → 歷史訊息保留（ix.state.chat.messages 在 reducer 中）

## 6. 已知不足（P4+）

- ShopReviewsSection 的 review 文字仍是 mock（後端 /analyze 只吐 good/bad 標籤與比例，沒吐逐則評論）。若要顯示真實評論 quote，需要後端新增欄位。
- Hero stats 第一格的 90 天 Sparkline 已在真實 dashboard 隱藏；若日後要支援，需要後端提供時間序列 API。
- §01 donut 內圈 % 已改用真實 `positive`；neutral 用 `max(0, 100-pos-neg)` 推回。若未來 backend 吐 neutral 欄位可直接替換。
- 舊 `/api/analyze-stream`（v3）留在 routes.py 做緩衝期相容；v3 UI 穩定驗證後可刪。
- PDF 下載按鈕尚未實作。

---

最後更新：2026-04-23（P3.12-R2 後端不 cap 照抓全部評論 + 前端 §04 ReviewsSection 顯示限制 50 + 「全部」改「精選」+ 三段 caption 補說明；P3.11 六輪 Codex 雙 AI 結案；prompt 純文字結構鎖定；SSE openSSE/result/failed listener malformed JSON 不 silent close 鎖定；ErrorVM.requestId fallback 改 null（runId 絕不冒充）；JSX 3438 行；outputs/test_reducer.mjs 48 case 回歸，含 11a/b/c terminal action shape + 11d/11e malformed terminal（外層 action + 內層 errorVM 雙重 requestId 鎖點） + 11f opts.requestId 缺值）
