# Implementation Plan: 場對新材料做工（forward pass over your field）

**Branch**: `018-field-relate` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/018-field-relate/spec.md`　｜　**設計源**：`concepts/有吸引子的場.md`（forward pass）

## Summary

新 `field/relate.py`：`FieldRelate.relate(title, body)`——嵌入材料、對**你冊封的吸引子**（種子＋
已冊封根因）算 cosine 找最近；近則 `RelationJudge`（可插拔）grounded 判**延伸/牴觸/無關聯**、遠則
**成核候選**、場空則提示。web `POST /field/relate`（`/library` 種子按鈕）顯示關係＋連根因。
**復用整條檢索（ensure_embeddings/cosine）＋既有 chat；零新資料表；場不自動改（原則 5）。**

## Technical Context

- **語言/執行**：Python 3.12＋、uv；web/jinja2 既有。核心零相依（urllib）。
- **復用**：`store/repository.py`（`list_seeds`、`_anointed_corpus_entries`、`ensure_embeddings`）、
  `ranking/embeddings`（`Embedder`/`cosine`）、`backends/openai_api._post`（判關係）、
  `backends/factory`（`make_embedder`）、`config.rag_min_score`（近/遠門檻，教訓 4 尺度校準）、
  `/library`／`library.html`、web 工廠注入樣式。
- **新增**：
  - `repository.list_field_attractors()`：種子（`list_seeds`）＋已冊封根因（`_anointed_corpus_entries`）。
  - `field/relate.py`：`FieldRelation` 型別＋`FieldRelate`（注入 embedder／judge／repo）＋`RelationJudge`
    Protocol＋`StubRelationJudge`（離線確定性）＋`OpenAIRelationJudge`（`_post` chat、grounded 判關係）。
  - `backends/factory.make_relation_judge(config)`。
  - web：`POST /field/relate`（entry_id＝種子 → 取 title/body → relate → 結果頁）；`/library` 種子加
    「🧭 關聯到我的場」；小結果模板。
- **測試**：unit（FieldRelate：近→判關係、遠→成核、場空→提示、排除自己；RelationJudge stub/openai）＋
  contract（`/field/relate` 顯示關係/成核/場空、失敗友善、不改場）。全離線、零外部呼叫。

## Constitution Check

| 憲章／原則／concept | 檢查 | 結果 |
|---|---|---|
| concept forward pass／拆開的 optimizer | 材料在場裡跑前向傳遞；AI 算關係（梯度）、人決定 | 🟢 正中（護城河核心） |
| 原則 5 權重由人冊封＋憲章 VI | 只提關係、**場不自動改**（不退根因/不改冊封） | 🟢 |
| 原則 3 溯源＋教訓 7 grounding | 關係只依材料＋根因主張、可回溯、不杜撰；無關說無關 | 🟢 |
| 教訓 1 可插拔離線 stub | `RelationJudge` stub、零外部呼叫可測 | 🟢 |
| 教訓 3 外部失敗攔截 | 判關係失敗 → 友善繁中、不噴堆疊 | 🟢 |
| 教訓 4 尺度校準 | 近/遠門檻沿用 `rag_min_score`（依後端校準） | 🟢 |
| 教訓 8 免動已出貨表 | 用既有種子/根因/嵌入，零新表 | 🟢 |
| 憲章 II 全繁中 · IV 零相依 | 全繁中；判關係用既有 chat，不加 pip | 🟢 |

**Gate：通過**，無違憲、無 NEEDS CLARIFICATION。

## Phase 0：research（見 [research.md](./research.md)）
## Phase 1：design（見 [data-model.md](./data-model.md)／[contracts/](./contracts/)／[quickstart.md](./quickstart.md)）

## 進度
- [x] Phase 0：research.md
- [x] Phase 1：data-model.md、contracts/、quickstart.md
- [ ] Phase 2：tasks.md（`/speckit-tasks`）
