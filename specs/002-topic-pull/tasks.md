---
description: "Task list — 主題拉取深挖（拉模式）"
---

# Tasks: 主題拉取深挖（拉模式）

**Input**: Design documents from `specs/002-topic-pull/`

**Prerequisites**: plan.md、spec.md、research.md、data-model.md、contracts/

**Tests**: TDD（憲章原則 I，不可妥協）——測試先寫、先失敗，再實作。

**Organization**: 依使用者故事分組。**大量複用階段 2**（sources／dedup／ranking／
summarize／backends／store／digest），只新增薄薄一層 `pull/`。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：可平行（不同檔案、無未完成相依）
- 面向使用者輸出與文件為繁體中文（憲章原則 II）

## Path Conventions
單一專案：新增於 `src/learnnews/pull/` 與 `src/learnnews/cli/pull_cmd.py`；測試於 `tests/`。

---

## Phase 1: Setup

- [X] T001 建立拉模式結構：`src/learnnews/pull/__init__.py`、`pull/types.py`、`pull/topic_query.py`、
  `pull/service.py`、`src/learnnews/cli/pull_cmd.py`、`src/learnnews/cli/pull_render.py`（佔位）per plan.md

---

## Phase 2: Foundational（阻斷性前置）

- [X] T002 [P] 定義 `TopicQuery`、`PullResult`、`PullEntry` dataclass（含 is_empty、truncated_count、
  missing_sources）於 `src/learnnews/pull/types.py`（per data-model.md）
- [X] T003 [P] 單元測試（先失敗）：主題查詢建構與來源可查詢性分類於 `tests/unit/test_topic_query.py`
- [X] T004 主題查詢建構——arXiv `search_query=all:<topic>`、標記來源可查詢/不可查詢於
  `src/learnnews/pull/topic_query.py`（使 T003 通過；依既有 sources/base）

**Checkpoint**：拉模式地基就緒，可開始使用者故事。

---

## Phase 3: User Story 1 - 對一個主題拉取相關原礦 (Priority: P1) 🎯 MVP

**Goal**：給定主題 → 跨來源擴展、去重、依主題排序、直達原文；預設附一句定位，`--raw` 純原礦。

**Independent Test**：以主題＋來源樣本執行 `learnnews pull`，驗證去重、依主題相關性排序、
每則含原文連結；`--raw` 時無任何生成文字。

### Tests for User Story 1（先寫、先失敗）⚠️

- [X] T005 [P] [US1] Contract test：`pull` CLI（去重、原文連結、排序、--raw、缺漏、空）於 `tests/contract/test_cli_pull.py`
- [X] T006 [P] [US1] Integration test：主題拉取＋跨源去重（情境 A/C）於 `tests/integration/test_pull_dedup.py`
- [X] T007 [P] [US1] Integration test：原文連結 100%（情境 D）＋不代勞不下結論（情境 E）於 `tests/integration/test_pull_quality.py`
- [X] T008 [P] [US1] Integration test：`--raw` 零生成文字（情境 B／SC-007）＋來源缺漏（F）＋冷門空結果（G）於 `tests/integration/test_pull_modes.py`
- [X] T009 [P] [US1] Unit test：PullService 擴展→去重→依主題排序→(可選)摘要於 `tests/unit/test_pull_service.py`

### Implementation for User Story 1

- [X] T010 [US1] PullService（擴展搜尋＋相關性過濾＋去重＋依主題排序＋上限＋可選摘要）於 `src/learnnews/pull/service.py`（依 T004；複用 dedup/ranking/summarize/backends）
- [X] T011 [US1] 拉取結果渲染（terminal/markdown/json；`--raw` 純標題＋來源＋連結、不生成文字）於 `src/learnnews/cli/pull_render.py`
- [X] T012 [US1] CLI `pull`（topic、--limit、--raw/--no-summary、--format、--output、--json）於 `src/learnnews/cli/pull_cmd.py`（依 T010、T011）
- [X] T013 [US1] 註冊 `pull` 子指令到入口於 `src/learnnews/cli/__main__.py`
- [X] T014 [US1] 拉取流程結構化日誌與繁中錯誤訊息（原則 V）於 `src/learnnews/pull/service.py`、`src/learnnews/cli/pull_cmd.py`

