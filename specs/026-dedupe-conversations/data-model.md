# Data Model: 既有重複對話清理

**無結構變更**——不新增表/欄。只**刪多餘 `conversations` 列**＋**UPDATE `why_nodes.conversation_id`**（重指）。

## 純值：DedupePlan（`chat/capture.py`，不落庫）
`plan_dedupe(convos, provenance) -> DedupePlan`：
- 輸入：`convos`＝`[{"id": int, "messages": list}, …]`；`provenance`＝`{why_node_id: conversation_id}`。
- 依 `conversation_fingerprint(messages)` 分組；每組（>1 份）：
  - `survivor`＝該組 id 最大者；`losers`＝其餘 ids。
  - `repoint`：對每個 `wid` 其 `provenance[wid] ∈ losers` → `wid → survivor`。
- 回 `DedupePlan`：
  - `delete_ids: list[int]`（所有組的 losers）
  - `repoint: dict[int,int]`（`wid → survivor_cid`）
  - `n_groups: int`（有重複的組數）、`n_extra: int`（＝len(delete_ids)）、`n_roots: int`（＝len(repoint)）
- 無重複 → 空計畫（`delete_ids=[]`, `repoint={}`, 三數皆 0）。

## 既有實體（動作對象）
- **對話 Conversation**：同指紋多份 → 留 survivor、刪 losers。
- **根因 WhyNode.conversation_id**：指向 loser 者 → UPDATE 為 survivor。**主張／階梯不碰**。
- **provenance**：清理後由 `why_nodes.conversation_id` 產生，每條原有由來仍映到 survivor。

## 不變量
- **非破壞**：只併同指紋（內容完全相同）；異指紋份數不變。
- **不改根因語意**：只動 `conversation_id`，不碰 claim/ladder/evidence。
- **不孤兒**：重指後刪 loser；每條原有由來的根因仍連得到 survivor。
- **預覽唯讀**：算計畫（`plan_dedupe`／`dedupe_plan`）不寫庫；只有確認後 `apply_dedupe` 才寫。
