# Data Model：live web 活水

**不新增資料表、不改既有表**（教訓 8）。web 源＝`sources` 表既有結構的一列。

## WebSearchAdapter（新，`sources/websearch_adapter.py`）
- 繼承 `SourceAdapter`；`__init__(source_id, web_search, queries: list[str])`。
- `fetch(since) -> list[Item]`：每 query `web_search.search(q)` → 映
  `Item(source_id="web", external_id="", title=r.title, url=r.url, abstract=r.snippet)` → 依 url 去重
  → `_finalize`。搜尋拋 `SourceUnavailable` → 向外拋（digest 攔）。

## 預設源（`DEFAULT_SOURCES` 加一列，既有 Source 結構）
`Source("web-ai-trends", "開放網路 AI 趨勢（需搜尋金鑰・opt-in）", "news", "web_search",
 endpoint=<換行分隔查詢>, enabled=False)`

## build_adapters 簽名變更
`build_adapters(sources, config=None) -> list[SourceAdapter]`
- `web_search` 源：config＋金鑰齊 → 建 `WebSearchAdapter`；否則跳過（FR-003）。

## 復用型別（不改）
- `models.Item`（title/url/abstract…）、`search.websearch.SearchResult`／`WebSearch`。

## 不變式
- **金鑰閘**：無 config／無搜尋金鑰 → 不建 web adapter、零搜尋（FR-003）。
- **opt-in**：`web-ai-trends` 預設 `enabled=False`。
- **流非種子**：web `Item` 進 `digest_entries`（當日流），**不進種子容器**；要留靠「收進」（原則 5）。
- **失敗→缺漏**：搜尋失敗 → `missing_sources` 標示、digest 照常（教訓 3、憲章 V）。
- **去重**：跨 query 依 url 去重。
