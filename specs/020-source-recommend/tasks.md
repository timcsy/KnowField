# 任務清單：場驅動來源推薦

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`020-source-recommend`

TDD 強制：每階段先寫紅測（Red）→ 實作轉綠（Green）。全複用 spec 008/009/016/005/018，零新相依/零新表。

---

## Phase 1：Setup

- [X] T001 在 `src/knowfield/config.py` 加 `source_recommend_queries: list[str]`（預設 roundup query 常數，如「最佳 AI 部落格 2026」「best AI research blogs」「top AI newsletters roundup」）與 `source_recommend_limit: int = 8`；`from_env` 加對應環境變數覆寫（可選）。

## Phase 2：Foundational（純函式核心，阻塞路由）

- [X] T002 [P] 在 `tests/unit/test_source_recommend.py` 寫 `recommend_sources` 紅測：注入假 `web_search`（回多筆結果、跨網域重複）＋假 `http_get`（部分站有活 feed、部分探到死 feed、部分無 feed）＋假 `embedder`＋種子 repo → 斷言：①死/幻覺 feed **不在**結果（FR-002）；②無 feed 候選 `has_feed=False` 保留（FR-010）；③`list_hits` 正確計跨結果重複。
- [X] T003 [P] 在 `tests/unit/test_source_recommend.py` 寫**排序**紅測：候選 A（場驅動高）、B（有活 feed）、C（僅跨清單重複）→ 斷言排序 A>B>C；另一案**無 attractor**（空場）→ 退回 `has_feed ＞ list_hits`、仍出清單（FR-005）。
- [X] T004 [P] 在 `tests/unit/test_source_recommend.py` 寫**已訂閱標示**紅測：候選 feed 已在 `list_sources` → `already_subscribed=True`（FR-007）。
- [X] T005 建 `src/knowfield/sources/recommend.py`：`@dataclass CandidateSource`＋`recommend_sources(web_search, embedder, repo, *, http_get=default_http_get, queries=None, limit=8)`。撒網→抽網域（netloc 去 www、計 `list_hits`）→ `discover_feed`＋`validate_feed`（死/幻覺丟棄、無 feed 標示、單站 try/except `SourceUnavailable` 跳過）→ 場驅動分數（`list_field_attractors`＋`ensure_embeddings`＋`cosine` 最大值）→ `already_subscribed`（`_source_id` 命中 `list_sources`）→ 排序 `(field_score, has_feed, list_hits)` 取前 `limit`。跑 T002/T003/T004 轉綠。

**檢查點**：純函式產出正確排序、驗證濾除、標示齊全；離線零外部呼叫。

---

## Phase 3：US1+US2+US3（P1）——web 動作、場驅動排序、人訂閱

- [X] T006 [P] 在 `tests/contract/test_source_recommend_web.py` 寫路由紅測：注入假 `app.state.recommend_factory` 回若干 `CandidateSource` → `POST /sources/recommend` 回 200＋`sources.html` 含各候選網域＋理由＋（有 feed 者）訂閱表單指向 `/sources/add`。
- [X] T007 [P] 寫**opt-in 守衛**紅測：GET `/sources` 與跑一次匯整（`/digest/refresh` 或既有 refresh 測法）時 `recommend_factory` **零呼叫**（spy 計數，FR-006）。
- [X] T008 [US1] 在 `src/knowfield/web/app.py` 加 `app.state.recommend_factory`（預設用 `make_web_search`＋`make_embedder`＋repo 建 `recommend_sources`，`finally` 關 repo）＋ `POST /sources/recommend`（呼叫 factory→渲染 sources.html 加 `recommendations`；空→友善提示）。跑 T006 轉綠。
- [X] T009 [US1] 在 `src/knowfield/web/templates/sources.html`：「追蹤」表單下加「🔎 幫我找新來源」表單（POST `/sources/recommend`）＋推薦區塊（`{% if recommendations %}`：網域＋feed 狀態＋理由＋場驅動標記；有 feed→「訂閱」表單 POST `/sources/add` `url=feed_url`；已訂閱→「已在名冊」；無 feed→「無 RSS，靠 web 活水/收進補」）。

**檢查點（US1/2/3 可獨立驗）**：/sources 一鍵得場驅動排序候選、訂閱複用 add、名冊不被自動改。

---

## Phase 4：US4（P2）——失敗/空友善

- [X] T010 [P] [US4] 寫失敗友善紅測：`recommend_factory` 拋 `SourceUnavailable` → `POST /sources/recommend` 回 200＋友善 `err`、不噴 Traceback（教訓 3）。
- [X] T011 [P] [US4] 寫空結果紅測：`recommend_factory` 回 `[]` → 頁面顯示「這次沒找到可訂的新來源」。
- [X] T012 [US4] 在 `POST /sources/recommend` 加 `except (SourceUnavailable, OpenAIError)` → `_log.error`＋友善 `err`；空清單→友善訊息。跑 T010/T011 轉綠。

**檢查點**：搜尋/抓 feed 失敗、空結果皆友善不崩。

---

## Phase 5：Polish & 回歸

- [X] T013 跑 `uv run pytest tests/unit/test_source_recommend.py tests/contract/test_source_recommend_web.py -q` 全綠。
- [X] T014 跑 `uv run pytest -q` 全綠（現 298 + 本增量新測）；確認範圍守住（無自動訂閱/每次匯整自動跑/品質加權/email-ingestion/CLI）。既有 `/sources/add|toggle|remove`、`test_field_relate_web` 等零回歸。

---

## 依賴與執行順序
- Setup（T001）→ Foundational（T002–T005，純函式核心）阻塞路由。
- US1/2/3（T006–T009）：路由＋模板，依 T005（recommend_sources）與 T001（config）。
- US4（T010–T012）依路由就緒。
- Polish（T013–T014）最後。

## 平行機會
- T002‖T003‖T004（不同測案）；T006‖T007；T010‖T011。
- 實作 T005（模組）、T008/T009（app＋模板）、T012（同路由）順序觸同批檔案，序執行。

## MVP
**T001–T009**＝一鍵場驅動來源推薦、訂閱複用 add、名冊不自動改。US4 為友善邊界，薄。
