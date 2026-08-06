---
description: "Task list — 知識庫管理（前端策展/修剪）"
---

# Tasks: 知識庫管理（前端策展／修剪）

**Input**: `specs/007-library/`（plan، spec، research، data-model، contracts/web-library، quickstart）

**Tests**: 含測試——憲章原則 I（TDD 不可妥協）。**測試先寫、先失敗、再實作。**

**Organization**: 依 user story 分期，各期可獨立實作與測試。

## Format: `[ID] [P?] [Story] Description`
- **[P]**：不同檔、無依賴 → 可並行
- **[Story]**：US1/US2/US3 溯源標籤

## Path Conventions
單一專案：`src/knowfield/`、`tests/`（repo 根）。

---

## Phase 1: Setup

- [x] T001 確認 `tests/{unit,contract}/` 就緒（本功能無新模組/schema，免建目錄）

---

## Phase 2: Foundational（阻塞所有 user story）

**⚠️ 三個 repo 方法皆**僅限種子容器**（結構保證每日流唯讀，research R1）。同檔循序。**

- [x] T002 repository：`list_seeds() -> list[CorpusEntry]`（只撈 `d.date=SEEDS_DATE` 的 entries，新在上）in `src/knowfield/store/repository.py`
- [x] T003 repository：`delete_seed(entry_id) -> bool`（限種子容器；同交易刪 `digest_entries`＋`entry_embeddings`；非種子回 False）in `repository.py`（依賴 T002 之後、同檔循序）
- [x] T004 repository：`set_seed_class(entry_id, cls) -> bool`（`cls∈{explainer,ordinary}`；限種子容器 UPDATE `source_class`）in `repository.py`

**Checkpoint**：種子的列/刪/重分類資料層就緒，每日流結構性受保護。

---

## Phase 3: User Story 1 - 瀏覽並刪除我收的種子（P1）🎯 MVP

**Goal**：`/library` 列出種子；刪除一則 → 消失、`ask` 檢索不到、嵌入一併清（無孤兒）。

**Independent Test**：種入幾則種子 → `/library` 看到清單 → 刪一則 → 清單少一則、`ask` 檢索不到它、`entry_embeddings` 無該筆。

### Tests（先寫、先失敗）
- [x] T005 [P] [US1] 單元測試 `tests/unit/test_seed_management.py`：`list_seeds` 只列種子（不含每日流）；`delete_seed` 移除 entry＋其嵌入、非種子 entry_id 回 False 不動作
- [x] T006 [P] [US1] 契約測試 `tests/contract/test_web_library.py`：`GET /library` 列出種子＋原文連結；`POST /library/remove` 後該則消失、`ask` 檢索不到；空庫顯示空狀態

### Implementation
- [x] T007 [US1] `templates/library.html`（種子清單：標題/類型/日期/原文連結＋刪除表單；空狀態）in `src/knowfield/web/templates/`
- [x] T008 [US1] `GET /library`（`repo.list_seeds()`→渲染）＋`POST /library/remove`（`delete_seed`→303）in `src/knowfield/web/app.py`
- [x] T009 [US1] 導覽加「知識庫」連結 in `src/knowfield/web/templates/base.html`

**Checkpoint**：離線 `/library` 列種子＋刪除（連清嵌入）可獨立跑通。**MVP 達成。**

---

## Phase 4: User Story 2 - 重新分類（解說文↔一般）（P2）

**Goal**：在 `/library` 切換種子品質層；改後 `ask` 檢索權重即時跟上。

**Independent Test**：一則「一般」種子 → 改「解說文」→ `ask` 對相關問題該則權重提高。

### Tests（先寫、先失敗）
- [x] T010 [P] [US2] 整合測試 `tests/integration/test_reclassify_weight.py`：重分類為解說文 → `ask` 排序權重提高（對照一般種子）

### Implementation
- [x] T011 [US2] `POST /library/reclassify`（`set_seed_class`→303）in `app.py`；`library.html` 加重分類切換鈕

**Checkpoint**：US1＋US2 皆可獨立運作。

---

## Phase 5: User Story 3 - 只碰種子、每日流唯讀（P3）

**Goal**：`/library` 只呈現種子；每日流條目不現身、且無法從此刪/改。

**Independent Test**：種一份每日匯整＋幾則種子 → `/library` 只見種子；對每日流 entry_id 送 remove/reclassify → 不動作、每日流完好。

### Tests（先寫、先失敗）
- [x] T012 [P] [US3] 契約測試 `tests/contract/test_web_library.py`（追加）：每日匯整條目**不出現**在 `/library`；`POST remove`/`reclassify` 帶每日流 entry_id → 不動作、該條目仍在

**Implementation**：無新碼——由 T003/T004 的「僅限種子容器」結構保證（research R1）；本期只加驗證測試。

**Checkpoint**：三個 user story 皆獨立可用。

---

## Phase 6: Polish & Cross-Cutting

- [x] T013 [P] `docs/usage.md` 補 `/library`（瀏覽/刪除/重分類、每日流唯讀）
- [x] T014 跑 `quickstart.md` 全流程；`uv run pytest -q` 全套（新測綠燈、**既有 166 不回歸**）

---

## Dependencies & Execution Order

- **Setup（T001）** → **Foundational（T002–T004）** → **US1（T005–T009）** → US2（T010–T011）→ US3（T012）→ Polish（T013–T014）。
- **`repository.py` 內 T002→T003→T004 同檔、循序**；`app.py` 內 T008→T011 同檔、循序。
- 各 user story 內：**測試先寫且失敗** → 再實作。

### Parallel Opportunities
- US1 測試可並行：**T005、T006**（不同檔）。
- US2 測試 T010、US3 測試 T012 可與各自實作前並行撰寫。
- T007（模板）與 T008（路由）不同檔，可並行起草，但 T008 依賴 T002/T003。

## Parallel Example: US1 測試
```bash
Task: "單元測試 tests/unit/test_seed_management.py"
Task: "契約測試 tests/contract/test_web_library.py"
```

## Implementation Strategy
1. Setup → Foundational（三 repo 方法，皆限種子容器）。
2. **US1 → STOP & VALIDATE（/library 列種子＋刪除連清嵌入）= MVP**，可展示。
3. 疊 US2（重分類權重）→ 測試 → 展示。
4. 疊 US3（每日流保護）→ 只加驗證測試（結構已保證）。
5. Polish：docs、全套不回歸。

## Notes
- [P]＝不同檔無依賴；[Story] 溯源；每個 user story 獨立可測。
- **先確認測試失敗再實作**；每任務或邏輯群組後 commit。
- 純 DB CRUD、離線可測（教訓 1）；刪除連清嵌入免孤兒（教訓 8）；每日流唯讀由 repo 結構保證（研究 R1）。
- 無新 schema/模組/相依（YAGNI）；照 `/interests` CRUD 樣式。
