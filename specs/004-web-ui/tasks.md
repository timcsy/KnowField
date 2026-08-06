---
description: "Task list — Web 介面（階段 6）"
---

# Tasks: Web 介面

**Input**: Design documents from `specs/004-web-ui/`

**Prerequisites**: plan.md、spec.md、research.md、data-model.md、contracts/

**Tests**: TDD（憲章原則 I，不可妥協）——測試先寫、先失敗，再實作。

**Organization**: 依使用者故事分組。**核心零改動、全複用**；新增只在 `web/` 一層。

## Format: `[ID] [P?] [Story] Description`
- **[P]**：可平行（不同檔案、無未完成相依）
- 面向使用者輸出與文件為繁體中文（憲章原則 II）

## Path Conventions
單一專案：新增 `src/knowfield/web/`（唯一碰框架處）；測試於 `tests/`（含 FastAPI TestClient）。

---

## Phase 1: Setup

- [X] T001 `pyproject.toml` 加 `web` extra（fastapi、uvicorn、jinja2），dev 加 httpx（TestClient 需）；建 `src/knowfield/web/{__init__,app,views,cache}.py`、`src/knowfield/web/templates/`（佔位）per plan.md

---

## Phase 2: Foundational（阻斷性前置）

- [X] T002 [P] 單元測試（先失敗）：`get_last_digest()` 讀最近匯整全部 entries 於 `tests/unit/test_get_last_digest.py`
- [X] T003 store 擴充 `get_last_digest() -> Digest | None` 於 `src/knowfield/store/repository.py`（使 T002 通過；per data-model.md）
- [X] T004 [P] 單元測試（先失敗）：views 把 Article/DigestEntry → PageEntry（散文切段、圖 is_ai、原標題副標）於 `tests/unit/test_web_views.py`
- [X] T005 `web/views.py`（Article/entry → PageEntry：headline、original_title、paragraphs、figure）於 `src/knowfield/web/views.py`（使 T004 通過）
- [X] T006 FastAPI app 骨架＋`base.html`（Tailwind CDN、RWD viewport、繁中版型）於 `src/knowfield/web/app.py`、`web/templates/base.html`
- [X] T007 [P] Contract test（先失敗）：後端失敗 → 友善繁中頁、**無 traceback、非未處理 500** 於 `tests/contract/test_web_error.py`
- [X] T008 錯誤邊界：`OpenAIError` 例外處理器 → 友善繁中錯誤頁 於 `src/knowfield/web/app.py`、`web/templates/error.html`（使 T007 通過；FR-009、教訓 3）

**Checkpoint**：web 地基（app／views／錯誤邊界／get_last_digest）就緒。

---

## Phase 3: User Story 1 - 在瀏覽器看今日匯整 (Priority: P1) 🎯 MVP

**Goal**：首頁顯示今日匯整——散文＋原文圖內嵌＋一鍵原文；無匯整顯示空狀態。

**Independent Test**：跑一次 digest 後開 `/`，驗證每則散文、原文圖 `<img>` 內嵌、原文連結；無匯整→空狀態。

### Tests for User Story 1（先寫、先失敗）⚠️

- [X] T009 [P] [US1] Contract test：`GET /`——有匯整→原文連結（FR-002）＋原文圖 `<img>`（FR-003）＋AI 圖標示；無匯整→空狀態（FR-011）於 `tests/contract/test_web_home.py`

### Implementation for User Story 1

- [X] T010 [US1] `GET /` 路由：讀 `get_last_digest()` → PageEntry 渲染 於 `src/knowfield/web/app.py`（依 T003、T005）
- [X] T011 [US1] `digest.html` 模板：散文＋圖內嵌＋一鍵原文＋空狀態（Tailwind RWD）於 `web/templates/digest.html`

**Checkpoint**：US1 可獨立運作 = **MVP**（瀏覽器看匯整）。

---

## Phase 4: User Story 2 - 輸入主題即時拉 (Priority: P2)

**Goal**：web 輸入主題即時拉，含快取／節流避免狂打後端。

**Independent Test**：`GET /pull?topic=agent` 回散文結果；同主題二次不打後端；冷門→空狀態。

### Tests for User Story 2（先寫、先失敗）⚠️

