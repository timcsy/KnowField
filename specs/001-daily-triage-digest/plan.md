# Implementation Plan: 每日推播分診（推模式 MVP）

**Branch**: `001-daily-triage-digest` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-daily-triage-digest/spec.md`

## Summary

實作 LearnNews「推」模式的每日分診管線：從論文骨幹（arXiv、Hugging Face Daily
Papers、Semantic Scholar）加 1–2 個精選新聞來源取得條目，**跨來源去重**、依**興趣過濾**
排序、為每則產生**封頂摘要（一句定位＋一句為何值得看）**與**直達原文連結**，輸出一份
每日匯整。技術取徑：Python 批次管線，核心邏輯做成可測試的函式庫，外加一層薄 CLI；
狀態以 SQLite 保存；摘要以小型 LLM（Claude Haiku）生成並嚴格封頂。TDD 全程先行。

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**（最小化，YAGNI）:
- `httpx`（來源 API／HTTP 取得）、`feedparser`（RSS／Atom，含 email-ingestion 產生的 feed）
- 論文來源官方 API：arXiv API、Hugging Face `datasets`/HTTP、Semantic Scholar Academic Graph API
- 去重／興趣排序的語義相似度：本地輕量 embedding 模型（`sentence-transformers`，離線、可測試）
- 封頂摘要：Anthropic Claude（`claude-haiku-4-5`）經 Messages API（低成本、輸出短）
- CLI：`click` 或 `argparse`（傾向 stdlib `argparse`，除非需求增長）

**Storage**: SQLite（stdlib `sqlite3`）——保存來源、條目、事件群組、興趣畫像、每日匯整、
已見紀錄與行為訊號。無需外部資料庫（符合 YAGNI）。

**Testing**: `pytest`（TDD：先寫失敗測試 → 實作 → 重構）；`pytest` fixtures 以錄製的來源
樣本與離線 embedding 做確定性測試（避免測試打真實 API）。

**Target Platform**: Linux／macOS 本機或排程（cron）執行的 CLI 批次工具。

**Project Type**: 單一專案——核心函式庫（`src/`）＋薄 CLI；符合可測試性與 YAGNI。

**Performance Goals**: 批次、非即時。單日候選規模數十至低數百則；一次匯整產出目標
數分鐘內完成即可。匯整輸出 ≤ 15 則（SC-007）。

**Constraints**: 尊重各來源 robots／服務條款與用量上限（法遵假設）；LLM 呼叫成本受控
（僅對進入匯整的少數條目做封頂摘要，非全量）；摘要嚴格封頂兩句（SC-004）。

**Scale/Scope**: MVP 單一使用者、少數來源（論文骨幹＋1–2 新聞源）、每日一次批次。

## Constitution Check

*GATE: 需在 Phase 0 前通過，Phase 1 設計後再檢查一次。*

依 `.specify/memory/constitution.md`（v1.1.0）六原則：

| 原則 | 本計畫如何遵守 | 狀態 |
|---|---|---|
| I. 測試優先（TDD，不可妥協） | 所有功能程式碼先寫失敗測試；contract/integration/unit 三層；來源以錄製樣本、embedding 以離線模型做確定性測試 | ✅ |
| II. 繁體中文文件與溝通 | 所有規格/計畫/設計文件與面向使用者輸出（摘要、CLI 訊息、錯誤）皆繁中 | ✅ |
| III. 規格驅動開發 | 計畫每項可追溯回 spec FR；分歧先改 spec | ✅ |
| IV. 簡潔與 YAGNI | 單一專案、SQLite、最小相依；本地 embedding 避免外部服務；未引入佇列/微服務 | ✅ |
| V. 可觀測性與明確錯誤處理 | 結構化日誌；來源失敗不靜默（FR-011）；錯誤訊息繁中且可行動 | ✅ |
| VI. 使用者保有決策主權 | 興趣畫像可檢視/修改/覆寫，明講優先於學習推斷（FR-009） | ✅ |

**Gate 結果**：無違反，Complexity Tracking 留空。唯一需在 Phase 0 研究確認的取捨：
去重演算法、embedding 模型、摘要 LLM 呼叫策略、各來源取得方式（見 research.md）。

## Project Structure

### Documentation (this feature)

```text
specs/001-daily-triage-digest/
├── plan.md              # 本檔
├── research.md          # Phase 0 產出
├── data-model.md        # Phase 1 產出
├── quickstart.md        # Phase 1 產出
├── contracts/           # Phase 1 產出（CLI 指令契約、來源 adapter 介面）
└── tasks.md             # /speckit-tasks 產出（非本命令）
```

### Source Code (repository root)

```text
src/
└── learnnews/
    ├── sources/         # 各來源 adapter（arxiv, hf_papers, semantic_scholar, newsletter…）
    ├── models/          # 資料實體（Source, Item, EventCluster, InterestProfile, Digest, Summary）
    ├── dedup/           # 去重／事件叢集
    ├── ranking/         # 興趣過濾與相關性排序
    ├── summarize/       # 封頂摘要（LLM 呼叫＋長度守衛）
    ├── digest/          # 匯整組裝與輸出
    ├── store/           # SQLite 存取
    └── cli/             # 薄 CLI 入口

tests/
├── contract/           # CLI 指令契約、來源 adapter 介面契約
├── integration/        # 端到端：來源樣本 → 去重 → 排序 → 摘要 → 匯整
└── unit/               # 各模組單元測試
```

**Structure Decision**: 採單一專案。核心邏輯（sources/dedup/ranking/summarize/digest/
store）為可獨立測試的函式庫，`cli/` 僅為薄入口。符合憲章原則 I（可測試）與 IV（YAGNI），
也預留日後接 web 介面而不需重寫核心。

## Complexity Tracking

> 無憲章違反，本表留空。
