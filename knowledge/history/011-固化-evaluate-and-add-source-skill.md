# 011：固化 evaluate-and-add-source 技能
> 日期：2026-07-23
> ⚠️ **已被 [107](107-退役會教錯路的來源skill-小腦沒有oracle.md) 取代（2026-08-23，退役）**——
> 這個技能的前提（一份會被定時抓取的來源名冊）隨 [068](068-退役新聞分診子系統.md) 消失了，
> 而它第 4 步要跑的 `knowfield … digest` 子指令已不存在。本條保留為固化當時的因果。

## 轉移
- 舊：「評估並加入來源」是重複的手動操作——實測 → 挑 → 加 → 驗 → 反流，已做 4 次
  （history/005、006、007，及拉模式 arXiv search 建 URL）。每次憑記憶重來。
- 新：固化為 domain 技能 `knowledge/skills/evaluate-and-add-source/SKILL.md`，並投影
  （symlink）到 `.claude/skills/evaluate-and-add-source`，現在就可用。

## 為什麼變
knowie-next／judge 連續多次把它標為 skill candidate（重複手動操作 → 該 skill 化）。
固化後，下次加來源不必重造流程，也把「先實測再加、留因果」的必要摩擦鎖進步驟。

## 影響
- 來源 = `knowledge/skills/`（真理來源）；投影 = `.claude/skills/` 的 per-skill symlink
  （fresh clone 後 judge §5 會重新確保投影）。
- 技能內容為 KnowField 專屬（DEFAULT_SOURCES 在 `src/knowfield/cli/fetchers.py`）。

## 待辦（另記）
- 真實後端散文忠實度抽查仍待做——API 額度 `allocation_quarantined`（403）尚未解除
  （2026-07-23 再測仍隔離）。解除後執行，見 experience 教訓 2、history/010。
  **（後續：同日稍後隔離解除，抽查已完成並通過，見 `history/012`。此待辦關閉。）**

## 狀態
✅ 已採用
