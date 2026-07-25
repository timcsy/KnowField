# Contract：web 活水 news 模式

## `WebSearch.search(query, *, news=False, time_range=None) -> list[SearchResult]`
- keyword-only 可選參數，**預設一般搜尋**（向後相容）。
- `StubWebSearch`：接受並**忽略** news/time_range（行為不變）。
- `ApiWebSearch`：`news=True` → payload 加 `topic="news"`；`time_range` 有值 → 加 `time_range`；
  一般模式 payload 不含這兩鍵。

## `WebSearchAdapter(source_id, web_search, queries, *, news=True, time_range=None)`
- `fetch` → `web_search.search(q, news=self.news, time_range=self.time_range)`。

## `build_adapters(sources, config)`（web_search 分支）
- 建 `WebSearchAdapter(..., news=True, time_range=config.search_news_time_range)`。

## `config.search_news_time_range`（預設 "week"）

## 契約測試（離線、零外部呼叫）
1. `ApiWebSearch.search(q, news=True, time_range="week")`（注入 poster）→ payload 含 `topic="news"`
   ＋`time_range="week"`。
2. `ApiWebSearch.search(q)`（一般）→ payload **不含** `topic`/`time_range`（向後相容）。
3. `StubWebSearch.search(q, news=True, time_range="day")` → 回固定結果、不拋（相容忽略）。
4. `WebSearchAdapter(..., news=True, time_range="week")`（注入記錄用 web_search）→ `fetch` 時
   search 收到 `news=True, time_range="week"`。
5. `WebSearchAdapter(...)` 預設 → `news=True`（digest 活水預設 news）。
6. **一般搜尋不變**：`SmartSearch`（`/search`）用的 `web_search.search(query)` 不帶 news → 一般模式
   （既有 SmartSearch/搜尋測試不回歸）。
