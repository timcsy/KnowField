# Data Model：智慧搜尋

**不新增資料表**（教訓 8）。以下為記憶體中的短暫型別，一律不落庫。

## SmartResult（新，`search/smart.py`）
一次智慧搜尋的產出。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `overview` | `str` | 整理重點文字（含 `[n]`）；`no_material` 時為「沒有相關材料」訊息 |
| `sources` | `list[Source]` | 整理引用的來源（`n`↔排序後第 n 則），復用 `rag.types.Source` |
| `no_material` | `bool` | 整理無可用材料（grounded 判定）→ 不出 sources |
| `results` | `list[SearchResult]` | **排序後**的完整結果清單（沿用 spec 009 `SearchResult`） |
| `overview_error` | `str \| None` | 整理階段失敗時的友善繁中訊息（結果仍在 `results`） |

## 復用型別（不改）
- `search.websearch.SearchResult`：`title`／`url`／`snippet`（spec 009）。
- `rag.types.CorpusEntry`：passages 轉接用（`entry_id` 佔位＝排序後序位、不寫 DB）。
- `rag.types.Source`：`n`／`title`／`url`。

## 資料流（run(query)）
```
query
  └─ web_search.search(query) → results[]            # spec 009
  └─ 對每則 embed(title+snippet)，cosine vs embed(query) → 排序 results   # R2
  └─ 取排序後 top-N：對每則 fetch_url(url) 抓內文（失敗→snippet）        # R3/R5
       └─ 包成 CorpusEntry(entry_id=n, title, url, body=內文/snippet)
  └─ answerer.answer(query, passages, "繁體中文") → overview 文字        # R3
  └─ _is_no_material(overview)? → no_material=True、清空 sources          # R4
  └─ 回 SmartResult(overview, sources=[Source(n,title,url)…], results=排序後全部)
```
排序後**完整清單**都給頁面（每則可收進）；整理只吃前 N。`[n]` 編號＝排序後序位 → 捲到 `#res-n`。

## 狀態/不變式
- **不落庫**：SmartResult 任何欄位都不寫 DB；只有使用者對某則按「收進」才經既有 ingest 成種子。
- **grounded**：`overview` 只源自 passages；`no_material` 時不列 sources（避免「說沒材料卻列來源」矛盾）。
- **排序穩定**：cosine 同分時保持搜尋後端原序（stable sort）。
