# Tasks：根因萃取（冊封根因＝吸引子本體）

**功能目錄**：`specs/012-root-cause/`　｜　**TDD 強制**　｜　基準測試：219（不回歸）
**設計源**：`concepts/有吸引子的場.md`（試金石、拆開的 optimizer、不自動冊封）

依 spec 的 US 分期。`[P]`＝可並行（不同檔、無未完成相依）。

## Phase 1：Setup

- [x] T001 唯讀盤點復用點：`store/schema.py` `_migrate`、`store/repository.py`（`list_corpus_entries`／
  `ensure_embeddings`／`delete_seed` 樣式）、`rag/service.py` `_weight`、`backends/openai_api._post`、
  `web/app.py` `/library` anoint 樣式、`templates/library.html`。

## Phase 2：Foundational（阻擋所有 US）

- [x] T002 `store/schema.py`：加 `why_nodes` 表（`CREATE TABLE IF NOT EXISTS`）＋`_migrate` 冪等
  （既有 db 也建表）。欄位見 data-model。
- [x] T003 `config.py`：加 `rag_root_weight`（預設 2.0），`from_env` 讀 `KNOWFIELD_RAG_ROOT_WEIGHT`。

## Phase 3：US1 AI 抽根因＋試金石（P1，萃取核心）

> 獨立測試：`RootCauseExtractor` 產 Candidate（claim＋7 條試金石＋霧詞＋no_material）；離線 stub 綠燈。

### 測試先行（TDD）
- [x] T004 [P] [US1] `tests/unit/test_rootcause.py`：`StubExtractor.extract` 回 Candidate（claim 非空、
  touchstones 7 條、no_material=False、零外部呼叫）。
- [x] T005 [P] [US1] `tests/unit/test_rootcause.py` 續：`OpenAIExtractor`（注入 poster 回 JSON）→ 解析
  claim/touchstones/fog/no_material；poster 拋 → `SourceUnavailable`；抽不出 → `no_material=True`。

### 實作
- [x] T006 [US1] 新增 `src/knowfield/rootcause/extract.py`：`Candidate` 型別＋`RootCauseExtractor`
  Protocol＋`StubExtractor`（確定性、試金石全「待驗」passed=False）＋`OpenAIExtractor`（`_post` chat、
  system 明令逐條試金石自我反駁/標霧詞/只用材料不杜撰、輸出 JSON、解析、失敗拋 `SourceUnavailable`）。
- [x] T007 [US1] `backends/factory.py` 加 `make_root_cause_extractor(config)`。

## Phase 4：US2 冊封（人挑）＋ US3 餵回 ask（P1，閉環）

> 獨立測試：why_nodes CRUD；已冊封 UNION 進 corpus（負 id、source_class=root）；ask 檢索得到、root 權重最高。

### 測試先行
- [x] T008 [P] [US2] `tests/unit/test_why_nodes_repo.py`：`add_why_node`→`list_why_nodes('candidate')`
  有它；`anoint_why_node`（改 claim）→ status='anointed'；`delete_why_node` → 消失且負 id 嵌入清掉。
- [x] T009 [P] [US3] `tests/unit/test_why_nodes_repo.py` 續：已冊封 why-node 進 `list_corpus_entries`
  （`entry_id<0`、`source_class='root'`、body=claim）；候選**不**進 corpus。
- [x] T010 [P] [US3] `tests/unit/test_rag_root_weight.py`：`_weight('root') > _weight('explainer') > 1.0`。
- [x] T011 [P] [US3] `tests/contract/test_root_cause.py`：**閉環**——`add_why_node`＋`anoint`（claim 含
  關鍵詞）→ `RagService.answer(問關鍵詞)` 檢索得到（sources 含其證據 url）。

### 實作
- [x] T012 [US2] `store/repository.py`：`add_why_node`／`list_why_nodes`／`anoint_why_node`／
  `delete_why_node`（清 `entry_embeddings WHERE entry_id=-id`）。
- [x] T013 [US3] `store/repository.py`：`list_corpus_entries` UNION `status='anointed'` → `CorpusEntry`
  （負 id、source_class='root'、url=證據0、body=claim）。
- [x] T014 [US3] `rag/service.py`：`_weight` 加 `root` 層（`rag_root_weight`）；`make_*` 傳入權重。

## Phase 5：US1/US2 串頁面＋US4 友善（P1/P2）

### 測試先行
- [x] T015 [P] [US1] `tests/contract/test_root_cause.py` 續：`/whynode/extract`（注入 stub extractor）→
  候選入庫、導 `/roots`、頁面顯示 claim＋試金石＋「AI 推斷」標示；`/library` 種子有「萃取根因」鈕。
- [x] T016 [P] [US2] `tests/contract/test_root_cause.py` 續：`/whynode/anoint` → status 轉 anointed；
  `/whynode/remove` → 消失；`/roots` 分「候選／已冊封」。
- [x] T017 [P] [US4] `tests/contract/test_root_cause.py` 續：萃取失敗（extractor 拋 `SourceUnavailable`）
  → `/whynode/extract` 友善繁中、非 500、不建候選；`no_material` → 不建候選、友善提示。

### 實作
- [x] T018 [US1] `web/app.py`：`app.state.extractor_factory`（預設 `make_root_cause_extractor`）；
  `POST /whynode/extract`（entry_id＝種子 → 取種子 title/body → extract → no_material/失敗友善、否則
  add_why_node → 導 /roots）。分層攔 `SourceUnavailable`。
- [x] T019 [US2] `web/app.py`：`POST /whynode/anoint`（id＋可選 claim）、`POST /whynode/remove`（id）；
  `GET /roots`（列候選＋已冊封）。
- [x] T020 [US1] `templates/roots.html`（候選卡：claim＋「AI 推斷（據 [來源]）」＋試金石逐條 badge＋
  霧詞旗標＋證據連結＋冊封（可編輯）/退回；已冊封清單）＋`library.html` 加「萃取根因」鈕＋
  `base.html` 導覽加「根因」。

## Phase 6：Polish

- [x] T021 [P] 更新 `docs/usage.md`：`/roots` 根因萃取（AI 提候選＋試金石、人冊封、餵回 ask）。
- [x] T022 全套 `uv run pytest` 綠、不回歸（≥219＋新測）；快速手測 /library→萃取→/roots→冊封→/ask。
- [ ] T023 真跑抽查（可選，留使用者）：設金鑰 → 對真種子萃取看根因＋試金石品質。

## 相依與 MVP

- **相依**：T002/T003 → T006 → T007；T012 → T013 → T014；T018→T019→T020。測試先於實作。
- **MVP**：Phase 3（萃取＋試金石可測）＋Phase 4（冊封＋餵回 ask 閉環）＝核心價值；Phase 5 串頁面。
- **並行**：unit（T004/5/8/9/10/11）、contract（T015/16/17）各 `[P]`（同檔內順序）。
- **範圍守恆**：**無自動冊封**、無一根因多載體、無成核、無自動三角測量、無 CLI。不動既有表。
