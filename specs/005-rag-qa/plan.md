# Implementation Plan: RAG 問答（個人知識庫）增量 1 MVP

**Branch**: `005-rag-qa` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-rag-qa/spec.md`

## Summary

在既有 CLI 上加 `ask "問題" [--today]`：對**已落庫的匯整條目**（`digest_entries.article_body/
article_headline`）做可溯源 RAG。存匯整時**批次嵌入**條目、落庫於**新表 `entry_embeddings`**；
問答時只嵌問題、對語料 **cosine 暴力比對**取 top-k、交**新的 Answerer 後端**合成繁中答案並
**逐點掛來源**。複用既有 `Embedder`／`_post` chat／`Repository`／CLI 框架。核心新增：一張表、
一個 `RagService`、一個 `Answerer`（Stub＋OpenAI）、一個 `ask` 指令。守 TDD、離線可跑。

## Technical Context

**Language/Version**: Python 3.12+（uv 管理）

**Primary Dependencies**: 僅標準庫（urllib）＋既有可插拔後端；**不新增**第三方相依（無向量庫）

**Storage**: SQLite（既有）；新增 `entry_embeddings` 表存條目嵌入向量（JSON）

**Testing**: pytest；契約測試用**離線後端**（HashingEmbedder＋StubAnswerer），零外部呼叫

**Target Platform**: 本機 CLI（macOS/Linux）

**Project Type**: 單一專案（CLI＋核心函式庫）

**Performance Goals**: 問答互動級（不重跑消化、不重嵌語料）；一次問答對外部 API 呼叫次數
= O(1)（僅嵌問題＋一次合成），與語料規模無關（SC-004）

**Constraints**: 離線可完整測試（教訓 1）；後端失敗攔成友善繁中（教訓 3、FR-006）；
無來源不出貨（原則 3、FR-003/004）

**Scale/Scope**: 個人語料數百～數千條目；暴力 cosine 為毫秒級 → 不需向量庫（YAGNI）

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。* 依 `.specify/memory/constitution.md` v1.2.0：

- **I. TDD（不可妥協）**：✅ 先寫失敗契約/整合/單元測試，再實作；tasks 會把測試排在實作前。
- **II. 繁體中文**：✅ 答案與所有面向使用者文字繁中，跟隨 `--lang`。
- **III. 規格驅動**：✅ 由 spec 005 展開，FR↔測試對映。
- **IV. YAGNI／最小相依**：✅ 暴力 cosine、不上向量庫、不新增第三方相依；複用既有後端／
  存取／CLI。新增一張表與一個 Answerer 介面屬**必要**（語料需持久嵌入、Q+context 合成無既有
  介面可用）。惰性回填避免另立回填指令。
- **V. 可觀測性／錯誤處理**：✅ 後端失敗攔在 CLI 邊界、友善繁中、不噴堆疊（FR-006）。
- **VI. 使用者保有決策主權**：✅ 答案 grounded、逐點可回原文，使用者自行核對／覆寫；
  本增量無自動冊封吸引子（原則 5 的 optimizer 那層是後續增量）。

**結論：無違規**，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/005-rag-qa/
├── plan.md              # 本檔
├── research.md          # Phase 0：技術決策
├── data-model.md        # Phase 1：實體與 schema
├── quickstart.md        # Phase 1：驗證指引
├── contracts/
│   └── cli-ask.md       # Phase 1：ask 指令契約
└── tasks.md             # /speckit-tasks 產出（本指令不建）
```

### Source Code (repository root)

```text
src/knowfield/
├── rag/                     # 新增
│   ├── __init__.py
│   ├── types.py             # RagAnswer、Source、Scope
│   ├── answerer.py          # Answerer 協定＋StubAnswerer（離線、grounded）
│   └── service.py           # RagService：載語料→確保嵌入→檢索→合成
├── backends/
│   ├── openai_api.py        # +OpenAIAnswerer（複用 _post /chat/completions）
│   └── factory.py           # +make_answerer
├── ranking/embeddings.py    # 複用（embed_many／cosine），不改
├── store/
│   ├── schema.py            # +entry_embeddings 表
│   └── repository.py        # +list_corpus_entries／get/save_entry_embedding／ensure_embeddings
├── cli/
│   ├── __main__.py          # +ask subparser
│   └── ask_cmd.py           # 新增：組裝後端→RagService→列印答案＋來源；攔 OpenAIError
└── config.py                # +rag_top_k／rag_min_score 預設（可調）

tests/
├── contract/test_ask.py     # ask 指令契約（離線後端）
├── integration/test_rag_service.py  # 檢索→合成→溯源、範圍過濾、查無說無
└── unit/test_entry_embeddings.py    # 表存取、惰性回填、embedder tag 不符重嵌
```

**Structure Decision**：單一專案，沿用既有 `src/knowfield/<子模組>` 佈局；RAG 自成 `rag/`
薄層，呼叫既有核心，不改去重/排序/消化邏輯。

## Complexity Tracking

> 無違規，免填。
