---
description: "Task list — 每日推播分診（推模式 MVP）"
---

# Tasks: 每日推播分診（推模式 MVP）

**Input**: Design documents from `specs/001-daily-triage-digest/`

**Prerequisites**: plan.md、spec.md、research.md、data-model.md、contracts/

**Tests**: 本專案採 TDD（憲章原則 I，不可妥協）——**所有測試任務先寫、先失敗，再實作**。

**Organization**: 依使用者故事分組，每個故事可獨立實作與測試。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行（不同檔案、無未完成相依）
- **[Story]**: US1／US2／US3
- 所有面向使用者輸出與文件為繁體中文（憲章原則 II）

## Path Conventions

單一專案：核心於 `src/knowfield/`，測試於 `tests/`（見 plan.md 結構決策）。

---

## Phase 1: Setup（共用基礎）

- [X] T001 建立專案結構（`src/knowfield/{sources,models,dedup,ranking,summarize,digest,store,cli}/`、`tests/{contract,integration,unit}/`）per plan.md
- [X] T002 初始化 Python 專案 `pyproject.toml`（Python 3.12+，相依：httpx、feedparser、sentence-transformers、anthropic、pytest）
- [X] T003 [P] 設定 lint/format（ruff、black）於 `pyproject.toml`
- [X] T004 [P] 設定 pytest 與離線測試慣例（`tests/conftest.py`：錄製樣本 fixtures、embedding 與 LLM 以 stub，禁打真實 API）

---

## Phase 2: Foundational（阻斷性前置，所有故事之前）

**⚠️ CRITICAL**：本階段完成前，任何使用者故事不得開工。

- [X] T005 [P] 單元測試（先失敗）：SQLite schema 與 repository round-trip，於 `tests/unit/test_store.py`
- [X] T006 依 data-model.md 實作 SQLite schema 於 `src/knowfield/store/schema.py`
- [X] T007 [P] 定義資料實體（Source、Item、EventCluster、InterestProfile、Digest、Summary、BehaviorSignal）於 `src/knowfield/models/`
- [X] T008 實作 store repository（CRUD）於 `src/knowfield/store/repository.py`（依 T006、T007；使 T005 通過）
- [X] T009 [P] 設定與結構化日誌（原則 V）於 `src/knowfield/config.py`、`src/knowfield/logging_setup.py`
- [X] T010 [P] SourceAdapter 基底介面與 `SourceUnavailable` 例外於 `src/knowfield/sources/base.py`（per contracts/source-adapter.md）
- [X] T011 [P] Embedding 包裝（`embed()` 介面＋本地模型＋離線 stub）於 `src/knowfield/ranking/embeddings.py`
- [X] T012 [P] 摘要 LLM 包裝（Claude `claude-haiku-4-5`）＋錄製回應 stub 於 `src/knowfield/summarize/llm.py`

**Checkpoint**：基礎就緒，可開始使用者故事。

---

## Phase 3: User Story 1 - 收到每日分診匯整 (Priority: P1) 🎯 MVP

**Goal**：給定來源與一份興趣清單，執行一次每日匯整——去重、依興趣排序、封頂摘要、直達原文。

**Independent Test**：以錄製來源樣本＋預設興趣清單執行 `knowfield digest`，驗證輸出為去重、排序後、每則含封頂摘要與原文連結的匯整。

### Tests for User Story 1（先寫、先失敗）⚠️

- [X] T013 [P] [US1] Contract test：`digest` CLI（去重、原文連結、摘要封頂、缺漏、空匯整）於 `tests/contract/test_cli_digest.py`
- [X] T014 [P] [US1] Contract test：ArxivAdapter（樣本解析、SourceUnavailable）於 `tests/contract/test_arxiv_adapter.py`
- [X] T015 [P] [US1] Contract test：HFPapersAdapter 於 `tests/contract/test_hf_adapter.py`
- [X] T016 [P] [US1] Contract test：SemanticScholarAdapter（含指數退避）於 `tests/contract/test_s2_adapter.py`
- [X] T017 [P] [US1] Contract test：RssAdapter（RSS／email-ingestion Atom）於 `tests/contract/test_rss_adapter.py`
- [X] T018 [P] [US1] Integration test：跨源去重（quickstart 情境 A/B）於 `tests/integration/test_dedup_digest.py`
- [X] T019 [P] [US1] Integration test：原文連結 100%（情境 C）＋摘要 ≤2 句不代勞（情境 D）於 `tests/integration/test_digest_quality.py`
- [X] T020 [P] [US1] Integration test：來源缺漏不靜默（情境 F）＋空匯整（情境 G）於 `tests/integration/test_digest_resilience.py`
- [X] T021 [P] [US1] Unit test：去重精確層＋語義層於 `tests/unit/test_dedup.py`
- [X] T022 [P] [US1] Unit test：興趣相關性排序於 `tests/unit/test_ranking.py`
- [X] T023 [P] [US1] Unit test：摘要長度守衛（SC-004）於 `tests/unit/test_summary_guard.py`

