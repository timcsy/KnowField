# Phase 1 Data Model：知識庫管理

## Schema
**無變更**——操作既有 `digest_entries`（種子容器：`digests.date = SEEDS_DATE`）＋`entry_embeddings`。

## Repository 新增方法（皆僅限種子容器）

### `list_seeds() -> list[CorpusEntry]`
```sql
SELECT de.id, de.title, de.url, de.article_headline, de.article_body,
       d.date, de.source_class
FROM digest_entries de JOIN digests d ON de.digest_id = d.id
WHERE d.date = SEEDS_DATE
ORDER BY de.id DESC          -- 新收的在上
```
回 `CorpusEntry`（既有；entry_id/title/url/headline/body/digest_date/source_class）。

### `delete_seed(entry_id) -> bool`
- 確認 `entry_id` 屬種子容器（`digest_id = get_or_create_seeds_digest()`）；不屬 → 回 False（不動作）。
- 同一交易：`DELETE FROM digest_entries WHERE id=?` ＋ `DELETE FROM entry_embeddings WHERE entry_id=?`。
- 回 True（已刪）。

### `set_seed_class(entry_id, cls) -> bool`
- `cls ∈ {'explainer','ordinary'}`，否則回 False。
- `UPDATE digest_entries SET source_class=? WHERE id=? AND digest_id=(種子容器)`；影響列數>0 回 True。

## 資料流

```
GET  /library            → repo.list_seeds() → 渲染清單（標題/類型/日期/原文連結）
POST /library/remove     → repo.delete_seed(entry_id) → redirect /library
POST /library/reclassify → repo.set_seed_class(entry_id, cls) → redirect /library
   （之後 ask 檢索：list_corpus_entries 撈不到已刪種子；重分類後即時算新權重）
```

## 記憶體實體
- **`CorpusEntry`**（既有，復用）：一則種子的展示資料。
- **來源類型**：`'explainer'`（解說文/高品質）｜`'ordinary'`（一般）。

## Web 路由（照 /interests CRUD）
- `GET /library`：`repo.list_seeds()` → `library.html`。
- `POST /library/remove`（Form `entry_id`）：`delete_seed` → 303 `/library`。
- `POST /library/reclassify`（Form `entry_id`＋`source_class`）：`set_seed_class` → 303 `/library`。
- 導覽（base.html）加「知識庫」。
- 皆用既有 `app.state.repo_factory`（測試可注入）。
