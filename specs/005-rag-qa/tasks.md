---
description: "Task list — RAG 問答（個人知識庫）增量 1 MVP"
---

# Tasks: RAG 問答（個人知識庫）增量 1 MVP

**Input**: `specs/005-rag-qa/`（plan.md، spec.md، research.md، data-model.md، contracts/cli-ask.md، quickstart.md）

**Tests**: 含測試任務——憲章原則 I（TDD 不可妥協）＋ spec 明訂。**測試先寫、先失敗、再實作。**

**Organization**: 依 user story 分期，各期可獨立實作與測試。

## Format: `[ID] [P?] [Story] Description`
- **[P]**：不同檔、無依賴 → 可並行
- **[Story]**：US1/US2/US3 溯源標籤

## Path Conventions
單一專案：`src/learnnews/`、`tests/`（repo 根）。

---

## Phase 1: Setup

- [ ] T001 [P] 建 `src/learnnews/rag/__init__.py`；確認 `tests/{contract,integration,unit}/` 就緒

---

## Phase 2: Foundational（阻塞所有 user story）

**⚠️ 完成前任何 user story 不能開工。**

- [ ] T002 [P] schema：在 `src/learnnews/store/schema.py` 新增 `entry_embeddings(entry_id, tag, dim, vector_json, PRIMARY KEY(entry_id,tag))`（data-model.md）
- [ ] T003 [P] 型別：`CorpusEntry`／`Source`／`RagAnswer`／`Scope` in `src/learnnews/rag/types.py`（含 `CorpusEntry.embed_text()`）
- [ ] T004 [P] Answerer 協定＋`StubAnswerer`（離線、grounded、逐點 `[n]`、只用傳入段落）in `src/learnnews/rag/answerer.py`
- [ ] T005 [P] `OpenAIAnswerer`（複用 `_post` `/chat/completions`、grounded prompt）in `src/learnnews/backends/openai_api.py`
- [ ] T006 `make_answerer(config)`（openai↔stub）in `src/learnnews/backends/factory.py`（依賴 T004、T005）
- [ ] T007 [P] config：`rag_top_k=6`、`rag_min_score=0.10`、`embedder_tag()` 輔助（`hashing-256`／`openai-<model>`）in `src/learnnews/config.py`
- [ ] T008 repository：`get_entry_embedding`／`save_entry_embedding`（INSERT OR REPLACE）in `src/learnnews/store/repository.py`（依賴 T002、T003）
- [ ] T009 repository：`ensure_embeddings(entries, embedder, tag)`（缺 tag 者**批次 `embed_many`** 補算並落庫）in `repository.py`（依賴 T008）
- [ ] T010 repository：`list_corpus_entries(today=False)`（`False`=全部 digests；`True`=`MAX(id)` 那份）→ `list[CorpusEntry]` in `repository.py`（依賴 T003）
- [ ] T011 repository：`save_digest` 內對新 entries **批次嵌入並存**（FR-009）in `repository.py`（依賴 T009）

**Checkpoint**：語料存取＋嵌入落庫＋合成後端就緒，可開 user story。

---

## Phase 3: User Story 1 - 對累積知識庫問答、答案可溯源（P1）🎯 MVP

**Goal**：`ask "問題"` 對**全部**已落庫匯整檢索、合成繁中答案、**逐點掛來源可回原文**。

**Independent Test**：種入多日已知內容條目，問命中某些條目的問題 → 答案出自那些條目且列出
對應來源；措辭不同的語義問題也命中。

### Tests（先寫、先失敗）
- [ ] T012 [P] [US1] 契約測試 `tests/contract/test_ask.py`：離線後端，累積問答回答＋列出來源（title/url）；用**實測會匹配**的字串（教訓 4）
- [ ] T013 [P] [US1] 整合測試 `tests/integration/test_rag_service.py`：檢索→合成→溯源；語義命中；`sources` 由檢索集合生成（原則 3）
- [ ] T014 [P] [US1] 單元測試 `tests/unit/test_entry_embeddings.py`：存/取、惰性回填、tag 不符則重嵌、`embed_many` 批次（不逐一）

### Implementation
- [ ] T015 [US1] `RagService.answer(question, scope, k, lang)` in `src/learnnews/rag/service.py`：載 scope 語料→`ensure_embeddings`→嵌問題→`cosine` 排序→top-k→`answerer.answer`→`RagAnswer`（`sources` 程式端生成）
- [ ] T016 [US1] `ask_cmd.handle(args)` in `src/learnnews/cli/ask_cmd.py`：`Config.from_env`→組 embedder/answerer→`RagService`→列印答案＋「來源：」清單
- [ ] T017 [US1] `ask` subparser（位置 `question`、`--lang`、`-k`；`set_defaults(func=ask_cmd.handle)`）in `src/learnnews/cli/__main__.py`

