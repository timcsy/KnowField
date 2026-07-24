# Web 契約：`/library`（知識庫管理）

## GET /library
- 回種子清單頁；每則：整理過標題、來源類型（解說文/一般）、收進日期、可點原文連結、
  刪除鈕、重分類鈕（切換解說文↔一般）。
- **只列種子**（種子容器）；每日流條目不出現（FR-005）。
- 無種子 → 空狀態提示（引導去「收進」）（FR-007）。

## POST /library/remove
- Form：`entry_id`。
- `delete_seed(entry_id)`：屬種子容器才刪，連 `entry_embeddings` 清（FR-003）；非種子（每日流/
  不存在）→ 不動作。→ 303 redirect `/library`。

## POST /library/reclassify
- Form：`entry_id`、`source_class`（`explainer`｜`ordinary`）。
- `set_seed_class`：僅種子容器內生效；非法 cls / 非種子 → 不動作。→ 303 redirect `/library`。

## 不變式（對映 FR）
- 每日流唯讀：remove/reclassify 對每日流 entry_id **一律不動作**（repo 層結構保證，FR-005）。
- 刪除無孤兒向量：連 `entry_embeddings` 清（FR-003）；刪後 `ask` 檢索不到（FR-002）。
- 重分類即時：改 `source_class`，下次 `ask` 權重跟上（FR-004）。
- 全繁中（FR-006）；離線可測（FR-008）。

## 退出/狀態
| 情境 | 行為 |
|---|---|
| 正常操作 | 303 → /library（重整看到結果） |
| 空庫 | 200＋空狀態提示 |
| 非種子 entry_id | 靜默不動作（每日流受保護），仍 303 /library |