### Implementation for User Story 1

- [X] T024 [P] [US1] ArxivAdapter 於 `src/knowfield/sources/arxiv.py`（依 T010）
- [X] T025 [P] [US1] HFPapersAdapter 於 `src/knowfield/sources/hf_papers.py`（依 T010）
- [X] T026 [P] [US1] SemanticScholarAdapter（指數退避）於 `src/knowfield/sources/semantic_scholar.py`（依 T010）
- [X] T027 [P] [US1] RssAdapter 於 `src/knowfield/sources/rss.py`（依 T010）
- [X] T028 [US1] 去重精確層（content_hash／external_id／canonical URL）於 `src/knowfield/dedup/exact.py`
- [X] T029 [US1] 去重語義層（embedding 叢集＋entity 加權）於 `src/knowfield/dedup/semantic.py`（依 T011、T028）
- [X] T030 [US1] 興趣相關性排序於 `src/knowfield/ranking/relevance.py`（依 T011）
- [X] T031 [US1] 封頂摘要器（提示禁結論式分析＋程式端長度守衛）於 `src/knowfield/summarize/summarizer.py`（依 T012）
- [X] T032 [US1] 預設興趣清單讀取（供 US1 獨立測試）於 `src/knowfield/ranking/interest_preset.py`
- [X] T033 [US1] 匯整組裝（排序、上限 ≤15、truncated_count、missing_sources、is_empty）於 `src/knowfield/digest/builder.py`（依 T028–T032）
- [X] T034 [US1] CLI `digest`（--date/--limit/--format/--output/--json）於 `src/knowfield/cli/digest_cmd.py`（依 T033）
- [X] T035 [US1] 匯整流程結構化日誌與繁中錯誤訊息（原則 V）於 `src/knowfield/digest/builder.py`、`cli/digest_cmd.py`

**Checkpoint**：US1 可獨立運作與測試 = **MVP**。

---

## Phase 4: User Story 2 - 掌控自己的興趣清單 (Priority: P2)

**Goal**：使用者可明講、檢視、修改、覆寫興趣清單，變更於次日匯整生效；明講優先於學習推斷。

**Independent Test**：`interests add/remove/set` 後 `list` 反映變更，且下次 `digest` 套用。

### Tests for User Story 2（先寫、先失敗）⚠️

- [X] T036 [P] [US2] Contract test：`interests` CLI（list/add/remove/set）於 `tests/contract/test_cli_interests.py`
- [X] T037 [P] [US2] Integration test：興趣變更於次日匯整生效（SC-005）於 `tests/integration/test_interest_apply.py`
- [X] T038 [P] [US2] Unit test：明講優先於學習權重於 `tests/unit/test_interest_precedence.py`

### Implementation for User Story 2

- [X] T039 [US2] InterestProfile 服務（CRUD、明講優先）於 `src/knowfield/interests/service.py`（依 T008 store）
- [X] T040 [US2] CLI `interests`（list/add/remove/set）於 `src/knowfield/cli/interests_cmd.py`（依 T039）
- [X] T041 [US2] 將 InterestProfile 接入排序，取代 US1 預設（保明講優先）於 `src/knowfield/ranking/relevance.py`（依 T039、T030）

**Checkpoint**：US1＋US2 皆可獨立運作。

---

## Phase 5: User Story 3 - 從行為校準排序 (Priority: P3)

**Goal**：依點擊／略過逐步校準排序，但明講永遠可覆寫。

**Independent Test**：固定興趣清單下模擬持續點擊某主題，後續匯整該主題排序上升；明講覆寫仍優先。

### Tests for User Story 3（先寫、先失敗）⚠️

