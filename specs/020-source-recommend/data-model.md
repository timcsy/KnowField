# Data Model：場驅動來源推薦

**不改 schema、不新增資料表。** 推薦候選為**短暫記憶體物件**（不落庫，除非人訂閱→走既有 `sources`）。

## 新實體

### `CandidateSource`（`sources/recommend.py`，記憶體）
| 欄位 | 型別 | 說明 |
|------|------|------|
| `domain` | `str` | 候選網域（去 www） |
| `homepage` | `str` | `https://<domain>/` |
| `feed_url` | `str \| None` | 驗證通過的 feed；無→None |
| `name` | `str` | 站名（feed 標題或網域） |
| `reason` | `str` | 繁中推薦理由（依最強命中訊號） |
| `field_score` | `float` | 對場（種子＋冊封根因）的 cosine 最大值；無 attractor→0 |
| `list_hits` | `int` | 跨搜尋結果重複出現次數（跨清單訊號） |
| `has_feed` | `bool` | 是否有驗證通過的活 feed（決定可否訂閱） |
| `already_subscribed` | `bool` | 是否已在名冊（`_source_id` 命中 `list_sources`） |

## 沿用（不變）
- `sources` 表與 `Source`（訂閱後落此，走既有 `/sources/add`→`upsert_source`）。
- `list_field_attractors()`、`ensure_embeddings`、`cosine`、`SearchResult`——全既有，不動。

## 排序契約
- key＝`(field_score, has_feed, list_hits)` 由大到小；取前 `source_recommend_limit`（預設 8）。
