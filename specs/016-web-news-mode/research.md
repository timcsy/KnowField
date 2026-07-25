# Research：web 活水 news 模式（階段 13 增量 b）

## R1：向後相容的簽名擴充
- **決策**：`WebSearch.search(query, *, news: bool=False, time_range: str|None=None)`——**keyword-only、
  預設不變**。所有既有呼叫（`SmartSearch`、`/search`）不帶參數 → 一般搜尋，零改、零回歸。
- **理由**：只有 `WebSearchAdapter` 明確帶 `news=True`；其餘沿用預設＝一般搜尋（FR-002/004）。

## R2：Tavily news 參數
- **決策**：`ApiWebSearch.search` 於 `news=True` 時，payload 加 `topic="news"`；`time_range` 有值
  （如 "week"/"day"/"month"）時加 `time_range`。一般模式 payload 不變（不送 topic/time_range）。
- **理由**：Tavily 支援 `topic="news"`＋`time_range` 回近期新聞。不支援的相容服務會忽略未知參數
  （寬鬆退回一般結果，邊界情況）。poster 可注入驗 payload 帶對參數（教訓 1）。

## R3：StubWebSearch 相容
- **決策**：`StubWebSearch.search` 加同 keyword-only 參數但**忽略**——回固定假結果、行為不變。
- **理由**：離線可測；news 模式在離線下不改行為（無真實新聞源，測 payload 由 ApiWebSearch 驗）。

## R4：WebSearchAdapter 帶 news
- **決策**：`WebSearchAdapter.__init__(source_id, web_search, queries, *, news=True, time_range=None)`；
  `fetch` → `self.web_search.search(q, news=self.news, time_range=self.time_range)`。
  `build_adapters` 建 web 源時 `news=True, time_range=config.search_news_time_range`。
- **理由**：digest 活水要時效新聞（US1）；手動 `/search` 的 `SmartSearch` 不經此 adapter，維持一般。

## R5：config
- **決策**：`config.search_news_time_range`（`LEARNNEWS_SEARCH_NEWS_RANGE`，預設 "week"）。可 "day"/"month"。
- **理由**：US3 時間範圍可調；"week" 是「剛紅」的合理窗。

## R6：失敗與相容
- **決策**：news 搜尋失敗照舊 `SourceUnavailable`（`_http_post_json` 既有）→ digest 攔成 missing。
  服務不支援 news 參數 → 多回一般結果（不因多送參數而失敗）。
- **理由**：沿用既有攔截（教訓 3）；寬鬆相容（邊界）。
