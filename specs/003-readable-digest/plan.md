# Implementation Plan: 可讀文章式消化（升級摘要）

**Branch**: `003-readable-digest` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-readable-digest/spec.md`

## Summary

把每則材料的消化從「一句定位」兩欄摘要，升級為**可讀散文文章（Article）＋可選配圖**。
新增一個可插拔的 `ArticleBuilder`（散文生成，忠實約束＋長度指引），取代預設路徑的
`SummaryBuilder`；新增 best-effort 抓圖層（原文圖優先，取不到退純文字或可選 AI 示意圖）。
推（digest）與拉（pull）都改用 Article。`--raw` 純原礦不變。**零新增相依**（散文與 AI 圖
皆走既有 OpenAI 格式 API／urllib；抓圖用 stdlib 解析）。後端失敗優雅降級。TDD 全程先行。

## Technical Context

**Language/Version**: Python 3.12+（沿用）

**Primary Dependencies**（零新增）:
- 既有可插拔生成後端（OpenAI 格式 chat）做散文；同一 API 的 images 端點做 AI 示意圖（urllib）
- stdlib `html.parser`／正規化解析抓原文圖（新聞 RSS enclosure/img、arXiv HTML figure）
- 既有 sources／dedup／ranking／store／digest／pull／cli

**Storage**: SQLite（沿用）；digest_entries 增存文章正文/圖資訊（供 `--from-digest` 與回顧）

**Testing**: `unittest`（pytest 相容）；散文與 AI 圖後端以 stub、抓圖以錄製 HTML 樣本，離線確定性

**Target Platform**: 沿用——CLI 批次工具（markdown 文章輸出可內嵌圖）

**Project Type**: 單一專案（新增 `summarize/article.py`、`media/`（抓圖/AI圖），改 digest/pull/render）

**Performance Goals**: 消化只對進榜材料（推 top-N、拉結果）；每則一次散文呼叫（＋可選抓圖/AI圖）

**Constraints**: 忠實不捏造（FR-002）；不下工具結論（FR-003）；每則一鍵原文（FR-004）；
AI 圖須標示（FR-007）；後端/抓圖失敗優雅降級（FR-011）

**Scale/Scope**: 單一使用者；推每日 ≤15 則、拉 ≤30 則的散文消化

## Constitution Check

*GATE: Phase 0 前通過，Phase 1 後再檢查。*

| 原則 | 遵守方式 | 狀態 |
|---|---|---|
| I. TDD | article builder／抓圖／render／降級 皆先寫失敗測試；stub＋錄製樣本確定性 | ✅ |
| II. 繁中 | 散文、標示、錯誤全繁中（FR-010） | ✅ |
| III. 規格驅動 | 每項可追溯 spec FR | ✅ |
| IV. 簡潔／YAGNI | 零新增相依、複用；抓圖 best-effort、AI 圖為可選旗標 | ✅ |
| V. 可觀測 | 生成/抓圖失敗優雅降級、繁中訊息、不炸 traceback（FR-011） | ✅ |
| VI. 主權 | `--raw` 保留；AI 圖開關由使用者決定 | ✅ |
| **原則 4（消化＋溯源）** | 本功能即其落地：完整消化＋每則一鍵原文 | ✅ |
| **原則 3（溯源）** | FR-004 一鍵原文；FR-007 AI 圖明確標示不混淆 | ✅ |

**Gate 結果**：無違反，Complexity Tracking 留空。Phase 0 需研究：散文提示（忠實/不下結論）、
抓圖策略、AI 圖端點、Article 取代 Summary 的資料遷移、優雅降級。

## Project Structure

### Documentation (this feature)
```text
specs/003-readable-digest/
├── plan.md · research.md · data-model.md · quickstart.md
└── contracts/
```

### Source Code — 新增粗體，其餘複用
```text
src/knowfield/
├── summarize/
│   ├── article.py        # 【新增】Article dataclass ＋ ArticleBuilder（散文，忠實守衛）
│   ├── llm.py            # 擴充：散文生成 prompt（OpenAI 格式）＋ stub
│   └── summarizer.py     # 保留（--raw 相關/舊路徑；預設改走 article）
├── media/                # 【新增】配圖
│   ├── figure_extract.py #   從原文抓圖（RSS enclosure/img、arXiv HTML；best-effort）
│   └── ai_image.py       #   可選 AI 示意圖（OpenAI 格式 images；必標示）
├── cli/{digest_cmd,pull_cmd,render,pull_render}.py   # 改：輸出 Article＋圖、降級
├── digest/builder.py · pull/service.py               # 改：產 Article 取代 Summary
├── models/ · store/ · sources/ · dedup/ · ranking/ · backends/   # 複用/微調

tests/
├── contract/test_cli_article.py, test_figure_extract.py
├── integration/test_article_*.py
└── unit/test_article_builder.py, test_ai_image_label.py
```

**Structure Decision**：沿用單一專案。散文消化是替換「摘要」這一層＋新增抓圖層，建在
階段 1–3 已測地基上；Article 取代 Summary 為預設產物，`--raw` 路徑不變。符合原則 IV。

## Complexity Tracking
> 無憲章違反，本表留空。
