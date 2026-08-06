# Contracts: 既有重複對話清理

## A. 純核心（`src/knowfield/chat/capture.py`）

### `plan_dedupe(convos: list[dict], provenance: dict) -> DedupePlan`
- `convos`＝`[{"id","messages"}]`；`provenance`＝`{wid: cid}`。依 `conversation_fingerprint` 分組。
- 每組 >1：`survivor`＝max id；losers＝其餘。指向 loser 的 wid → repoint 到 survivor。
- 回 `DedupePlan(delete_ids, repoint, n_groups, n_extra, n_roots)`。空/無重複 → 全空、三數 0。
- 純函式、無副作用、離線可測；缺欄位（無 messages）視為空內容、不崩。

## B. Repository 契約（`src/knowfield/store/repository.py`）

### `dedupe_plan() -> DedupePlan`（唯讀）
- 讀 `list_conversations()`（取 id＋messages）＋`why_node_provenance()`；呼叫 `plan_dedupe`；回計畫。**不寫庫**。

### `apply_dedupe() -> dict`（人確認後）
- 重算 `dedupe_plan()`；對 `repoint` 每筆 `UPDATE why_nodes SET conversation_id=survivor WHERE id=wid`；
  `DELETE FROM conversations WHERE id IN delete_ids`；commit。回摘要 `{"groups","removed","repointed"}`。
- **不改任何 why_node 的 claim/ladder/evidence**；不動異指紋份。

## C. Web 契約（`src/knowfield/web/app.py`＋模板）

### `GET /conversations/dedupe` → 預覽（唯讀）
- 算 `dedupe_plan()`；渲染 `dedupe.html`：「發現 N 組重複、共 M 份多餘、K 條根因將重指」＋「確認清理」(POST)＋「取消」(回 /conversations)。
- 無重複 → 顯示「沒有重複可清」（無確認鈕）。**不動資料**（守衛測）。

### `POST /conversations/dedupe` → 執行（人確認）
- `apply_dedupe()`；`RedirectResponse('/conversations?cleaned=1&removed=M', 303)`；`/conversations` 顯示結果 flash「已清理：併掉 M 份多餘、重指 K 條根因」。

### `conversations.html`
- 頁首加「🧹 清理重複對話」鈕（連 `GET /conversations/dedupe`）；讀 `cleaned`/`removed` query 顯示成功 flash。

## D. 測試契約

- **單元**（`test_capture_core.py` 擴）：`plan_dedupe`——3 組各數份→delete_ids/n_extra 正確、survivor=max id；repoint 只含指向 loser 者；異指紋不入計畫；空/無重複→全空；未連根因的多餘份仍列入 delete。
- **web**（`test_dedupe_web.py`）：
  - `GET /conversations/dedupe` 顯示 N/M/K、且**資料未變**（人閘門守衛）。
  - `POST` 後：同組留 1（max id）、指向 loser 的根因 provenance 改指 survivor、異指紋份數不變、根因 claim 不變。
  - 空庫／無重複 → 友善「沒有重複可清」、不崩。
