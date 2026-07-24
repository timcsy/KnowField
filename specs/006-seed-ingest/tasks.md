---
description: "Task list — 種子 ingest（個人知識庫）增量 2a"
---

# Tasks: 種子 ingest（個人知識庫）增量 2a

**Input**: `specs/006-seed-ingest/`（plan، spec، research، data-model، contracts/cli-ingest، quickstart）

**Tests**: 含測試——憲章原則 I（TDD 不可妥協）。**測試先寫、先失敗、再實作。**

**Organization**: 依 user story 分期，各期可獨立實作與測試。

## Format: `[ID] [P?] [Story] Description`
- **[P]**：不同檔、無依賴 → 可並行
- **[Story]**：US1/US2/US3 溯源標籤

## Path Conventions
單一專案：`src/learnnews/`、`tests/`（repo 根）。

---

## Phase 1: Setup

- [x] T001 [P] 建 `src/learnnews/seed/__init__.py`；確認 `tests/{contract,integration,unit}/` 就緒

---

## Phase 2: Foundational（阻塞所有 user story）

**⚠️ 完成前任何 user story 不能開工。**

- [x] T002 [P] schema：`digest_entries` 加 `source_class TEXT DEFAULT 'ordinary'` in `src/learnnews/store/schema.py`
- [x] T003 [P] config：`rag_explainer_weight=1.5`（env `LEARNNEWS_RAG_EXPLAINER_WEIGHT`）＋`SEEDS_DATE='__種子__'` 常數 in `src/learnnews/config.py`
- [x] T004 [P] `CorpusEntry` 加 `source_class` 欄 in `src/learnnews/rag/types.py`
- [x] T005 repository：`list_corpus_entries` SELECT 帶 `source_class`；`today=True` 加 `WHERE d.date != SEEDS_DATE`（排除種子容器）in `src/learnnews/store/repository.py`（依賴 T002、T004）
- [x] T006 repository：`get_or_create_seeds_digest() -> int`（哨兵種子容器）in `repository.py`（依賴 T002）

**Checkpoint**：語料帶 source_class、種子有家、`ask` 撈得到種子（尚無 ingest）。

---

## Phase 3: User Story 1 - 把一篇經典收進 KB、之後問得到（P1）🎯 MVP

**Goal**：`ingest <arXiv-id|url>` 抓單篇→消化→存為種子；`ask`（CLI＋web）檢索得到、可溯源；重複不重複。

**Independent Test**：用可注入假 http_get，ingest 一篇→ask 命中它→列來源含原文連結；再 ingest 同篇→「已在庫」不重插。

### Tests（先寫、先失敗）
- [x] T007 [P] [US1] 單元測試 `tests/unit/test_seed_fetch.py`：arXiv id 正規化（裸/`arXiv:`/`abs/`/版本）、`id_list` Atom 解析、URL 淺抽 title＋主文、去重鍵
- [x] T008 [P] [US1] 契約測試 `tests/contract/test_ingest.py`：離線假 http_get → ingest 成功印標題＋原文連結；重複 ingest → 「已在庫」、KB 不新增
- [x] T009 [P] [US1] 整合測試 `tests/integration/test_seed_retrieval.py`：種子進 KB → `ask` 檢索得到、列為來源、附原文連結（沿用增量 1）

### Implementation
- [x] T010 [US1] `seed/fetch.py`：`normalize_arxiv_id`、`fetch_arxiv_by_id`、`fetch_url`（`http_get` 可注入）→ `Item`
- [x] T011 [US1] repository：`seed_exists(external_id, url)`（`content_hash` 去重）＋`ingest_seed(item, article, source_class) -> entry_id` in `repository.py`（依賴 T006）
- [x] T012 [US1] `seed/service.py`：`SeedService.ingest(ref, explainer)`：正規化→查重→抓→`ArticleBuilder` 消化→`ingest_seed`→`ensure_embeddings`（**交易式：抓+消化成功才寫入**）
- [x] T013 [US1] `cli/ingest_cmd.py`（組後端→SeedService→列印）＋`ingest` subparser（位置 `ref`、`--explainer`）in `src/learnnews/cli/__main__.py`

**Checkpoint**：離線 `ingest` 收單篇→`ask` 問得到＋溯源→重複不重複。**MVP 達成。**

---

