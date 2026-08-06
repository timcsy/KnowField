# Tasks：場對新材料做工（forward pass over your field）

**功能目錄**：`specs/018-field-relate/`　｜　**TDD 強制**　｜　基準測試：274（不回歸）
**設計源**：`concepts/有吸引子的場.md`（forward pass／拆開的 optimizer）

依 spec 的 US 分期。`[P]`＝可並行（不同檔、無未完成相依）。

## Phase 1：Setup

- [x] T001 唯讀盤點：`store/repository.py`（`list_seeds`／`_anointed_corpus_entries`／`ensure_embeddings`）、
  `ranking/embeddings`（`Embedder`/`cosine`）、`backends/openai_api._post`、`backends/factory`、
  `rag/service`（檢索/門檻樣式）、`config.rag_min_score`、`web/app.py`／`templates/library.html`。

## Phase 2：Foundational（吸引子對照集）

- [x] T002 `store/repository.py`：`list_field_attractors() -> list[CorpusEntry]`（種子＋已冊封根因）。
- [x] T003 [P] `tests/unit/test_field_attractors.py`：`list_field_attractors` 只含種子＋已冊封根因
  （不含每日流條目）；候選（未冊封）根因不在內。

## Phase 3：US1/US2/US3 判關係核心（P1，forward pass）

> 獨立測試：`FieldRelate.relate` 近→判關係、遠→成核、場空→提示、排除自己；RelationJudge stub/openai。

### 測試先行（TDD）
- [x] T004 [P] [US1] `tests/unit/test_relation_judge.py`：`StubRelationJudge.judge` 回確定性
  `{kind:extend,...}`；`OpenAIRelationJudge`（注入 poster 回 `{kind:contradict,reason}`）→ 解析對；
  poster 拋 → `SourceUnavailable`。
- [x] T005 [P] [US1] `tests/unit/test_field_relate.py`：注入 stub judge＋HashingEmbedder＋含一冊封根因
  的 repo，材料與該根因相近 → `kind` 來自 judge、`attractor` 為該根因、`relate` 不寫任何庫。
- [x] T006 [P] [US2] `tests/unit/test_field_relate.py` 續：材料與所有吸引子都遠（注入 embedder 令
  cosine 低）→ `kind="nucleate"`；材料空/太短 → `empty`。
- [x] T007 [P] [US3] `tests/unit/test_field_relate.py` 續：場空（無種子無根因）→ `kind="empty"`、
  **不呼叫 judge**；材料 url＝某種子 url → 該種子被排除、不選為 attractor。

### 實作
- [x] T008 [US1] 新增 `src/knowfield/field/relate.py`：`FieldRelation` 型別＋`RelationJudge` Protocol＋
  `StubRelationJudge`（確定性）＋`OpenAIRelationJudge`（`_post` chat、grounded system 明令延伸/牴觸/
  無關聯、牴觸明說、不杜撰、輸出 JSON、解析、失敗拋 `SourceUnavailable`）。
- [x] T009 [US1] `src/knowfield/field/relate.py` 續：`FieldRelate(embedder, judge, repo, min_score)`
  ＋`relate(title, body, exclude_url=None)`：吸引子空→empty；排除自己；ensure_embeddings＋cosine 找最近；
  `<min_score`→ nucleate（實質）/empty（太短）；否則 judge → FieldRelation。**不寫庫**。
- [x] T010 [US1] `backends/factory.py` 加 `make_relation_judge(config)`。

## Phase 4：US1/US4 web 觸發＋友善（P1/P2）

### 測試先行
- [x] T011 [P] [US1] `tests/contract/test_field_relate_web.py`：`/library` 種子有「關聯到我的場」；
  `POST /field/relate`（注入 `field_relate_factory` 回假 `FieldRelation`）→ 結果頁顯示關係＋理由；
  牴觸結果顯示「牴觸」。
- [x] T012 [P] [US4] `tests/contract/test_field_relate_web.py` 續：factory 拋 `SourceUnavailable` →
  友善繁中、非 500、無 Traceback；relate 後 `list_why_nodes`/`list_seeds` 不變（不改場）。

### 實作
- [x] T013 [US1] `web/app.py`：`app.state.field_relate_factory`（預設組 `FieldRelate(make_embedder,
  make_relation_judge, repo, config.rag_min_score)`）；`POST /field/relate`（entry_id＝種子 → 取
  title/body → relate（exclude_url=種子url）→ 結果頁）；分層攔 `SourceUnavailable`/例外 → 友善。
- [x] T014 [US1] `templates/field_relate.html`（結果頁：kind 徽章「延伸/牴觸/無明顯關聯/成核候選/
  場空」＋grounded 理由＋連到根因/種子）＋`library.html` 種子加「🧭 關聯到我的場」表單。

## Phase 5：Polish

- [x] T015 [P] 更新 `docs/usage.md`：場對新材料做工（延伸/牴觸/成核、grounded、場不自動改、護城河）。
- [x] T016 全套 `uv run pytest` 綠、不回歸（≥274＋新測）；快速手測（離線 stub）。
- [ ] T017 真跑抽查（可選，留使用者）：對一則種子關聯，看延伸/牴觸/成核判定品質。

## 相依與 MVP

- **相依**：T002 → T009；T008 → T009 → T010；T013 → T014。測試先於實作。
- **MVP**：Phase 2（吸引子集）＋Phase 3（FieldRelate 判關係）＝核心；Phase 4 串頁面。
- **並行**：unit（T003/4/5/6/7）、contract（T011/12）各 `[P]`（同檔內順序）。
- **範圍守恆**：**無自動標註每則、無批次成核、無自動改場、無多跳、無 CLI**；不新增資料表。
