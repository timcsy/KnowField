# Implementation Plan: web 活水 news 模式（只回近期新聞）

**Branch**: `016-web-news-mode` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/016-web-news-mode/spec.md`

## Summary

`WebSearch.search` 加 **keyword-only** 可選參數 `news=False`、`time_range=None`（向後相容）。
`ApiWebSearch` news 模式 → Tavily payload 加 `topic="news"`＋`time_range`。`WebSearchAdapter`
（digest 活水）以 `news=True`＋`config.search_news_time_range`（預設 "week"）呼叫。手動 `/search`
（`SmartSearch`）呼叫維持不帶參數＝一般搜尋、零改。**零 schema、零新相依、既有測試不回歸。**

## Technical Context

- **語言/執行**：Python 3.12＋、uv。核心零相依（urllib）。
- **復用**：`search/websearch.py` `WebSearch`/`StubWebSearch`/`ApiWebSearch`/`_http_post_json`
  （spec 009）、`sources/websearch_adapter.py` `WebSearchAdapter`（spec 015）、`cli/fetchers.py`
  `build_adapters`、`config`。`SmartSearch`（spec 010）呼叫不變。
- **改動**：
  - `WebSearch` Protocol：`search(query, *, news=False, time_range=None)`。
  - `StubWebSearch.search`：加同簽名、**忽略**（行為不變）。
  - `ApiWebSearch.search`：`news=True` → payload `topic="news"`；`time_range` 有值 → payload `time_range`。
  - `WebSearchAdapter.__init__` 加 `news=True`、`time_range=None`；`fetch` → `search(q, news=…, time_range=…)`。
  - `cli/fetchers.build_adapters`：建 web 源時 `news=True, time_range=config.search_news_time_range`。
  - `config.search_news_time_range`（"week"）。
- **測試**：unit（ApiWebSearch news payload；StubWebSearch 相容；WebSearchAdapter 傳 news；一般搜尋
  不帶 news）＋既有全綠。全離線、零外部呼叫。

## Constitution Check

| 憲章／原則 | 檢查 | 結果 |
|---|---|---|
| 根公理 成本要極低 | 撈近期新聞＝真追得到剛紅 | 🟢 正中 |
| concept 反濾泡（近因） | 伸手到名冊外＋抓「剛紅」的近因 | 🟢 |
| 原則 3 溯源 | news 結果一樣帶原文網址 | 🟢 |
| 教訓 1 可插拔離線 stub | Stub 相容、離線可測；poster 驗 payload | 🟢 |
| 教訓 3 外部失敗攔截 | news 失敗沿用 SourceUnavailable→missing（不變） | 🟢 |
| 向後相容 | news/time_range 預設關；`/search` 不動；既有測試不回歸 | 🟢 |
| 憲章 II 全繁中 · IV 零相依 | 全繁中；複用 urllib，不加 pip | 🟢 |

**Gate：通過**，無違憲、無 NEEDS CLARIFICATION。

## Phase 0：research（見 [research.md](./research.md)）
## Phase 1：design（見 [contracts/](./contracts/)／[quickstart.md](./quickstart.md)；無新資料模型）

## 進度
- [x] Phase 0：research.md
- [x] Phase 1：contracts/、quickstart.md
- [ ] Phase 2：tasks.md（`/speckit-tasks`）
