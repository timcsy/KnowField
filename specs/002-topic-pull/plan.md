# Implementation Plan: 主題拉取深挖（拉模式）

**Branch**: `002-topic-pull` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-topic-pull/spec.md`

## Summary

實作 KnowField「拉」模式：給定主題 → 跨來源**擴展搜尋**（對可查詢來源用主題查詢、對
其他來源以相關性過濾近期材料）→ 去重 → 依主題相關性排序 → 收斂上限 →（預設）附一句
封頂定位、可 `--raw` 切純原礦 → 輸出可直達原文的材料清單。**大量複用階段 2 的地基**
（sources／dedup／ranking／summarize／backends／store），只新增一個 pull 服務、一個
主題查詢 URL 建構、一個 CLI 指令。TDD 全程先行。

## Technical Context

**Language/Version**: Python 3.12+（沿用）

**Primary Dependencies**（沿用，零新增）:
- 既有可插拔 `Embedder`（離線 stub／OpenAI 格式 API）做主題相關性
- 既有 `Summarizer`（stub／OpenAI 格式 API）做預設一句定位；`--raw` 時不呼叫
- 既有來源 adapter（arXiv／HF／RSS）、`dedup`、`RelevanceRanker`、`store`

**Storage**: SQLite（沿用；拉取結果可選擇性保存，MVP 先不落庫，直接輸出）

**Testing**: `unittest`（pytest 相容）；來源以錄製樣本、embedding／摘要以 stub，離線確定性

**Target Platform**: 沿用——CLI 批次工具

**Project Type**: 單一專案（沿用；新增 `pull/` 模組與 `cli/pull_cmd.py`）

**Performance Goals**: 互動式單次拉取，數秒內回應；結果 ≤ 30 則（SC-004）

**Constraints**: 每則直達原文（FR-005）；不生成結論（FR-006）；擴展需設上限防爆量（FR-007）；
不依賴 Semantic Scholar citation graph（429，history/005）

**Scale/Scope**: 單一使用者、單次主題拉取、跨現有 6 來源

## Constitution Check

*GATE: Phase 0 前通過，Phase 1 後再檢查。*

| 原則 | 本計畫如何遵守 | 狀態 |
|---|---|---|
| I. 測試優先（TDD） | pull 服務、主題查詢建構、CLI 皆先寫失敗測試；沿用離線 stub 確定性測試 | ✅ |
| II. 繁體中文 | 拉取輸出、狀態、錯誤全繁中（FR-009） | ✅ |
| III. 規格驅動 | 計畫每項可追溯回 spec FR | ✅ |
| IV. 簡潔與 YAGNI | 零新增相依、複用既有模組；拉取結果先不落庫 | ✅ |
| V. 可觀測性 | 拉取記錄 topic／結果數／缺漏來源；缺漏不靜默（FR-008） | ✅ |
| VI. 使用者決策主權 | 主題由使用者給；`--raw` 切換由使用者決定；沿用可 disable 來源 | ✅ |

**Gate 結果**：無違反，Complexity Tracking 留空。Phase 0 需釐清的取捨：各來源「擴展」的
具體查詢方式、與近期推匯整重疊的處理。

## Project Structure

### Documentation (this feature)

```text
specs/002-topic-pull/
├── plan.md · research.md · data-model.md · quickstart.md
└── contracts/
```

### Source Code (repository root) — 新增以粗體標示，其餘複用

```text
src/knowfield/
├── pull/                    # 【新增】拉模式
│   ├── service.py           #   PullService：擴展→去重→排序→(可選)摘要→組裝
│   └── topic_query.py       #   為可查詢來源建構主題查詢 URL（arXiv search）
├── cli/
│   └── pull_cmd.py          # 【新增】knowfield pull 指令
├── sources/ dedup/ ranking/ summarize/ backends/ store/ models/   # 複用
└── digest/                  # 複用（部分邏輯共用）

tests/
├── contract/test_cli_pull.py, test_topic_query.py     # 【新增】
├── integration/test_pull_*.py                          # 【新增】
└── unit/test_pull_service.py                           # 【新增】
```

**Structure Decision**：沿用單一專案。拉模式是薄薄一層新服務（`pull/`）＋薄 CLI，
建在階段 2 已測試的地基上；符合原則 IV（不重造）。

## Complexity Tracking

> 無憲章違反，本表留空。
