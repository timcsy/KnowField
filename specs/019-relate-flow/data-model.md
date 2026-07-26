# Data Model：forward-pass 接每日流

**不改 schema、不新增資料表。** 僅擴充兩個記憶體 view/model 欄位。

## 變更

### `DigestEntry`（models）— 追加欄位
| 欄位 | 型別 | 說明 |
|------|------|------|
| `entry_id` | `int \| None = None` | 對應 `digest_entries.id`；`get_last_digest` 填入，供關聯按鈕。尾端預設，不破壞既有建構。 |

### `PageEntry`（views）— 追加欄位
| 欄位 | 型別 | 說明 |
|------|------|------|
| `entry_id` | `int \| None = None` | 由 `entry_to_page` 以 `getattr(entry,"entry_id",None)` 帶出；`None`（如 pull 條目）→ 模板不顯示關聯鈕。 |

## 沿用（不變）
- `digest_entries` 表（含 `id`、`article_headline`、`article_body`、`url`）。
- `CorpusEntry`、`FieldRelation`、`why_nodes`、`entry_embeddings`——全 spec 018 既有，不動。

## 讀取契約
- `get_entry_material(entry_id) -> (headline_or_title: str, body: str, url: str) | None`
  以 `digest_entries.id` 取任一條目（種子 or 流）；`headline_or_title = article_headline or title`；不存在→`None`。
