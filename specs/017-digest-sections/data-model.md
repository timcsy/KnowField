# Data Model：匯整分區

## `digest_entries` 加欄（SCHEMA＋_migrate ALTER 冪等，不改既有欄）
| 欄位 | 型別 | 說明 |
|---|---|---|
| `source_id` | TEXT DEFAULT '' | 條目來源 id（供分區映射 sources.type）；舊資料為 '' |

## 分類 helper（`web/app.py` 或 helper 模組）
`_section_of(source_type: str | None) -> str`：`"foundational"` if `type in {"paper","blog"}` else `"news"`。

## Repository
- `save_digest`：INSERT 補 `source_id=e.item.source_id`。
- `get_last_digest`：SELECT `source_id` → 回填 `Item.source_id`。

## 首頁 context 變更
- `news_entries`／`foundational_entries`（各 `entry_to_page` 後的清單）；取代原單一 `entries`
  （或並存）。

## 來源類別（既有 sources.type，語意釐清）
- `paper`＝論文（arXiv/HF）→ 基礎。
- `blog`＝**基礎部落格**（ycc/lilianweng）→ 基礎。
- `news`＝新聞媒體/策展/社群/web 活水（TechCrunch/Verge/Ars/Import AI/HN/Reddit/web-ai-trends）→ 新聞。
- **重分類**：`hn-ai`、`reddit-localllama` `blog→news`。

## 不變式
- **只改呈現＋新增欄**：匯整產生（排序/去重/每來源上限）不變（FR-006）。
- **向後相容**：source_id 空/未知 → 新聞區；不崩（FR-005）。
- **溯源不變**：兩區每則帶原文連結（原則 3）。
