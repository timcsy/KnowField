# Tasks：探索（多角度擴展搜尋）

**功能目錄**：`specs/011-explore-multiangle/`　｜　**TDD 強制**　｜　基準測試：209（不回歸）

依 spec 的 US 分期。`[P]`＝可並行（不同檔、無未完成相依）。

## Phase 1：Setup

- [x] T001 唯讀盤點復用點：`search/smart.py` `SmartSearch`（spec 010）、`search/websearch.py`、
  `backends/openai_api.py:36` `_post`、`backends/factory.py`、`web/app.py:/search`、`templates/search.html`。

## Phase 2：Foundational（阻擋所有 US）

- [x] T002 `src/knowfield/config.py` 加 `explore_max_subqueries`（預設 5），`from_env` 讀
  `KNOWFIELD_EXPLORE_MAXQ`（沿用既有欄位樣式）。

## Phase 3：US1 一鍵撒更廣的網（P1，MVP 核心）

> 獨立測試：`SmartSearch.run(q, explore=True)` fan-out 多角度、合併去重、跑既有整理；離線 stub 綠燈。

### 測試先行（TDD）
- [x] T003 [P] [US1] `tests/unit/test_expand.py`：`StubQueryExpander.expand` 回非空確定性清單；
  `OpenAIQueryExpander`（注入 poster 回多行）→ 解析成清單、**上限裁切**、空/例外 → `[]`。
- [x] T004 [P] [US1] `tests/unit/test_smart_search.py` 追加：`run(q, explore=True)`（注入 StubExpander＋
  web_search 回**含重複 url** 的多結果）→ 合併池**去重**（重複只一則）、原 query 納入、角度數≤max；
  `run(q, explore=False)` → web_search **只呼叫一次**（計數驗證，等同增量 b）。
- [x] T005 [P] [US1] `tests/unit/test_smart_search.py` 追加：expander.expand **拋錯** → 退回單 query
  （結果＝單搜尋、run 不拋，教訓 3）。

### 實作
- [x] T006 [US1] 新增 `src/knowfield/search/expand.py`：`QueryExpander` Protocol＋`StubQueryExpander`
  （確定性 `[q+" 原理", q+" 應用", q+" 比較"]`）＋`OpenAIQueryExpander`（`_post` chat 拆解、逐行解析、
  上限、空/例外回 `[]`；poster 可注入供測試）。
- [x] T007 [US1] `src/knowfield/search/smart.py`：`SmartSearch.__init__` 加 `expander=None`、
  `max_subqueries=5`；`run(query, explore=False)`＋私有 `_collect(query, explore)`——explore 時
  `angles=dedup([query]+expander.expand())[:max]`（expand 拋錯→`[query]`）、各搜、依 url 正規化
  合併去重；非 explore 走單 query。其餘（排序/抓取/整理）不動。
- [x] T008 [US1] `src/knowfield/backends/factory.py` 加 `make_query_expander(config)`；
  `make_smart_search` 改為注入 expander＋`max_subqueries=config.explore_max_subqueries`。

## Phase 4：US1/US2 串頁面＋友善退回（P1/P2）

> 獨立測試：/search 有「深入探索」開關；勾選走多角度、不勾＝增量 b；拆角度失敗退回單 query。

### 測試先行
- [x] T009 [P] [US1] `tests/contract/test_explore.py`：`/search?q=X&explore=1`（注入
  `smart_search_factory` 記錄收到的 explore）→ 收到 `explore=True`；`/search?q=X`（不帶）→ `explore=False`。
- [x] T010 [P] [US1] `tests/contract/test_explore.py` 續：頁面含「深入探索」checkbox（`name="explore"`）；
  帶 `explore=1` 時回填 checked。
- [x] T011 [P] [US2] `tests/contract/test_explore.py` 續：真實鏈（StubExpander）下 `smart_search_factory`
  預設走 offline、`/search?q=X&explore=1` 回 200、頁面正常（合併去重不崩）。

### 實作
- [x] T012 [US1] `src/knowfield/web/app.py`：`_default_smart_search(query, explore)` 呼叫
  `make_smart_search(config).run(query, explore)`；`smart_search_factory` 簽名改 `(q, explore=False)`；
  `/search` 路由讀 `explore: str = ""`→`bool`、傳入 factory。
- [x] T013 [US1] `src/knowfield/web/templates/search.html`：搜尋表單加「深入探索」checkbox
  （`name="explore" value="1"`，沿用 ask.html today 樣式）、勾選回填；加一行說明「從多個角度撒網、較花額度」。
- [x] T014 [US1] 同步既有注入點：`tests/contract/test_smart_search.py`、`tests/contract/test_web_search.py`
  的 `smart_search_factory` lambda 改 `lambda q, explore=False: ...`（相容新簽名）。

## Phase 5：Polish

- [x] T015 [P] 更新 `docs/usage.md`：`/search` 說明加「深入探索（多角度、opt-in、預設關）」。
- [x] T016 全套 `uv run pytest` 綠、不回歸（≥209＋新測）；快速手測 `/search` 勾/不勾（離線 stub）。
- [ ] T017 真跑抽查（可選，留使用者）：設金鑰 → 勾深入探索看多角度整理品質。

## 相依與 MVP

- **相依**：T002 → T006 → T007 → T008 → T012 → T013；T014 隨 T012 簽名改一起。測試先於實作。
- **MVP**：Phase 3（`SmartSearch.run(explore=True)` fan-out＋去重可測）即最小可交付；Phase 4 串頁面。
- **並行**：T003/T004/T005（unit）、T009/T010/T011（contract）各 `[P]`（同檔內順序）。
- **範圍守恆**：**無 (b) agentic 多輪迴圈**、無子角度分組顯示、無新資料表、無新 pip 相依、無 CLI。
