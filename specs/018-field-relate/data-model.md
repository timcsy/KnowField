# Data Model：場對新材料做工

**不新增資料表**（教訓 8）。全記憶體短暫、不落庫；**場不自動改**（原則 5）。

## FieldRelation（新，`field/relate.py`）
| 欄位 | 型別 | 說明 |
|---|---|---|
| `kind` | str | `extend`（延伸）｜`contradict`（牴觸）｜`none`（無明顯關聯）｜`nucleate`（成核候選）｜`empty`（場空） |
| `attractor` | CorpusEntry \| None | 最相關的冊封吸引子（種子/根因）；nucleate/empty 為 None |
| `reason` | str | grounded 理由（繁中一句，指出依據）；nucleate/empty 為提示語 |
| `score` | float | 與最近吸引子的 cosine（供顯示/除錯） |

## Relation（`RelationJudge` 回傳，記憶體）
`{kind: "extend"|"contradict"|"none", reason: str}`

## 新方法/類
- `repository.list_field_attractors() -> list[CorpusEntry]`：`list_seeds()` ＋ `_anointed_corpus_entries()`。
- `field/relate.py`：`FieldRelate(embedder, judge, repo, min_score)`；`RelationJudge` Protocol＋
  `StubRelationJudge`／`OpenAIRelationJudge`。
- `backends/factory.make_relation_judge(config)`。

## 復用（不改）
- `list_seeds`／`_anointed_corpus_entries`／`ensure_embeddings`（spec 006/012）、`cosine`、`CorpusEntry`、
  `config.rag_min_score`（近/遠門檻）、`_post`（chat）。

## 不變式
- **不落庫、不改場**：只回 `FieldRelation`；不退根因/不改冊封/不改權重（原則 5）。
- **grounded**：關係只依材料＋該根因主張；無關回 `none`（不硬掰，教訓 7）。
- **排除自己**：材料若為某吸引子，對照時排除它。
- **場空/太短**：`kind="empty"`＋友善提示（不崩）。
