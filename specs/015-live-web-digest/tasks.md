# Tasks：live web 活水（開放網路進每日 digest）

**功能目錄**：`specs/015-live-web-digest/`　｜　**TDD 強制**　｜　基準測試：249（不回歸）
**設計源**：`draft/2026-07-24-趨勢熱詞發現.md`(live 活水段)、`concepts/有吸引子的場.md`（反濾泡）

依 spec 的 US 分期。`[P]`＝可並行（不同檔、無未完成相依）。

## Phase 1：Setup

- [x] T001 唯讀盤點復用點：`sources/base.py` `SourceAdapter`＋`_finalize`、`cli/fetchers.py`
  `build_adapters`／`_ADAPTERS`／`DEFAULT_SOURCES`、`search/websearch.py` `WebSearch`／`StubWebSearch`／
  `make_web_search`、`models.Item`、`digest/builder.py`（`except SourceUnavailable`→missing）、
  `web/app.py` refresh／pull／`cli/digest_cmd.py` 的 `build_adapters` 呼叫。

## Phase 2：US1/US3 WebSearchAdapter（P1，核心）

> 獨立測試：`WebSearchAdapter(StubWebSearch, queries).fetch()` → Items（映射/去重）；失敗向外拋。

### 測試先行（TDD）
- [x] T002 [P] [US1] `tests/unit/test_websearch_adapter.py`：`WebSearchAdapter(StubWebSearch(), ["q1","q2"])`
  `.fetch(datetime(1970,1,1))` → 回 `Item` 清單、每則有 url、`SearchResult`→`Item` 欄位對映
  （title/url/abstract=snippet）、**依 url 去重**。
- [x] T003 [P] [US4] `tests/unit/test_websearch_adapter.py` 續：注入會拋 `SourceUnavailable` 的
  web_search → `fetch` **向外拋**（不吞）。

### 實作
- [x] T004 [US1] 新增 `src/learnnews/sources/websearch_adapter.py`：`WebSearchAdapter(SourceAdapter)`
  ——`__init__(source_id, web_search, queries)`；`fetch(since)` 每 query `search()`→ 映 `Item`
  （source_id="web"）→ 依 url 正規化去重 → `_finalize`；搜尋拋 `SourceUnavailable` 向外拋。

## Phase 3：US2 opt-in 金鑰閘＋預設源（P1，接管線）

> 獨立測試：build_adapters 有無金鑰的建/跳；預設源停用；run_digest 帶 web adapter → 匯整含 web 材料。

### 測試先行
- [x] T005 [P] [US2] `tests/unit/test_build_adapters_web.py`：`build_adapters([web源], config=無金鑰)` →
  **不含** web adapter；`config=有金鑰` → **含**；`build_adapters([web源])`（無 config）→ 不含。
- [x] T006 [P] [US2] `tests/unit/test_build_adapters_web.py` 續：`web-ai-trends` 在 `DEFAULT_SOURCES`
  且 `enabled=False`（預設停用）；`_parse_queries` 換行/逗號分隔正確。
- [x] T007 [P] [US1/US3] `tests/contract/test_live_web_digest.py`：`run_digest(repo,
  adapters=[WebSearchAdapter(StubWebSearch,…), 一般 stub adapter], date, limit)` → 匯整 `entries`
  **含 web 材料**（title/url 對得上）、web 材料**在 `digest_entries`（流）不在種子容器**。
- [x] T008 [P] [US4] `tests/contract/test_live_web_digest.py` 續：`run_digest` 帶會拋
  `SourceUnavailable` 的 web adapter → 匯整**照常產出**、`missing_sources` 含該源 id。

### 實作
- [x] T009 [US2] `cli/fetchers.py`：`build_adapters(sources, config=None)`——`web_search` 特例
  （config＋金鑰齊→建 `WebSearchAdapter(s.id, make_web_search(config), _parse_queries(s.endpoint))`，
  否則跳過）；加 `_parse_queries`；`DEFAULT_SOURCES` 加 `web-ai-trends`（enabled=False）。
- [x] T010 [US2] 呼叫處傳 config：`cli/digest_cmd.py` handle、`web/app.py` `_default_digest_refresh`
  → `build_adapters(sources, config)`；`web/app.py` pull → 維持 `build_adapters(sources)`（跳過 web）。

## Phase 4：Polish

- [x] T011 [P] 更新 `docs/usage.md`：開放網路 AI 趨勢源（opt-in、需金鑰、治追不到剛紅、流非種子）。
- [x] T012 全套 `uv run pytest` 綠、不回歸（≥249＋新測）；快速手測（離線 stub adapter 進 digest）。
- [ ] T013 真跑抽查（可選，留使用者）：/sources 啟用該源＋金鑰 → refresh，看 Opus 5 這類是否進匯整。

## 相依與 MVP

- **相依**：T004 → T009 → T010；測試（T002/3/5/6/7/8）先於實作。
- **MVP**：Phase 2（adapter）＋Phase 3（build_adapters 金鑰閘＋預設源＋run_digest 整合）＝可交付。
- **並行**：unit（T002/3/5/6）、contract（T007/8）各 `[P]`（同檔內順序）。
- **範圍守恆**：**無自動變種子、無竄升/成核、無 LLM 查詢擴展、無串流、無硬抓 Threads/X、無興趣驅動
  查詢**；不新增/不改資料表。
