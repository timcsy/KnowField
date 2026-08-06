# Tasks：web 活水 news 模式（只回近期新聞）

**功能目錄**：`specs/016-web-news-mode/`　｜　**TDD 強制**　｜　基準測試：260（不回歸）

依 spec 的 US 分期。`[P]`＝可並行（不同檔、無未完成相依）。

## Phase 1：Setup

- [x] T001 唯讀盤點：`search/websearch.py`（`WebSearch`/`StubWebSearch`/`ApiWebSearch`/`_http_post_json`）、
  `sources/websearch_adapter.py`、`cli/fetchers.py` web_search 分支、`search/smart.py`（`/search` 呼叫）、`config`。

## Phase 2：US1/US2 搜尋後端 news 模式（P1，核心）

> 獨立測試：ApiWebSearch news payload 帶 topic/time_range；一般不帶；Stub 相容。

### 測試先行（TDD）
- [x] T002 [P] [US1] `tests/unit/test_websearch.py` 追加：`ApiWebSearch.search(q, news=True,
  time_range="week")`（注入 poster）→ payload 含 `topic="news"`＋`time_range="week"`。
- [x] T003 [P] [US2] `tests/unit/test_websearch.py` 追加：`ApiWebSearch.search(q)`（一般）→ payload
  **不含** `topic`/`time_range`（向後相容）；`StubWebSearch.search(q, news=True, time_range="day")`
  → 回固定結果、不拋（相容忽略）。

### 實作
- [x] T004 [US1] `search/websearch.py`：`WebSearch` Protocol 與 `StubWebSearch.search` 加
  `*, news=False, time_range=None`（Stub 忽略）；`ApiWebSearch.search` 於 `news=True` 加
  `topic="news"`、`time_range` 有值加 `time_range`。
- [x] T005 [US1] `config.py`：加 `search_news_time_range`（"week"），`from_env` 讀
  `KNOWFIELD_SEARCH_NEWS_RANGE`。

## Phase 3：US1/US3 活水走 news、時間範圍可調（P1/P2，接管線）

> 獨立測試：WebSearchAdapter 傳 news；build_adapters 帶 config 時間範圍。

### 測試先行
- [x] T006 [P] [US1] `tests/unit/test_websearch_adapter.py` 追加：`WebSearchAdapter(..., news=True,
  time_range="week")`（注入記錄用 web_search）→ `fetch` 時 search 收到 `news=True, time_range="week"`；
  預設 `news=True`。

### 實作
- [x] T007 [US1] `sources/websearch_adapter.py`：`__init__` 加 `*, news=True, time_range=None`；
  `fetch` → `search(q, news=self.news, time_range=self.time_range)`。
- [x] T008 [US1] `cli/fetchers.py`：build_adapters web_search 分支建
  `WebSearchAdapter(..., news=True, time_range=config.search_news_time_range)`。

## Phase 4：Polish

- [x] T009 [P] 更新 `docs/usage.md`：web 活水 news 模式（近期新聞、時間範圍可調、/search 維持一般）。
- [x] T010 全套 `uv run pytest` 綠、不回歸（≥260＋新測）；快速手測。
- [ ] T011 真跑抽查（可選，留使用者）：重新整理看 web 活水是否改回近期新聞（少 SEO 清單文）。

## 相依與 MVP

- **相依**：T004 → T007 → T008；T005 → T008。測試（T002/3/6）先於實作。
- **MVP**：Phase 2（後端 news payload）＋Phase 3（adapter 走 news）＝可交付。
- **並行**：T002/T003（websearch unit）、T006（adapter unit）各 `[P]`。
- **範圍守恆**：**不改 /search 手動搜尋、無客端日期過濾、無興趣驅動查詢、無多供應商對映**；
  向後相容（news 預設關）、零 schema、零新相依。