- [X] T012 [P] [US2] Unit test：cache TTL 命中/過期、節流 於 `tests/unit/test_web_cache.py`
- [X] T013 [P] [US2] Contract test：`GET /pull`——回主題散文結果＋原文連結；**同主題二次不呼叫後端**（FR-005/SC-004，以計數驗證）；冷門→空狀態 於 `tests/contract/test_web_pull.py`

### Implementation for User Story 2

- [X] T014 [US2] `web/cache.py`：記憶體 TTL 快取＋節流（使 T012 通過）於 `src/knowfield/web/cache.py`
- [X] T015 [US2] `GET /pull` 路由：正規化主題→快取命中回快取／否則 `run_pull`→存快取 於 `src/knowfield/web/app.py`（依 T014）
- [X] T016 [US2] `pull.html` 模板（＋首頁主題輸入框）於 `web/templates/pull.html`、`web/templates/digest.html`

**Checkpoint**：US1＋US2 皆可運作。

---

## Phase 5: User Story 3 - 管理興趣清單 (Priority: P3)

**Goal**：web 檢視／新增／刪除興趣主題。

**Independent Test**：`/interests` 新增再刪除，清單即時反映。

### Tests for User Story 3（先寫、先失敗）⚠️

- [X] T017 [P] [US3] Contract test：`/interests` list／`POST add`／`POST remove` 反映變更（FR-006）於 `tests/contract/test_web_interests.py`

### Implementation for User Story 3

- [X] T018 [US3] `/interests`＋`/interests/add`＋`/interests/remove` 路由（`InterestService`）＋`interests.html` 於 `src/knowfield/web/app.py`、`web/templates/interests.html`

**Checkpoint**：三故事皆可運作。

---

## Phase 6: Polish & Cross-Cutting

- [X] T019 [P] 執行 quickstart.md 情境 A–H 端到端驗證（含 RWD 手機/桌面人工檢視）
- [X] T020 [P] 更新 `docs/usage.md`：web 啟動說明（`uv sync --extra web`、`uvicorn knowfield.web.app:app`）
- [X] T021 [P] 補齊剩餘單元測試覆蓋於 `tests/`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup（P1）**：無相依。
- **Foundational（P2）**：依 Setup；阻斷所有故事（app／views／錯誤邊界／get_last_digest）。
- **US1（P3）**：依 Foundational；核心呈現，獨立可測。
- **US2（P4）**：依 Foundational；快取＋拉路由（複用 run_pull）。
- **US3（P5）**：依 Foundational；興趣路由（複用 InterestService）。
- **Polish（P6）**：依所需故事完成。

### Within Each User Story
- 測試先寫且**先失敗**，再實作（原則 I）。
- get_last_digest／views → app 骨架／錯誤邊界 → 路由 → 模板。

### Parallel Opportunities
- Foundational：T002、T004、T007 可平行（測試）；T005/T006/T008 依序或按檔案。
- US2 測試 T012、T013 可平行。
- Polish T019–T021 可平行。

---

## Parallel Example: Foundational
```bash
Task: "Unit test get_last_digest in tests/unit/test_get_last_digest.py"
Task: "Unit test web views in tests/unit/test_web_views.py"
Task: "Contract test 錯誤邊界 in tests/contract/test_web_error.py"
```

---

## Implementation Strategy

### MVP First（僅 User Story 1）
1. Setup → 2. Foundational → 3. US1（首頁看匯整）→ 4. **STOP 並驗證**（quickstart A/B/H）→ 可展示。

### Incremental Delivery
1. Setup＋Foundational → 地基。
2. US1 → 瀏覽器看匯整 MVP。
3. US2 → 即時拉。
4. US3 → 管理興趣。

---

## Notes
- [P]＝不同檔案、無未完成相依。
- 每個功能任務前先確認其測試已寫且失敗（TDD）。
- **核心零改動**（只加 `store.get_last_digest`）；框架相依只在 `web/`。
- 每則一鍵原文（原則 3）；AI 圖標「AI 示意・非原文」；後端失敗友善頁不噴 500（教訓 3）。
- RWD（情境 F）為人工視覺驗證；其餘離線可測（後端 stub、匯整樣本）。