**Checkpoint**：US1 可獨立運作與測試 = **MVP**（直接給 topic 字串）。

---

## Phase 4: User Story 2 - 從推匯整一鍵深挖 (Priority: P2)

**Goal**：從最近一次每日匯整的第 N 則取其主題，直接發起拉取。

**Independent Test**：跑一次 digest（落庫其 entries）後，`pull --from-digest <rank>` 回傳該則主題的擴展結果。

### Tests for User Story 2（先寫、先失敗）⚠️

- [X] T015 [P] [US2] Contract test：`pull --from-digest <rank>` 於 `tests/contract/test_cli_pull_from_digest.py`

### Implementation for User Story 2

- [X] T016 [US2] 匯整條目落庫（digest 執行時保存 entries：item＋matched_topic）於 `src/learnnews/store/repository.py`、`src/learnnews/digest/builder.py`
- [X] T017 [US2] `pull --from-digest <rank>`：讀最近匯整第 N 則主題發起拉取於 `src/learnnews/cli/pull_cmd.py`（依 T016、T010）

**Checkpoint**：US1＋US2 皆可獨立運作。

---

## Phase 5: Polish & Cross-Cutting

- [X] T018 [P] 執行 quickstart.md 情境 A–G 端到端驗證
- [X] T019 [P] 更新 `docs/usage.md` 加入 `pull` 指令說明（繁中，憲章原則 II）
- [X] T020 [P] 補齊剩餘單元測試覆蓋於 `tests/unit/`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup（P1）**：無相依。
- **Foundational（P2）**：依 Setup；阻斷使用者故事。
- **US1（P3）**：依 Foundational；不依賴其他故事（直接給 topic 即可獨立測試）。
- **US2（P4）**：依 Foundational＋US1（複用 PullService）；另需匯整落庫（T016）。
- **Polish（P5）**：依所需故事完成。

### Within Each User Story
- 測試先寫且**先失敗**，再實作（原則 I）。
- types → topic_query → service → render → CLI → 入口註冊。

### Parallel Opportunities
- Foundational：T002、T003 可平行。
- US1 測試 T005–T009 可平行；實作中 T011（render）與 T010（service）可平行起步，
  CLI（T012）待兩者。
- Polish T018–T020 可平行。

---

## Parallel Example: User Story 1
```bash
# 先啟動 US1 全部測試（先失敗）：
Task: "Contract test pull CLI in tests/contract/test_cli_pull.py"
Task: "Integration test 去重 in tests/integration/test_pull_dedup.py"
Task: "Integration test --raw 模式 in tests/integration/test_pull_modes.py"
Task: "Unit test PullService in tests/unit/test_pull_service.py"
```

---

## Implementation Strategy

### MVP First（僅 User Story 1）
1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 →
4. **STOP 並驗證**：quickstart 情境 A–G → 可展示（拉模式 MVP）。

### Incremental Delivery
1. Setup＋Foundational → 地基。
2. US1 → 獨立測試 → 拉模式 MVP（直接給 topic）。
3. US2 → 從匯整一鍵深挖 → 推拉銜接。

---

## Notes
- [P]＝不同檔案、無未完成相依。
- 每個功能任務前先確認其測試已寫且失敗（TDD）。
- 拉輸出：預設一句定位（複用摘要守衛＋鷹架剝除防線）；`--raw` 完全不呼叫 LLM。
- 每則必有直達原文連結，否則排除或標缺漏（不靜默）。
- 不依賴 Semantic Scholar citation graph（429）；不落庫拉取結果（YAGNI）。
