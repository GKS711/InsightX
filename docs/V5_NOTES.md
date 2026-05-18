# V5_NOTES — InsightX v5 work-in-progress policy

**最後更新**：2026-05-19
**路徑變更**：原本在 `.claude/v5-work/V5_NOTES.md`（被 `.gitignore` 排除，已隨 Cowork worktree 一併消失）→ 現遷至 `docs/V5_NOTES.md` 並 commit 進 git，跟 v3/v4 系列 docs 同層，未來不會再因 worktree 清理而丟失。

---

## 約束（**只有一條**）

> **不要開 PR 把 `claude/distracted-roentgen-e83b40` 整批 merge 進 `main`。**

v5 還在進行中，不適合一次把所有 commit 全合進 main。等到階段性成熟、要把某個 feature 正式釋出時，再走 **cherry-pick 個別 commit** 或 **單獨開 commit 的方式進 main**，不要走「PR 大合併」。

---

## 允許的動作

| 動作 | 狀態 |
|---|---|
| `git push origin claude/distracted-roentgen-e83b40` 推 branch 到 GitHub | ✅ 允許 — 純雲端備份 / 跨機器同步 |
| 在 `main` 上 commit / push | ✅ 允許 — main 不再凍結 |
| Cherry-pick v5 commit 到 main | ✅ 允許 — 階段性釋出的正式管道 |
| Co-Authored-By: Claude 署名 | ✅ 允許 — 歷史 commit 已有，不再糾正 |
| 任何 v5 branch 上的進一步開發 | ✅ 允許 |
| **開 PR (`claude/... → main`) 大合併** | ❌ **唯一禁止** |

---

## 為什麼禁這一條

PR 預設會把整個 source branch（這裡是 v5 累積的 8+ 個 commit）一次 squash 或 merge 進 target。對 WIP 來說會：

1. 把未個別測過的 commit 一起帶進 main，main 失去穩定保證
2. 失去個別 commit 的 review 機會（PR 是整批同意）
3. 之後想退某個改動很難（要 revert 一整坨）

**替代方案**：v5 階段性成熟 → `git checkout main && git cherry-pick <hash>` 把該 commit 拉到 main → 個別 review + 個別 push。

---

## 歷史脈絡（為了避免再次誤解）

5/18 原本的 V5_NOTES 寫的是「**worktree-only、no push、no PR、main 不動、no Claude attribution**」——過嚴。5/19 通盤檢視後修正：

| 原政策 | 修正 | 原因 |
|---|---|---|
| no push | ✅ 開放 | branch push 是雲端備份，沒理由禁 |
| no PR | ⚠️ 部分保留 | PR 大合併禁；cherry-pick / 個別 commit 開放 |
| main 不動 | ✅ 開放 | main 不需要凍結 |
| no Claude attribution | ✅ 開放 | 歷史既成事實，不糾正 |
