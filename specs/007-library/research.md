# Phase 0 Research：知識庫管理 技術決策

## R1：每日流唯讀——由 repo 方法結構保證（非靠 UI）

- **Decision**：新增的 `list_seeds`／`delete_seed`／`set_seed_class` **一律加 `WHERE digest_id =
  種子容器 id`**（`get_or_create_seeds_digest()`，spec 006 哨兵 `date=SEEDS_DATE`）。刪除/重分類
  傳入的 `entry_id` 若不屬種子容器 → **不動作**（回 False）。
- **Rationale**：FR-005「每日流唯讀」若只靠「UI 不顯示流」不夠——惡意/錯誤的 POST 仍可能帶
  流的 entry_id。**把保護做進資料層**（教訓 7 的同型：保證做進程式，不靠上層自律）。
- **Alternatives rejected**：只在 web 層擋——繞過即失守。

## R2：刪除連清嵌入——交易式無孤兒（FR-003、教訓 8）

- **Decision**：`delete_seed(entry_id)`：先確認屬種子容器 → `DELETE FROM digest_entries WHERE
  id=?` ＋ `DELETE FROM entry_embeddings WHERE entry_id=?`，同一交易 commit。
- **Rationale**：孤兒向量會讓 `ask` 檢索到已刪內容或報錯。刪除必連清（教訓 8 免動已出貨表的
  另一面——動它就動乾淨）。
- **注意**：`entry_embeddings.entry_id` 對 `digest_entries.id`；種子刪除後其向量一併清。

## R3：重分類即時生效（FR-004）

- **Decision**：`set_seed_class(entry_id, cls)` 改 `digest_entries.source_class`。`ask` 檢索**每次
  即時讀 `source_class` 算權重**（spec 006 `RagService`）→ **天然即時跟上**，無需重嵌/重算。
- **Rationale**：權重是查詢時算的，改分類下次問答就生效，零額外工。
- **cls 值域**：`'explainer'`／`'ordinary'`（與 spec 006 一致）；其他值拒絕。

## R4：復用 CorpusEntry 與 /interests CRUD 樣式（YAGNI）

- **Decision**：`list_seeds` 回既有 `CorpusEntry`（已含 entry_id/title/url/headline/source_class/
  digest_date）。web 照 `/interests`：`GET /library` 列出、`POST /library/remove`（entry_id）、
  `POST /library/reclassify`（entry_id＋目標類）→ 操作後 `RedirectResponse('/library', 303)`。
- **Rationale**：模式現成、測試現成樣式；無新 service（repo 方法即足）、無新 schema。

## R5：無回收桶／復原（YAGNI）

- **Decision**：刪除即刪（刻意操作）；本增量不做回收桶/undo。
- **Rationale**：個人工具、種子可重新 `ingest`；回收桶是額外狀態，YAGNI。日後要再議。

## R6：測試策略（離線純 CRUD）

- **Decision**：unit 測 repo 三方法（含「刪流的 entry_id → 不動作」的安全測）；contract 測 web
  路由（種入種子＋每日匯整 → `/library` 只列種子、刪除生效、重分類後 `ask` 權重變、每日流不現身）。
  全離線（HashingEmbedder＋Stub，零外部呼叫）。
