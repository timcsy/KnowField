---
description: "Task list — web 搜尋（開放網路進水口）"
---

# Tasks: web 搜尋（開放網路進水口）

**Input**: `specs/009-web-search/`（plan، spec، research، data-model، contracts/web-search، quickstart）

**Tests**: 含測試——憲章原則 I（TDD 不可妥協）。**測試先寫、先失敗、再實作。**

**Organization**: 依 user story 分期，各期可獨立實作與測試。

## Format: `[ID] [P?] [Story] Description`
- **[P]**：不同檔、無依賴 → 可並行
- **[Story]**：US1/US2/US3 溯源標籤

## Path Conventions
單一專案：`src/knowfield/`、`tests/`（repo 根）。

---

## Phase 1: Setup

- [x] T001 [P] 建 `src/knowfield/search/__init__.py`；確認 `tests/{unit,contract}/` 就緒

---

## Phase 2: Foundational（阻塞所有 user story）

- [x] T002 [P] config：`search_api_url`／`search_api_key`（env `KNOWFIELD_SEARCH_API_URL`／`KNOWFIELD_SEARCH_KEY`）in `src/knowfield/config.py`
- [x] T003 `search/websearch.py`：`SearchResult`（title/url/snippet）＋`WebSearch` 協定＋`StubWebSearch`（離線回固定假結果）in `src/knowfield/search/websearch.py`

**Checkpoint**：搜尋型別與離線後端就緒。

---

## Phase 3: User Story 1 - 對開放網路搜尋（P1）🎯 MVP

**Goal**：`/search?q=` → 可插拔後端回結果 → 頁面列出（標題/網址/摘要）；查無友善提示。

**Independent Test**：注入假 `web_search_factory` 回固定結果 → `GET /search?q=x` 列出那些結果、每則可點原文；空結果→查無提示。

### Tests（先寫、先失敗）
- [x] T004 [P] [US1] 單元測試 `tests/unit/test_websearch.py`：`StubWebSearch.search` 回結果；真實後端解析（假 http POST → title/url/snippet 寬鬆解析）；失敗拋 `SourceUnavailable`
- [x] T005 [P] [US1] 契約測試 `tests/contract/test_web_search.py`：`GET /search?q=`（注入假後端）列出結果＋原文連結；查無→提示

### Implementation
- [x] T006 [US1] `search/websearch.py`：真實 urllib 後端（POST `config.search_api_url`、Tavily 形狀寬鬆解析）＋`make_web_search(config)`（stub↔真實）in `src/knowfield/search/websearch.py`＋`src/knowfield/backends/factory.py`
- [x] T007 [US1] `templates/search.html`（查詢框＋結果清單＋空狀態）in `src/knowfield/web/templates/`
- [x] T008 [US1] `GET /search`（`app.state.web_search_factory`→渲染）in `src/knowfield/web/app.py`；導覽加「搜尋」in `base.html`

**Checkpoint**：離線 `/search` 列結果可獨立跑通。**MVP 達成。**

---

## Phase 4: User Story 2 - 把有價值的結果冊封成種子（P1）

**Goal**：每則結果「收進」→ 走既有 `/ingest` 成種子；未收進的不落庫。

**Independent Test**：假結果 → 對一則的 url 送 `POST /ingest`（既有，抓取可注入）→ 該篇成種子、`ask` 檢索得到；其餘未落庫。

### Tests（先寫、先失敗）
- [x] T009 [P] [US2] 契約測試 `tests/contract/test_web_search.py`（追加）：結果頁每則有「收進」表單→`/ingest`（ref=url）；收進一則後 `list_seeds` 有它、未收進的不在庫

### Implementation
- [x] T010 [US2] `search.html` 每則結果加「收進」表單（`POST /ingest`，hidden `ref`=結果 url）in `src/knowfield/web/templates/search.html`

**Checkpoint**：搜尋→收進成種子可跑通（收進復用既有 ingest，無新後端碼）。

---

## Phase 5: User Story 3 - 誠實邊界：後端不可用不炸（P3）

**Goal**：搜尋後端失敗/未設金鑰 → 頁內友善繁中、頁面正常、無堆疊。

**Independent Test**：注入 `web_search_factory` 拋 `SourceUnavailable` → `GET /search?q=x` 200＋友善繁中、無 `Traceback`。

### Tests（先寫、先失敗）
- [ ] T011 [P] [US3] 契約測試 `tests/contract/test_web_search.py`（追加）：後端拋 `SourceUnavailable`→200＋友善繁中、無 `Traceback`；未設金鑰→走 stub（不崩）

### Implementation
- [ ] T012 [US3] `GET /search` 攔 `SourceUnavailable` → 頁內友善繁中訊息（不噴堆疊）in `src/knowfield/web/app.py`

**Checkpoint**：三個 user story 皆獨立可用。

---

## Phase 6: Polish & Cross-Cutting

- [x] T013 [P] `docs/usage.md` 補 `/search`（搜尋→收進成種子、可插拔後端、離線 stub）
- [x] T014 真跑：離線端到端＋收進→種子已驗；真實搜尋金鑰真跑留使用者
- [x] T015 跑 `quickstart.md` 全流程；`uv run pytest -q` 全套（新測綠燈、**既有 190 不回歸**）

---

## Dependencies & Execution Order

- **Setup（T001）** → **Foundational（T002–T003）** → **US1（T004–T008）** → US2（T009–T010）→ US3（T011–T012）→ Polish（T013–T015）。
- **`websearch.py` 內 T003→T006 同檔、循序**；`app.py` 內 T008→T012 同檔、循序。
- 各 user story 內：**測試先寫且失敗** → 再實作。

### Parallel Opportunities
- Foundational：T002（config）與 T003（websearch.py）不同檔，可並行。
- US1 測試可並行：**T004、T005**（不同檔）。

## Parallel Example: US1 測試
```bash
Task: "單元測試 tests/unit/test_websearch.py"
Task: "契約測試 tests/contract/test_web_search.py"
```

## Implementation Strategy
1. Setup → Foundational（config＋SearchResult/Stub）。
2. **US1 → STOP & VALIDATE（離線 /search 列結果）= MVP**，可展示。
3. 疊 US2（收進成種子；復用既有 /ingest，只加表單）→ 測試 → 展示。
4. 疊 US3（後端不可用友善）→ 測試 → 展示。
5. Polish：docs、真跑、全套不回歸。

## Notes
- [P]＝不同檔無依賴；[Story] 溯源；每個 user story 獨立可測。
- **先確認測試失敗再實作**；每任務或邏輯群組後 commit。
- 搜尋後端可注入離線測（教訓 1）；失敗友善（教訓 3）；結果不落庫、人冊封才留（原則 5）。
- **「收進」復用既有 /ingest**（spec 006）＝零新後端碼；無新 schema、無新 pip 相依（YAGNI）。
