# Phase 1 Data Model：web 搜尋

## Schema
**無變更**——搜尋結果**不落庫**；「收進」復用種子容器（spec 006）。

## 記憶體實體
### `SearchResult`（`search/websearch.py`，短暫）
| 欄位 | 型別 | 說明 |
|---|---|---|
| title | str | 標題 |
| url | str | 原文網址（收進/溯源用） |
| snippet | str | 摘要 |

### `WebSearch`（協定）：`search(query: str) -> list[SearchResult]`
- `StubWebSearch`：回固定假結果（離線、可測）。
- 真實後端：urllib POST `config.search_api_url`（帶 `search_api_key`）→ 寬鬆解析 title/url/snippet；
  失敗拋 `SourceUnavailable`（繁中）。

## Factory / Config
- `make_web_search(config)`：`search_api_url`＋`search_api_key` 齊 → 真實；否則 `StubWebSearch`。
- `Config`：+`search_api_url`、`search_api_key`（env `LEARNNEWS_SEARCH_API_URL`／`LEARNNEWS_SEARCH_KEY`）。

## Web
- `GET /search?q=`：`web_search_factory(q)`→`search.html`（結果＋每則「收進」表單→`/ingest`）。
- `app.state.web_search_factory`（測試可注入）。導覽加「搜尋」。
- 「收進」＝既有 `POST /ingest`（ref=url），零新後端碼。