**Checkpoint**：US1 可獨立跑通——離線 `ask` 對累積庫回答且掛來源。**MVP 達成。**

---

## Phase 4: User Story 2 - 限定「今天」範圍問答（P2）

**Goal**：`--today` 把檢索限縮到最近一份匯整；預設仍跨累積。

**Independent Test**：種入「昨天」「今天」兩份匯整；同問題在預設與 `--today` 下，驗證來源範圍。

### Tests（先寫、先失敗）
- [ ] T018 [P] [US2] 整合測試 `tests/integration/test_rag_scope.py`：`--today` 來源只含最近一份、預設涵蓋全部

### Implementation
- [ ] T019 [US2] `RagService` 接 `Scope(today)` → 用 `list_corpus_entries(today)` in `src/learnnews/rag/service.py`
- [ ] T020 [US2] `--today` 旗標接進 `ask_cmd.py` 與 `__main__.py`

**Checkpoint**：US1＋US2 皆可獨立運作。

---

## Phase 5: User Story 3 - 誠實邊界：查無說無、失敗不炸（P3）

**Goal**：查無相關/空庫 → 明說「沒有相關材料」不杜撰；後端失敗 → 友善繁中、無堆疊。

**Independent Test**：(a) 空庫/無關問題 → 「沒有相關材料」且無編造；(b) 後端拋錯 → 友善繁中、退出碼 1、無 traceback。

### Tests（先寫、先失敗）
- [ ] T021 [P] [US3] 契約測試 `tests/contract/test_ask_boundaries.py`：空庫/無關→沒有相關材料且**不產生內容/來源**；後端 `OpenAIError`→友善繁中、無 `Traceback`

### Implementation
- [ ] T022 [US3] `RagService` 門檻濾除：低於 `rag_min_score` 或空語料 → `RagAnswer(no_material=True)`，**不呼叫合成後端** in `src/learnnews/rag/service.py`
- [ ] T023 [US3] `ask_cmd` 攔 `OpenAIError` → 友善繁中訊息、退出碼 1、不噴 traceback（教訓 3）in `src/learnnews/cli/ask_cmd.py`

**Checkpoint**：三個 user story 皆獨立可用。

---

## Phase 6: Polish & Cross-Cutting

- [ ] T024 [P] `docs/usage.md` 補 `ask` 用法（`--today`／`--lang`／`-k`、輸出格式、離線/真實）
- [ ] T025 真跑抽查忠實（真實後端，人工核對每論點有原文依據、無杜撰）——quickstart §3
- [ ] T026 跑 `quickstart.md` 全流程；`uv run pytest -q` 全套（新測綠燈、**既有 128 不回歸**）

---

## Dependencies & Execution Order

- **Setup（T001）** → **Foundational（T002–T011）** → **US1（T012–T017）** → US2（T018–T020）→ US3（T021–T023）→ Polish（T024–T026）。
- Foundational 阻塞全部 user story；US1 為 MVP，US2/US3 依附 US1 管線但各自可獨立測試。
- **repository.py 內 T008→T009→T010→T011 同檔、循序**（不可並行）。
- 各 user story 內：**測試先寫且失敗** → 再實作；service 先於 cmd 先於 parser。

### Parallel Opportunities
- Foundational 可並行：**T002、T003、T004、T005、T007**（不同檔）；T006 待 T004/T005；T008–T011 循序。
- US1 測試可並行：**T012、T013、T014**（不同檔）。
- 其後 T015→T016→T017 循序（service→cmd→parser）。

## Parallel Example: US1 測試
```bash
Task: "契約測試 tests/contract/test_ask.py"
Task: "整合測試 tests/integration/test_rag_service.py"
Task: "單元測試 tests/unit/test_entry_embeddings.py"
```

## Implementation Strategy
1. Setup → Foundational（阻塞）。
2. **US1 → STOP & VALIDATE（離線 `ask` 累積問答＋掛來源）= MVP**，可展示。
3. 疊 US2（範圍）→ 測試 → 展示。
4. 疊 US3（誠實邊界）→ 測試 → 展示。
5. Polish：文件、真跑抽查、全套不回歸。

## Notes
- [P]＝不同檔無依賴；[Story] 溯源；每個 user story 獨立可測。
- **先確認測試失敗再實作**；每任務或邏輯群組後 commit。
- 離線後端只驗接線；語義品質靠真實後端抽查（教訓 4 雜湊碰撞——fixture 用實測會匹配字串）。
