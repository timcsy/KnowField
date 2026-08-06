# Tasks：智慧搜尋（搜尋結果的消化＋溯源整理）

**功能目錄**：`specs/010-smart-search/`　｜　**TDD 強制**　｜　基準測試：197（不回歸）

依 spec 的 US 分期；每期可獨立測試交付。`[P]`＝可並行（不同檔、無未完成相依）。

## Phase 1：Setup

- [x] T001 確認復用點就位（唯讀盤點，不改碼）：`search/websearch.py`（`WebSearch`）、`seed/fetch.py:92`
  `fetch_url`、`rag/answerer.py` `Answerer`、`rag/service.py` `_is_no_material`、`rag/types.py`
  `CorpusEntry`/`Source`、`backends/factory.py` `make_embedder/make_answerer/make_web_search`。

## Phase 2：Foundational（阻擋所有 US）

- [x] T002 在 `src/knowfield/config.py` 加 `smart_search_topn`（預設 "4"），`from_env` 讀
  `KNOWFIELD_SMART_TOPN`（沿用既有欄位樣式）。

## Phase 3：US1 讀完給我重點（整理）＋ US2 排序（P1，MVP 核心）

> 獨立測試：`SmartSearch.run(query)` 對排序後 top-N 抓內文、合成 grounded 整理（逐點 `[n]`），
> 回排序後完整結果；離線 stub 全鏈綠燈。

### 測試先行（TDD）
- [x] T003 [P] [US1] `tests/unit/test_smart_search.py`：`SmartSearch.run` 用注入 stub（StubWebSearch＋
  假 fetch 回固定 HTML＋HashingEmbedder＋StubAnswerer）——驗 ①**排序**（令某則最相關→排第一）、
  ②**passages 轉接**（entry_id=序位、title/url/body=內文）、③整理含 `[n]`、④回排序後**完整** results。
- [x] T004 [P] [US1] `tests/unit/test_smart_search.py` 續：**單則抓不到降級**（fetch 對某 url 拋錯→該則
  用 snippet、run 不拋）、**no_material**（answerer 回「沒有相關材料」→ `no_material=True`、`sources=[]`）。

### 實作
- [x] T005 [US1] 新增 `src/knowfield/search/smart.py`：`SmartResult` dataclass（overview／sources／
  no_material／results／overview_error）＋`SmartSearch`（注入 web_search／embedder／answerer／fetch／
  top_n），`run(query)`：搜尋→排序（embed query 與 title+snippet、cosine、stable sort）→ top-N `fetch`
  （失敗退 snippet）→ 包 `CorpusEntry`→ `answerer.answer(query, passages, "繁體中文")`→ `_is_no_material`
  判定→ 回 `SmartResult`。內文抓取單則以 try 包、降級。
- [x] T006 [US1] `src/knowfield/backends/factory.py` 加 `make_smart_search(config)`：組
  web_search/embedder/answerer/fetch_url/top_n。

## Phase 4：US3 挑到的才留（P1，串頁面）＋ US4 友善降級（P2）

> 獨立測試：`/search` 顯示整理＋排序結果、`[n]`→`#res-n`、可收進；整理失敗仍列結果、非 500。

### 測試先行
- [x] T007 [P] [US3] `tests/contract/test_smart_search.py`：`/search?q=X`（注入
  `app.state.smart_search_factory` 回假 `SmartResult`）→ 頁面含**整理段**、結果卡有 `id="res-1"…`、
  每則「收進」表單（`action="/ingest"`）、整理 `[n]` 是連到 `#res-n` 的連結。
- [x] T008 [P] [US4] `tests/contract/test_smart_search.py` 續：**整理失敗**（factory 拋錯）→ 頁面顯示
  友善繁中整理錯誤、**仍列原始結果**、非 500、無 Traceback；**no_material** 的 SmartResult → 顯示無材料、
  **不列 `[n]` 來源**。
- [x] T009 [P] [US3] `tests/contract/test_smart_search.py` 續：**收進不變**——對一則結果 url POST /ingest
  （monkeypatch `knowfield.seed.fetch.default_http_get` 真實離線）→ `list_seeds` 有該 url（同 spec 009 US2）。

### 實作
- [x] T010 [US3] `src/knowfield/web/app.py`：`app.state.smart_search_factory = _default_smart_search`
  （呼叫 `make_smart_search(config).run(q)`）；`/search` 路由改為：搜尋層 try（`SourceUnavailable`→err，
  同階段 9）外，**整理層另一個 try**——成功回 `SmartResult`、失敗設 `overview_error` 但保留原始 results。
  傳 `result`（SmartResult 或降級物）給 template。
- [x] T011 [US3] `src/knowfield/web/templates/search.html`：頂端渲染 `overview`（marked＋MathJax，`[n]`→
  `#res-n`，複用 ask.html JS）＋ `overview_error`／`no_material` 友善區塊；結果卡加 `id="res-{{ loop.index }}"`、
  維持「收進」表單。空 query／查無維持既有。

## Phase 5：Polish

- [x] T012 [P] 更新 `docs/usage.md`：`/search` 說明加「整理＋排序」（讀完給重點、可回溯、人挑不變）。
- [x] T013 全套 `uv run pytest` 綠、不回歸（≥197＋新測）；快速手測 `/search`（離線 stub）。
- [ ] T014 真跑抽查（可選，留使用者）：設 Tavily 金鑰 → `/search` 真 query 看整理品質。

## 相依與 MVP

- **相依**：T002 → T005 → T006 → T010 → T011；測試（T003/4/7/8/9）先於對應實作。
- **MVP**：Phase 3（US1＋US2，核心整理＋排序，`SmartSearch.run` 可測）即最小可交付；Phase 4 串上頁面。
- **並行**：T003/T004（unit）與 T007/T008/T009（contract）各自 `[P]`（同檔內順序寫）。
- **範圍守恆**：**無探索（multi-angle/agentic）**、無新資料表、無新 pip 相依、無 CLI。
