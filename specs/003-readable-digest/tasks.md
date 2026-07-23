---
description: "Task list — 可讀文章式消化（階段 5）"
---

# Tasks: 可讀文章式消化（升級摘要）

**Input**: Design documents from `specs/003-readable-digest/`

**Prerequisites**: plan.md、spec.md、research.md、data-model.md、contracts/

**Tests**: TDD（憲章原則 I，不可妥協）——測試先寫、先失敗，再實作。

**Organization**: 依使用者故事分組。**大量複用階段 1–4**；核心是以 Article 取代 Summary、
新增抓圖層。

## Format: `[ID] [P?] [Story] Description`
- **[P]**：可平行（不同檔案、無未完成相依）
- 面向使用者輸出與文件為繁體中文（憲章原則 II）

## Path Conventions
單一專案：新增 `src/learnnews/summarize/article.py`、`src/learnnews/media/`；改 digest/pull/render。

---

## Phase 1: Setup

- [ ] T001 建立骨架：`src/learnnews/summarize/article.py`、`src/learnnews/media/{__init__,figure_extract,ai_image}.py`（佔位）per plan.md

---

## Phase 2: Foundational（阻斷性前置）

- [ ] T002 [P] 定義 `Article`、`Figure` dataclass（含 body、source_url、figure、degraded；Figure.kind＝原文/AI 示意）於 `src/learnnews/summarize/article.py`（per data-model.md）
- [ ] T003 entry 遷移：`DigestEntry`／`PullEntry` 由 `summary` 改帶 `article`（`--raw` 時為 None）於 `src/learnnews/models/__init__.py`、`src/learnnews/pull/types.py`；同步更新既有受影響測試斷言
- [ ] T004 [P] `digest_entries` schema 增欄（article_body、figure_url、figure_kind）於 `src/learnnews/store/schema.py`、`src/learnnews/store/repository.py`

**Checkpoint**：Article 地基就緒，可開始使用者故事。

---

## Phase 3: User Story 1 - 讀每則的可讀散文消化 (Priority: P1) 🎯 MVP

**Goal**：每則材料產出可讀散文（完整傳達、忠實不捏造、不下結論），附一鍵原文；推拉皆套用；後端失敗優雅降級。

**Independent Test**：對一則材料產生散文消化，驗證為連貫散文（非列點）、不含原文沒有的數據、附直達原文連結；後端失敗時退精簡不炸。

### Tests for User Story 1（先寫、先失敗）⚠️

- [ ] T005 [P] [US1] Unit test：ArticleBuilder 產散文＋忠實守衛（不下結論、不捏造之行為）於 `tests/unit/test_article_builder.py`
- [ ] T006 [P] [US1] Contract test：digest/pull 輸出散文（非列點）＋一鍵原文連結於 `tests/contract/test_cli_article.py`
- [ ] T007 [P] [US1] Integration test：忠實不捏造（情境 C）＋不下工具結論（情境 D）於 `tests/integration/test_article_faithful.py`
- [ ] T008 [P] [US1] Integration test：推與拉皆走散文（情境 A/B）於 `tests/integration/test_article_both_modes.py`
- [ ] T009 [P] [US1] Integration test：優雅降級（情境 H：散文後端失敗退精簡、退出碼 0、不炸）於 `tests/integration/test_article_degrade.py`

### Implementation for User Story 1

- [ ] T010 [US1] ArticleBuilder（散文生成＋程式端守衛：剝鷹架、標 degraded）＋ 散文 prompt/stub 於 `src/learnnews/summarize/article.py`、`src/learnnews/summarize/llm.py`（依 T002）
- [ ] T011 [US1] digest builder 產 `Article` 取代 `Summary` 於 `src/learnnews/digest/builder.py`（依 T010、T003）
- [ ] T012 [US1] pull service 產 `Article` 於 `src/learnnews/pull/service.py`（依 T010、T003）
- [ ] T013 [US1] 渲染散文文章（markdown/terminal，含一鍵原文）於 `src/learnnews/cli/render.py`、`src/learnnews/cli/pull_render.py`
- [ ] T014 [US1] 優雅降級：散文後端失敗 → 退精簡＋標 degraded、退出碼 0、不炸於 `src/learnnews/summarize/article.py`、`src/learnnews/cli/digest_cmd.py`、`src/learnnews/cli/pull_cmd.py`（FR-011）

**Checkpoint**：US1 可獨立運作與測試 = **MVP**（散文消化，暫無圖）。

---

## Phase 4: User Story 2 - 配圖幫助吸收 (Priority: P2)

**Goal**：文章配圖——原文圖優先（可溯源）；無則可選 AI 示意圖，必標「AI 示意・非原文」。

**Independent Test**：有原文圖者文章帶原文圖並標來源；無原文圖且 `--ai-image` 時附 AI 圖並標示；未啟用則純文字，不阻塞。

