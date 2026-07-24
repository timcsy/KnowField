# Phase 1 Data Model：RAG 問答 MVP

## 新增儲存：`entry_embeddings` 表

```sql
CREATE TABLE IF NOT EXISTS entry_embeddings (
    entry_id INTEGER NOT NULL,      -- → digest_entries.id
    tag TEXT NOT NULL,              -- embedder 身分：'hashing-256' / 'openai-<model>'
    dim INTEGER NOT NULL,           -- 向量維度（驗證用）
    vector_json TEXT NOT NULL,      -- JSON 陣列（float）
    PRIMARY KEY (entry_id, tag)
);
```

- 一則條目對每種 embedder 各存一列，空間不混比。
- `INSERT OR REPLACE` 落庫；查詢以 `(entry_id, tag)` 命中。

## 資料流（一次 `ask`）

```
list_corpus_entries(today) ─► [CorpusEntry...]
   └─ ensure_embeddings(entries, embedder, tag):
        缺 (entry_id,tag) 的 → embed_many(其文字) → save_entry_embedding  (批次)
embedder.embed(question) ─► qvec
cosine(qvec, each entry.vec) ─► 排序 ─► 濾 < rag_min_score ─► top-k
   ├─ 空 → RagAnswer(no_material=True)
   └─ 非空 → answerer.answer(question, passages, lang) ─► RagAnswer(text, sources)
```

## 記憶體實體（dataclass）

### `CorpusEntry`（檢索單位）
| 欄位 | 型別 | 說明 |
|---|---|---|
| entry_id | int | `digest_entries.id` |
| title | str | 原文標題 |
| url | str | 原文連結（溯源） |
| headline | str | 整理過標題 |
| body | str | 消化散文 |
| digest_date | str | 所屬匯整日期 |
| embed_text() | str | `headline\nbody`（空 body 退回 title） |

### `Source`（被引用來源）
| 欄位 | 型別 | 說明 |
|---|---|---|
| n | int | 引用編號（對應答案裡 `[n]`） |
| title | str | 標題 |
| url | str | 原文連結 |

### `RagAnswer`（回傳）
| 欄位 | 型別 | 說明 |
|---|---|---|
| text | str | 繁中答案（含 `[n]` 標註）；`no_material` 時為空 |
| sources | list[Source] | 實際檢索到、傳入合成的來源（程式端生成） |
| no_material | bool | 查無相關 → True，且不呼叫合成後端 |

### `Scope`
- `today: bool`（預設 False＝累積全部；True＝最近一份匯整）

## Repository 新增方法

- `list_corpus_entries(today: bool=False) -> list[CorpusEntry]`
- `get_entry_embedding(entry_id: int, tag: str) -> Vector | None`
- `save_entry_embedding(entry_id: int, tag: str, vec: Vector) -> None`（INSERT OR REPLACE）
- `ensure_embeddings(entries, embedder, tag) -> dict[int, Vector]`：批次補缺並回傳全表向量
- （`save_digest` 內：對新 entries 批次嵌入並 `save_entry_embedding`，FR-009）

## Answerer 後端

- `Answerer`（Protocol）：`answer(question: str, passages: list[CorpusEntry], lang: str) -> str`
- `StubAnswerer`：離線、grounded、逐點 `[n]`，只用傳入段落。
- `OpenAIAnswerer`：`_post` `/chat/completions`，grounded prompt。
- `make_answerer(config) -> Answerer`：openai↔stub（沿用 factory 樣式）。

## Config 新增

- `rag_top_k: int = 6`
- `rag_min_score: float = 0.10`
- embedder tag 由 embedder 型別推得（`hashing-256` / `openai-<embed_model>`）。
