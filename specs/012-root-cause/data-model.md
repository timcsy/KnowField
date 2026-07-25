# Data Model：根因萃取

## 新表 `why_nodes`（`store/schema.py`，CREATE IF NOT EXISTS＋_migrate 冪等）
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | why-node id |
| `claim` | TEXT NOT NULL | 根因主張（一段話） |
| `evidence_urls` | TEXT（JSON 陣列） | 證據原文連結（來源種子 url）；不可為空才可冊封 |
| `touchstones` | TEXT（JSON） | 試金石逐條 `[{name, passed}]` |
| `fog_flag` | INTEGER（0/1） | 是否有霧詞 |
| `status` | TEXT | `'candidate'`（候選）｜`'anointed'`（已冊封） |
| `source_entry_id` | INTEGER | 來源種子的 digest_entries.id |
| `created_at` | TEXT | 建立時間（由呼叫端傳入，不用 Date.now 於核心） |

**不動既有表**（digest_entries／entry_embeddings／seeds 容器不改結構）。

## `Candidate`（`rootcause/extract.py`，記憶體）
`{claim:str, touchstones:list[{name:str, passed:bool}], fog_flag:bool, evidence:list[str], no_material:bool}`
- 7 條試金石 `name`：預測力／反事實／機制／壓縮／可重導／追問不撞牆／多源三角。
- `no_material=True` → 抽不出有把握的根因，不建候選。

## Repository 方法
- `add_why_node(claim, evidence_urls, touchstones, fog_flag, source_entry_id, created_at) -> id`（status='candidate'）。
- `list_why_nodes(status=None) -> list[WhyNode]`。
- `anoint_why_node(id, claim=None) -> bool`（可改 claim；status→'anointed'）。
- `delete_why_node(id) -> bool`（連 `entry_embeddings WHERE entry_id=-id` 一併清）。
- `list_corpus_entries` UNION：`status='anointed'` → `CorpusEntry(entry_id=-id, title="根因：…", url=證據0,
  body=claim, source_class="root")`。

## RagService 權重
- `_weight("root")=rag_root_weight（2.0）` > `_weight("explainer")=1.5` > 其餘 1.0。

## 不變式
- **候選 ≠ 冊封**：只有 `anointed` 進 corpus／被 ask 檢索；候選不影響問答。
- **grounding**：候選必帶 evidence＋touchstones，否則不可冊封（程式保證）。
- **不自動轉正**：無 candidate→anointed 的自動路徑；只有 web 冊封動作。
- **負 id 不碰撞**：why-node 的 CorpusEntry.entry_id 恆負，與 digest_entries 正 id 不衝突。
