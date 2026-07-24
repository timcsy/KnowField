---
description: "Task list — 來源訂閱（自助加/管理來源）"
---

# Tasks: 來源訂閱（自助加／管理來源）

**Input**: `specs/008-source-subscribe/`（plan، spec، research، data-model، contracts/web-sources، quickstart）

**Tests**: 含測試——憲章原則 I（TDD 不可妥協）。**測試先寫、先失敗、再實作。**

**Organization**: 依 user story 分期，各期可獨立實作與測試。

## Format: `[ID] [P?] [Story] Description`
- **[P]**：不同檔、無依賴 → 可並行
- **[Story]**：US1/US2/US3 溯源標籤

## Path Conventions
單一專案：`src/learnnews/`、`tests/`（repo 根）。

---

## Phase 1: Setup

- [x] T001 確認 `tests/{unit,contract}/` 就緒（無新 schema/相依）

---

## Phase 2: Foundational（阻塞所有 user story）

- [x] T002 repository：`delete_source(source_id)`（`DELETE FROM sources WHERE id=?`）in `src/learnnews/store/repository.py`
- [x] T003 [P] `sources/subscribe.py` 骨架：`_FeedLinkParser`（html.parser 找 `<link rel=alternate rss/atom>`）＋`discover_feed(url, http_get)` in `src/learnnews/sources/subscribe.py`

**Checkpoint**：探測與刪除底層就緒。

---

## Phase 3: User Story 1 - 自助追蹤一個站台/部落格（P1）🎯 MVP

**Goal**：貼 URL → 探測 feed → 實測有料 → 加入啟用；下次 digest 自動抓。

**Independent Test**：假 http_get 給「首頁 HTML（含 feed link）＋feed 內容」→ `subscribe` 建出 Source；web `POST /sources/add` 後來源出現在清單。

### Tests（先寫、先失敗）
- [x] T004 [P] [US1] 單元測試 `tests/unit/test_feed_discovery.py`：`discover_feed`（url 即 feed／HTML alternate link／找不到→None）；`validate_feed`（≥1 條有效、空/壞→拋）；`subscribe`（建 Source、無 feed/無料→SourceUnavailable）
- [x] T005 [P] [US1] 契約測試 `tests/contract/test_web_sources.py`：`GET /sources` 列出；`POST /sources/add`（注入 subscribe_factory）→ 來源加入並顯示；種入該假來源後 `build_adapters` 能抓到（自動帶入匯整）

### Implementation
- [x] T006 [US1] `sources/subscribe.py`：`validate_feed`（復用 `RssAdapter`＋注入 fetch，≥1 條）＋`subscribe(url, http_get)`（discover→validate→建 `Source(id=網域 slug, name=feed 標題)`；失敗拋 `SourceUnavailable`）
- [x] T007 [US1] `templates/sources.html`（來源清單＋加來源框；結果/錯誤訊息）in `src/learnnews/web/templates/`
- [x] T008 [US1] `GET /sources`＋`POST /sources/add`（`app.state.subscribe_factory`→已存提示/否則 `upsert_source`；攔 `SourceUnavailable` 頁內友善不落庫）in `src/learnnews/web/app.py`
- [x] T009 [US1] 導覽加「來源」in `src/learnnews/web/templates/base.html`

**Checkpoint**：離線貼假來源 → 加入 → digest 抓得到。**MVP 達成。**

---

## Phase 4: User Story 2 - 管理我追蹤的來源（P2）

**Goal**：列出來源，停用/啟用/刪除；停用後匯整不抓、刪除被尊重。

**Independent Test**：種幾個來源 → `/sources` 列出 → 停用一個（enabled_only 不含它）→ 刪除一個（消失）→ 重啟用。

### Tests（先寫、先失敗）
- [x] T010 [P] [US2] 契約測試 `tests/contract/test_web_sources.py`（追加）：`POST /sources/toggle` 停用→`list_sources(enabled_only=True)` 不含；`POST /sources/remove`→清單消失；重啟用恢復

### Implementation
- [x] T011 [US2] `POST /sources/toggle`（`set_source_enabled`）＋`POST /sources/remove`（`delete_source`）in `app.py`；`sources.html` 加停用/啟用/刪除鈕

**Checkpoint**：US1＋US2 皆可獨立運作。

---

## Phase 5: User Story 3 - 誠實邊界：不加壞來源（P3）

**Goal**：無 feed／抓不到料／網路失敗 → 友善繁中、來源清單未新增。

**Independent Test**：假 http_get 分別回「無 feed 首頁」「探測到 feed 但空」「拋例外」→ `POST /sources/add` 皆友善提示、`list_sources` 未增。

### Tests（先寫、先失敗）
- [x] T012 [P] [US3] 契約測試 `tests/contract/test_web_sources.py`（追加）：三種失敗 → 200＋友善繁中、無 `Traceback`、**來源數不變**；重複加同 feed → 「已在追蹤」不重複

### Implementation
- [x] T013 [US3] 確保 `POST /sources/add` 對 `SourceUnavailable` 頁內攔（含網路失敗）、去重（同 id 提示已在追蹤）in `app.py`／`subscribe.py`

**Checkpoint**：三個 user story 皆獨立可用。

---

## Phase 6: Polish & Cross-Cutting

- [x] T014 [P] `docs/usage.md` 補 `/sources`（貼 URL 加來源、探測/驗證、停用/刪除）
- [x] T015 真跑：離線端到端＋build_adapters 帶入已驗；貼真實部落格 RSS 真跑留使用者（網路）
- [x] T016 跑 `quickstart.md` 全流程；`uv run pytest -q` 全套（新測綠燈、**既有 177 不回歸**）

---

## Dependencies & Execution Order

- **Setup（T001）** → **Foundational（T002–T003）** → **US1（T004–T009）** → US2（T010–T011）→ US3（T012–T013）→ Polish（T014–T016）。
- **`app.py` 內 T008→T011→T013 同檔、循序**；`subscribe.py` 內 T003→T006 同檔、循序。
- 各 user story 內：**測試先寫且失敗** → 再實作；discover/validate 先於 web。

### Parallel Opportunities
- Foundational：T002（repository）與 T003（subscribe.py）不同檔，可並行。
- US1 測試可並行：**T004、T005**（不同檔）。

## Parallel Example: US1 測試
```bash
Task: "單元測試 tests/unit/test_feed_discovery.py"
Task: "契約測試 tests/contract/test_web_sources.py"
```

## Implementation Strategy
1. Setup → Foundational（delete_source＋discover_feed）。
2. **US1 → STOP & VALIDATE（貼假來源→加入→digest 抓到）= MVP**，可展示。
3. 疊 US2（停用/啟用/刪除）→ 測試 → 展示。
4. 疊 US3（不加壞來源）→ 測試 → 展示。
5. Polish：docs、真跑、全套不回歸。

## Notes
- [P]＝不同檔無依賴；[Story] 溯源；每個 user story 獨立可測。
- **先確認測試失敗再實作**；每任務或邏輯群組後 commit。
- 探測/驗證用可注入 `http_get` 離線測（教訓 1）；加前驗證有料才落庫（教訓 7）；失敗不加壞（教訓 3）。
- 復用 RssAdapter/sources 表/build_adapters（教訓 8、抓取管線零改）；無新 schema/相依（YAGNI）。
