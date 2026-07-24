# Phase 1 Data Model：種子 ingest 增量 2a

## Schema 變更

### `digest_entries` 加一欄
```sql
ALTER TABLE digest_entries ADD COLUMN source_class TEXT DEFAULT 'ordinary';
-- 'ordinary'（每日匯整、一般種子）| 'explainer'（解說文種子，高品質）
```
（既有列預設 `'ordinary'`，不影響增量 1。）

### 種子容器 digest（哨兵，非 schema 變更）
- 一列 `digests(date='__種子__')`，`get_or_create` 取得其 id；種子皆插為它的 `digest_entries`。
- `list_corpus_entries(today=True)` 以 `date != '__種子__'` 排除它。

## 資料流（一次 `ingest`）
```
ref（arXiv-id | url）
  ├ 正規化 → external_id/canonical_url；查種子容器是否已存 → 是則「已在庫」結束
  ├ fetch_arxiv_by_id / fetch_url（http_get 可注入）→ Item（title, abstract, url）
  ├ ArticleBuilder.build(item, matched_topic='', with_image=False) → Article
  │    （任一步失敗 → SourceUnavailable/OpenAIError，不寫入）
  ├ repo.ingest_seed(item, article, source_class) → 存入種子容器（回 entry_id）
  └ repo.ensure_embeddings([該 entry], embedder, tag)  批次嵌入落庫
之後 ask 沿用增量 1：list_corpus_entries(累積) 撈到種子 → 加權排序 → 合成可溯源答案
```

## 記憶體實體

### `CorpusEntry`（增量 1 既有，+1 欄）
| 欄位 | 型別 | 說明 |
|---|---|---|
| entry_id | int | `digest_entries.id` |
| title / url / headline / body / digest_date | … | （不變） |
| **source_class** | str | `'ordinary'` \| `'explainer'`（新增，決定檢索權重） |

### `Item`（既有，複用）：種子抓取結果（source_id='seed'、external_id=正規化 id、title、abstract、url）
### `Article`（既有，複用）：消化產出（body、headline、source_url）

## Repository 新增／改動
- `get_or_create_seeds_digest() -> int`：取得哨兵種子容器 id（無則建）。
- `seed_exists(external_id, url) -> bool`：以 `content_hash` 查種子容器內是否已存（去重）。
- `ingest_seed(item, article, source_class) -> int`：插入一筆種子 entry，回 `entry_id`。
- `list_corpus_entries(today)`：SELECT 加 `source_class`；`today=True` 加 `WHERE date != '__種子__'`。

## RagService 改動
- 排序：`weighted = cosine(qvec, vec) * _weight(e.source_class)`；`_weight('explainer')=
  config.rag_explainer_weight`（預設 1.5），其餘 1.0。
- 門檻：入選條件仍 `cosine >= min_score`（**原始 cosine**，非加權）；權重只排序入選者。

## Config 新增
- `rag_explainer_weight: float = 1.5`（env `LEARNNEWS_RAG_EXPLAINER_WEIGHT`）
- `SEEDS_DATE = '__種子__'` 哨兵常數。

## Fetch（`seed/fetch.py`）
- `fetch_arxiv_by_id(arxiv_id, http_get) -> Item`（id_list API＋複用 Atom 解析）
- `fetch_url(url, http_get) -> Item`（stdlib html.parser 淺抽 title＋主文）
- `normalize_arxiv_id(ref) -> str | None`（辨識並抽出裸 id；非 arXiv 回 None → 走 URL）
- `http_get(url) -> str` 預設 urllib；測試注入 fixtures。
