# Data Model：探索（多角度擴展）

**不新增資料表**（教訓 8）。全記憶體短暫、不落庫。

## QueryExpander（新，`search/expand.py`）
| 成員 | 型別 | 說明 |
|---|---|---|
| `expand(query)` | `-> list[str]` | 回子角度查詢清單（不含原 query 亦可，由呼叫端補）；失敗回 `[]` |

- `StubQueryExpander`：確定性 `[f"{q} 原理", f"{q} 應用", f"{q} 比較"]`（離線、可測）。
- `OpenAIQueryExpander(base_url, api_key, model, max_n)`：`_post` chat 拆解、逐行解析、上限、
  空/例外回 `[]`。

## SmartSearch（擴充，`search/smart.py`）
- `__init__` 新增 `expander=None`、`max_subqueries=5`。
- `run(query, explore=False)`：`explore=True` 且有 expander → fan-out＋合併去重取得結果池；
  否則單 query（增量 b）。其餘（排序/抓取/整理）**不變**。
- 回傳型別仍為 `SmartResult`（spec 010，不變）。

## 資料流（explore=True）
```
query
 ├─ subs = expander.expand(query)   （失敗→[]）
 ├─ angles = dedup([query] + subs)[:max_subqueries]     # 原 query 必納、上限≤5
 ├─ merged = 合併 每個 angle 的 web_search.search(a)，依 url 正規化去重（留最先）
 └─ SmartSearch 既有管線：排序 → 抓 top-N 內文 → grounded 整理 → SmartResult
```

## 復用型別（不改）
- `SearchResult`（spec 009）、`SmartResult`／`CorpusEntry`／`Source`（spec 010）。

## 不變式
- **不落庫**：子角度、合併池、整理皆不寫 DB；只有「收進」才成種子（原則 5）。
- **成本有界**：`len(angles) ≤ max_subqueries`；抓取則數 ≤ SmartSearch top-N（不隨角度放大）。
- **不劣化**：原 query 永遠在 angles → explore 結果 ⊇ 單 query 結果（去重後）。
- **opt-in**：`explore` 預設 False；False 時零拆解、零多搜。
