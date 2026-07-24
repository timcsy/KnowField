# Implementation Plan: 種子 ingest（個人知識庫）增量 2a

**Branch**: `006-seed-ingest` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-seed-ingest/spec.md`

## Summary

加 CLI `ingest <arXiv-id|url> [--explainer]`：抓單篇 → `ArticleBuilder` 消化 → `ensure_embeddings`
嵌入 → 存為 KB **種子**。種子存進**「種子容器」digest**（哨兵 date），沿用 `digest_entries`→
`entry_id` 不變、`entry_embeddings` 免動；`digest_entries` 加 `source_class` 欄（解說文／一般），
`RagService` 檢索時**以來源類權重加成排序**（相關度門檻仍用原始 cosine 把關）。抓取器
`http_get` 可注入 → 離線可測。複用消化/嵌入/檢索/存取/CLI，不重寫核心。

## Technical Context

**Language/Version**: Python 3.12+（uv）

**Primary Dependencies**: 僅標準庫（urllib、xml、html.parser）＋既有可插拔後端；**不新增**第三方相依

**Storage**: SQLite（既有）；`digest_entries` 加 `source_class` 欄；種子存入哨兵「種子容器」digest

**Testing**: pytest；契約測試用**離線後端＋可注入假抓取器**（零外部呼叫）

**Target Platform**: 本機 CLI

**Project Type**: 單一專案（CLI＋核心函式庫）

**Performance Goals**: ingest 單篇＝一次抓取＋一次消化＋一次嵌入；`ask` 沿用增量 1（O(1) 呼叫）

**Constraints**: 離線可完整測試（教訓 1）；抓取/解析失敗攔友善繁中、**不寫半殘種子**（FR-006）；
種子必掛原文連結（原則 3）；使用者手動冊封、工具不認 canon（原則 5、FR-008）

**Scale/Scope**: 個人手挑種子數十～低百篇；沿用暴力 cosine（YAGNI）

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。* 依 constitution v1.2.0：

- **I. TDD**：✅ 先寫失敗契約/整合/單元測試再實作。
- **II. 繁體中文**：✅ 所有面向使用者文字＋消化繁中。
- **III. 規格驅動**：✅ 由 spec 006 展開，FR↔測試對映。
- **IV. YAGNI／最小相依**：✅ **種子容器 digest** 復用 `digest_entries`（免動 `entry_embeddings`
  的 entry_id）；URL 抽取用 stdlib `html.parser` 淺抽（深 readability 留後續）；不新增相依。
- **V. 可觀測性／錯誤處理**：✅ 抓取失敗拋 `SourceUnavailable`→CLI 攔友善繁中、不半殘入庫。
- **VI. 決策主權**：✅ 使用者手動 `ingest` 指定、工具不自動認 canon（FR-008）。

**結論：無違規**，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/006-seed-ingest/
├── plan.md          # 本檔
├── research.md      # Phase 0：技術決策
├── data-model.md    # Phase 1：實體與 schema
├── quickstart.md    # Phase 1：驗證指引
├── contracts/
│   └── cli-ingest.md
└── tasks.md         # /speckit-tasks 產出
```

### Source Code (repository root)

```text
src/learnnews/
├── seed/                     # 新增
│   ├── __init__.py
│   ├── fetch.py              # fetch_arxiv_by_id／fetch_url（http_get 可注入）→ Item
│   └── service.py            # SeedService.ingest(ref, explainer)：抓→消化→嵌入→存；去重
├── summarize/article.py      # 複用 ArticleBuilder.build（不改）
├── ranking/embeddings.py     # 複用 embed_many／cosine（不改）
├── rag/
│   ├── types.py              # CorpusEntry +source_class
│   └── service.py            # 檢索排序加來源類權重（門檻仍用原始 cosine）
├── store/
│   ├── schema.py             # digest_entries +source_class 欄
│   └── repository.py         # 種子容器 digest、ingest_seed、list_corpus_entries 帶 source_class＋--today 排除種子
├── cli/
│   ├── __main__.py           # +ingest subparser
│   └── ingest_cmd.py         # 組後端→SeedService→列印結果；攔 SourceUnavailable/OpenAIError
└── config.py                 # +rag_explainer_weight、SEEDS_DATE 哨兵

tests/
├── contract/test_ingest.py            # ingest 指令（離線假抓取器）：成功/去重/失敗友善
├── integration/test_seed_retrieval.py # 種子進 KB → ask 檢索得到＋溯源；解說文權重＞快訊
└── unit/test_seed_fetch.py            # arXiv/URL 解析、id 正規化、去重鍵
```

**Structure Decision**：單一專案；種子自成 `seed/` 薄層，呼叫既有消化/嵌入/存取，`ask` 零改
即受惠。

## Complexity Tracking

> 無違規，免填。