### Tests for User Story 2（先寫、先失敗）⚠️

- [ ] T015 [P] [US2] Contract test：figure_extract 從 RSS／arXiv HTML 樣本抓圖、取不到回 None 於 `tests/contract/test_figure_extract.py`
- [ ] T016 [P] [US2] Unit test：AI 圖必標「AI 示意・非原文」於 `tests/unit/test_ai_image_label.py`
- [ ] T017 [P] [US2] Integration test：原文圖內嵌（情境 E）＋AI 圖標示（情境 F）於 `tests/integration/test_article_images.py`

### Implementation for User Story 2

- [ ] T018 [US2] figure_extract（RSS enclosure/img、arXiv HTML；best-effort，取不到回 None）於 `src/learnnews/media/figure_extract.py`
- [ ] T019 [US2] ai_image（OpenAI 格式 images 端點，可選；回傳標 kind=AI 示意）於 `src/learnnews/media/ai_image.py`
- [ ] T020 [US2] 配圖接入 ArticleBuilder（原文圖優先、`--ai-image` 才 AI 圖）＋渲染標示於 `src/learnnews/summarize/article.py`、`src/learnnews/cli/render.py`、`src/learnnews/cli/pull_render.py`（依 T018、T019）
- [ ] T021 [US2] CLI 加 `--ai-image` 旗標於 `src/learnnews/cli/__main__.py`

**Checkpoint**：US1＋US2 皆可運作（散文＋圖）。

---

## Phase 5: User Story 3 - 純原礦模式保留 (Priority: P3)

**Goal**：`--raw` 得純原礦（僅標題＋來源＋連結），不生成文字或圖、不呼叫後端。

**Independent Test**：`--raw` 執行，驗證無散文無圖、未呼叫生成後端。

### Tests for User Story 3（先寫、先失敗）⚠️

- [ ] T022 [P] [US3] Contract test：`--raw` 純原礦、無散文無圖、未呼叫後端於 `tests/contract/test_cli_raw_preserved.py`

### Implementation for User Story 3

- [ ] T023 [US3] 確認/補強 `--raw` 路徑跳過 ArticleBuilder 與抓圖於 `src/learnnews/cli/digest_cmd.py`、`src/learnnews/cli/pull_cmd.py`

**Checkpoint**：三故事皆可獨立運作。

---

## Phase 6: Polish & Cross-Cutting

- [ ] T024 [P] 執行 quickstart.md 情境 A–H 端到端驗證
- [ ] T025 [P] 更新 `docs/usage.md`（散文消化、`--ai-image`）
- [ ] T026 [P] 補齊剩餘單元測試覆蓋於 `tests/unit/`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup（P1）**：無相依。
- **Foundational（P2）**：依 Setup；阻斷使用者故事（Article 模型／entry 遷移／schema）。
- **US1（P3）**：依 Foundational；核心散文消化，獨立可測。
- **US2（P4）**：依 Foundational＋US1（圖接入 Article）。
- **US3（P5）**：依 Foundational；`--raw` 多為驗證既有路徑。
- **Polish（P6）**：依所需故事完成。

### Within Each User Story
- 測試先寫且**先失敗**，再實作（原則 I）。
- Article 模型 → builder → digest/pull → render → 降級。

### Parallel Opportunities
- Foundational：T002、T004 可平行（T003 遷移需先於依賴它的實作）。
- US1 測試 T005–T009 可平行；US2 測試 T015–T017 可平行。
- Polish T024–T026 可平行。

---

## Parallel Example: User Story 1
```bash
Task: "Unit test ArticleBuilder in tests/unit/test_article_builder.py"
Task: "Contract test 散文輸出 in tests/contract/test_cli_article.py"
Task: "Integration test 忠實不捏造 in tests/integration/test_article_faithful.py"
Task: "Integration test 優雅降級 in tests/integration/test_article_degrade.py"
```

---

## Implementation Strategy

### MVP First（僅 User Story 1）
1. Setup → 2. Foundational → 3. US1（散文消化，暫無圖）→ 4. **STOP 並驗證**（quickstart A–D、H）→ 可展示。

### Incremental Delivery
1. Setup＋Foundational → 地基。
2. US1 → 散文消化 MVP。
3. US2 → 加配圖。
4. US3 → 確認純原礦。

---

## Notes
- [P]＝不同檔案、無未完成相依。
- 每個功能任務前先確認其測試已寫且失敗（TDD）。
- 散文 MUST 忠實（不捏造）＋不下工具結論；每則一鍵原文（原則 3/4）。
- AI 圖 MUST 標「AI 示意・非原文」（原則 3）。
- 後端/抓圖失敗優雅降級、不炸 traceback（原則 V、experience 教訓 3）。
- 真實後端接上後 MUST 抽查散文忠實度（experience 教訓 2）。