- [X] T042 [P] [US3] Integration test：反覆點擊提升排序＋明講覆寫優先於 `tests/integration/test_behavior_learning.py`
- [X] T043 [P] [US3] Unit test：learned_weights 更新於 `tests/unit/test_learned_weights.py`

### Implementation for User Story 3

- [X] T044 [US3] BehaviorSignal 擷取（clicked/skipped）於 `src/knowfield/interests/behavior.py`（依 T008）
- [X] T045 [US3] learned_weights 校準（明講仍優先）於 `src/knowfield/interests/learning.py`（依 T044、T039）
- [X] T046 [US3] 將 learned_weights 疊入排序於 `src/knowfield/ranking/relevance.py`（依 T045、T041）

**Checkpoint**：三個故事皆可獨立運作。

---

## Phase 6: Polish & Cross-Cutting

- [X] T047 [P] CLI `sources`（list/enable/disable）＋contract test 於 `src/knowfield/cli/sources_cmd.py`、`tests/contract/test_cli_sources.py`
- [X] T048 [P] 執行 quickstart.md 情境 A–G 端到端驗證
- [X] T049 [P] 繁中使用說明文件（憲章原則 II）於 `docs/usage.md`
- [X] T050 程式碼整理與重構（YAGNI，去除重複）
- [X] T051 [P] 補齊剩餘單元測試覆蓋於 `tests/unit/`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup（P1）**：無相依，可立即開始。
- **Foundational（P2）**：依 Setup；**阻斷所有使用者故事**。
- **User Stories（P3+）**：皆依 Foundational 完成；之後可平行或依 P1→P2→P3 順序。
- **Polish（P6）**：依所需故事完成。

### User Story Dependencies
- **US1（P1）**：Foundational 後即可開始，不依賴其他故事（用預設興趣清單保持獨立可測）。
- **US2（P2）**：Foundational 後可開始；T041 會取代 US1 的預設興趣讀取，但 US1 仍可獨立測試。
- **US3（P3）**：Foundational 後可開始；T046 疊加於 US2 的排序，但明講優先不變。

### Within Each User Story
- 測試先寫且**先失敗**，再實作（憲章原則 I）。
- models → services → CLI → 整合。

### Parallel Opportunities
- Setup 中 T003、T004 可平行。
- Foundational 中 T005、T007、T009、T010、T011、T012 可平行（不同檔案）。
- 各故事的測試任務（標 [P]）可一起啟動。
- US1 的四個 adapter（T024–T027）可平行。
- Foundational 完成後，若人力足夠，US1／US2／US3 可平行開發。

---

## Parallel Example: User Story 1

```bash
# 先啟動 US1 全部測試（先失敗）：
Task: "Contract test digest CLI in tests/contract/test_cli_digest.py"
Task: "Contract test ArxivAdapter in tests/contract/test_arxiv_adapter.py"
Task: "Integration test 跨源去重 in tests/integration/test_dedup_digest.py"
Task: "Unit test 去重 in tests/unit/test_dedup.py"

# 再平行實作四個來源 adapter：
Task: "ArxivAdapter in src/knowfield/sources/arxiv.py"
Task: "HFPapersAdapter in src/knowfield/sources/hf_papers.py"
Task: "SemanticScholarAdapter in src/knowfield/sources/semantic_scholar.py"
Task: "RssAdapter in src/knowfield/sources/rss.py"
```

---

## Implementation Strategy

### MVP First（僅 User Story 1）
1. 完成 Phase 1 Setup。
2. 完成 Phase 2 Foundational（阻斷性）。
3. 完成 Phase 3 US1。
4. **STOP 並驗證**：以 quickstart 情境 A–G 獨立測試 US1。
5. 可展示／部署（MVP！）。

### Incremental Delivery
1. Setup ＋ Foundational → 基礎就緒。
2. US1 → 獨立測試 → MVP。
3. US2 → 獨立測試 → 交付。
4. US3 → 獨立測試 → 交付。

---

## Notes
- [P] = 不同檔案、無未完成相依。
- 每個功能任務前先確認其測試已寫且失敗（TDD）。
- 面向使用者輸出全繁中；摘要嚴守「一句定位＋一句為何值得看」，禁結論式分析。
- 每則進匯整條目必有直達原文連結，否則排除或標缺漏（不靜默）。
- 每完成一個任務或邏輯群組即 commit。