## Phase 4: User Story 2 - 解說文勝過平庸快訊（P2）

**Goal**：`--explainer` 種子檢索權重高於一般；門檻仍用原始 cosine 把關。

**Independent Test**：種一篇解說文＋一篇一般，兩者對某問題都相關 → 解說文排序在前。

### Tests（先寫、先失敗）
- [x] T014 [P] [US2] 整合測試 `tests/integration/test_explainer_weight.py`：解說文種子與一般種子同相關 → 解說文排序在前 / 更易入選來源

### Implementation
- [x] T015 [US2] `rag/service.py`：排序改 `cosine × _weight(source_class)`（`explainer`→`rag_explainer_weight`，餘 1.0）；**入選門檻仍套原始 cosine `>= min_score`**

**Checkpoint**：US1＋US2 皆可獨立運作（`--explainer` 在 T013 已可標，此期讓它影響排序）。

---

## Phase 5: User Story 3 - 誠實邊界：抓不到不炸、不半殘（P3）

**Goal**：抓取/解析/後端失敗 → 友善繁中、退出碼 1、無 traceback、**KB 無半殘種子**。

**Independent Test**：假 http_get 拋 `SourceUnavailable`／後端拋 `OpenAIError` → 友善訊息、退出碼 1、種子容器未新增。

### Tests（先寫、先失敗）
- [x] T016 [P] [US3] 契約測試 `tests/contract/test_ingest_boundaries.py`：抓取失敗→友善繁中、退出碼 1、無 `Traceback`、**KB 條目數不變（無半殘）**

### Implementation
- [x] T017 [US3] `ingest_cmd` 攔 `SourceUnavailable`／`OpenAIError` → 友善繁中訊息、退出碼 1（`SeedService` 的交易式順序已保證失敗不寫入，T012）

**Checkpoint**：三個 user story 皆獨立可用。

---

## Phase 6: Polish & Cross-Cutting

- [x] T018 [P] `docs/usage.md` 補 `ingest` 用法（arXiv/URL、`--explainer`、去重、失敗行為）
- [ ] T019 真跑抽查（真實後端）：`ingest` 一篇真 arXiv → `ask` 問到＋溯源 → 重複去重 → 失敗 case——quickstart §1–5
- [x] T020 跑 `quickstart.md` 全流程；`uv run pytest -q` 全套（新測綠燈、**既有 147 不回歸**）

---

## Dependencies & Execution Order

- **Setup（T001）** → **Foundational（T002–T006）** → **US1（T007–T013）** → US2（T014–T015）→ US3（T016–T017）→ Polish（T018–T020）。
- Foundational 阻塞全部；US1 為 MVP，US2/US3 依附 US1 管線但各自可獨立測試。
- **`repository.py` 內 T005→T006→T011 同檔、循序**（不可並行）。
- 各 user story 內：**測試先寫且失敗** → 再實作；fetch/repo 先於 service 先於 cmd。

### Parallel Opportunities
- Foundational 可並行：**T002、T003、T004**（不同檔）；T005/T006 循序（repository.py）。
- US1 測試可並行：**T007、T008、T009**（不同檔）。
- 其後 T010→T011→T012→T013 大致循序（fetch→repo→service→cmd）。

## Parallel Example: US1 測試
```bash
Task: "單元測試 tests/unit/test_seed_fetch.py"
Task: "契約測試 tests/contract/test_ingest.py"
Task: "整合測試 tests/integration/test_seed_retrieval.py"
```

## Implementation Strategy
1. Setup → Foundational（阻塞）。
2. **US1 → STOP & VALIDATE（離線 `ingest`→`ask` 問到＋去重）= MVP**，可展示。
3. 疊 US2（解說文權重）→ 測試 → 展示。
4. 疊 US3（誠實邊界）→ 測試 → 展示。
5. Polish：docs、真跑抽查、全套不回歸。

## Notes
- [P]＝不同檔無依賴；[Story] 溯源；每個 user story 獨立可測。
- **先確認測試失敗再實作**；每任務或邏輯群組後 commit。
- 抓取以可注入 `http_get` 離線測（教訓 1）；檢索沿用增量 1 校準門檻（教訓 4）；失敗攔截（教訓 3）。
- 種子容器「假裝成 digest」是刻意取捨（免動增量 1 嵌入表），見 research R1。
