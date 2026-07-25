# Implementation Plan: 根因萃取（冊封根因＝吸引子本體）

**Branch**: `012-root-cause` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/012-root-cause/spec.md`　｜　**設計源**：`knowledge/concepts/有吸引子的場.md`

## Summary

新增 `why_nodes` 容器 + 可插拔 `RootCauseExtractor`（對種子抽候選根因＋試金石自我反駁）+ web
冊封動作（人 accept/退回）+ 已冊封 why-node 以**負 entry_id** 映成 `CorpusEntry(source_class="root")`
UNION 進 `list_corpus_entries` → `ask` 檢索得到、`RagService` 給 root 最高權重。閉環：進水→**冊封**
→**讀**。不動既有表（新表＋查詢層 UNION）。

## Technical Context

- **語言/執行**：Python 3.12＋、uv；web/jinja2 既有。核心零相依（urllib）。
- **復用**：`store/schema.py` `_migrate`（加表冪等）、`store/repository.py`（種子/語料/嵌入方法、
  `list_corpus_entries`、`ensure_embeddings`）、`rag/service.py` `_weight`／檢索、`rag/types.CorpusEntry`、
  `backends/openai_api._post`（chat 萃取）、`web/app.py` `/library` anoint 樣式（reclassify/remove）、
  `templates/library.html`、config 後端設定。
- **新增**：
  - `store/schema.py`：`why_nodes` 表（`CREATE TABLE IF NOT EXISTS`＋`_migrate` 冪等）。
  - `rootcause/extract.py`：`RootCauseExtractor`＋`StubExtractor`＋`OpenAIExtractor`（`_post`）；
    `Candidate` 型別（claim／touchstones／fog_flag／evidence／no_material）。
  - `backends/factory.py` `make_root_cause_extractor(config)`。
  - `repository`：`add_why_node`／`list_why_nodes`／`anoint_why_node`／`delete_why_node`；
    `list_corpus_entries` UNION 已冊封 why-node（負 entry_id）。
  - `rag/service.py` `_weight` 加 `root` 層（`rag_root_weight`，預設 2.0 > explainer 1.5）。
  - `config`：`rag_root_weight`。
  - web：`/whynode/extract`（對種子萃取）、`/whynode/anoint`、`/whynode/remove`；`/library` 或
    新 `/roots` 顯示候選（試金石結果）＋已冊封清單。
- **測試**：unit（extractor stub／解析／no_material；repository why_nodes CRUD；corpus UNION）＋
  contract（萃取→候選卡＋試金石、冊封→ask 檢索得到且 root 權重最高、退回、失敗友善）。全離線。

## Constitution Check

| 憲章／原則／concept | 檢查 | 結果 |
|---|---|---|
| 原則 5 權重由人冊封＋憲章 VI | 候選只是候選；人 accept 才轉正；工具不自動冊封 | 🟢 正中（本階段＝原則 5 實作） |
| concept 試金石／folie à deux 解藥 | 萃取 MUST 對自己 adversarial：逐條 pass/fail＋霧詞旗標 | 🟢 |
| 原則 3 溯源＋教訓 7 落結構 | 候選標「AI 推斷」＋證據 url；缺證據/試金石不給冊封（程式保證） | 🟢 |
| 教訓 8 免動已出貨表 | 新增 `why_nodes` 表＋查詢層 UNION；不改既有表結構 | 🟢 |
| 教訓 1 可插拔離線 stub | `RootCauseExtractor` stub、零外部呼叫可測 | 🟢 |
| 教訓 3 外部失敗攔截 | 萃取失敗/逾時 → 友善繁中、不噴堆疊 | 🟢 |
| 憲章 II 全繁中 · IV 零相依 | 面向使用者全繁中；萃取用既有 chat（urllib），不加 pip | 🟢 |

**Gate：通過**，無違憲、無 NEEDS CLARIFICATION。

## Phase 0：research（見 [research.md](./research.md)）
## Phase 1：design（見 [data-model.md](./data-model.md)／[contracts/](./contracts/)／[quickstart.md](./quickstart.md)）

## 進度
- [x] Phase 0：research.md
- [x] Phase 1：data-model.md、contracts/、quickstart.md
- [ ] Phase 2：tasks.md（`/speckit-tasks`）
