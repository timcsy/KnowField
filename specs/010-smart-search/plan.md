# Implementation Plan: 智慧搜尋（搜尋結果的消化＋溯源整理）

**Branch**: `010-smart-search` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-smart-search/spec.md`

## Summary

在階段 9 的 `/search` 上疊一層「消化＋溯源＋排序」＝**RAG over 搜尋結果**。復用密度極高：
搜尋（spec 009 `WebSearch`）→ 排序（`Embedder`＋cosine）→ 抓 top-N 內文（spec 006 `fetch_url`）→
包成 `CorpusEntry` passages → 既有 `Answerer`（grounded＋`_is_no_material`）合成繁中「整理」→
`/search` 頁頂端渲染整理（`[n]` 溯源，複用 ask 頁那套）。**不新增相依、不新增資料表、不改
answerer 介面。**

## Technical Context

- **語言/執行**：Python 3.12＋、uv；web 這層 fastapi/jinja2（既有）。核心零相依（urllib）。
- **主要復用**：
  - `search/websearch.py`：`WebSearch`／`make_web_search`（spec 009）。
  - `seed/fetch.py:92` `fetch_url(url, http_get)->Item`（spec 006）——抓內文。
  - `rag/answerer.py` `Answerer.answer(question, passages, lang)`＋`StubAnswerer`／`OpenAIAnswerer`；
    `rag/service.py:14` `_is_no_material(text)`——grounded「無材料」判定（spec 005）。
  - `rag/types.py` `CorpusEntry`／`Source`——passages 與 `[n]` 來源型別。
  - `backends/factory.py` `make_embedder`／`make_answerer`／`make_web_search`；`Embedder`＋cosine。
  - `web/app.py:281` `/search` 路由、`templates/search.html`、`ask.html` 的 `[n]` 渲染 JS。
- **新增**：`search/smart.py`（智慧搜尋服務）、`make_smart_search` factory、`/search` 路由擴充、
  `search.html` 頂端整理段。
- **測試**：unit（smart 服務：排序、passages 轉接、grounded 降級）＋contract（`/search` 顯示
  整理＋`[n]`、抓不到降級、整體失敗仍列結果）。全離線 stub、零外部呼叫。

## Constitution Check

| 憲章／原則 | 檢查 | 結果 |
|---|---|---|
| 原則 4 消化到底、可回溯 | 整理是消化主線，逐點 `[n]` 可回溯 | 🟢 正中 |
| 原則 3 溯源 | `[n]` 掛真實結果、可點回原文 | 🟢 |
| 原則 5 人冊封＋憲章 VI | 整理是閱讀輔助、不落庫；只有「收進」才成種子 | 🟢 |
| 教訓 7 grounding 做進結構 | 復用 `Answerer` grounded＋`_is_no_material`，非提示自律 | 🟢 |
| 教訓 3 外部失敗攔截 | 單則抓不到降級 snippet；整體失敗友善繁中、仍列結果 | 🟢 |
| 教訓 1 可插拔離線 stub | Stub 全鏈（搜尋/嵌入/answerer）零外部呼叫可測 | 🟢 |
| 教訓 8 免動已出貨表 | 不新增 schema（收進沿用種子容器） | 🟢 |
| 憲章 II 全繁中 · IV 零相依/YAGNI | 面向使用者全繁中；抓取用既有 `fetch_url`，不加 pip | 🟢 |

**Gate：通過**，無違憲、無 NEEDS CLARIFICATION。

## Phase 0：research（見 [research.md](./research.md)）

決策點：整理放哪層、排序在抓取前或後、passages 轉接、降級策略、整體失敗與搜尋失敗的分層攔截、
`[n]` ↔ 結果卡對應、top-N 值。

## Phase 1：design（見 [data-model.md](./data-model.md)／[contracts/](./contracts/)／[quickstart.md](./quickstart.md)）

- `search/smart.py`：`SmartResult` 型別＋`SmartSearch` 服務（注入 web_search／fetch／embedder／
  answerer），`run(query)->SmartResult`。
- `make_smart_search(config)`：組真實或離線後端。
- `/search` 路由：呼叫 `app.state.smart_search_factory(q)`；搜尋失敗與整理失敗**分層攔截**。
- `search.html`：頂端整理段（marked＋MathJax＋`[n]`→`#res-n`），結果卡加 `id="res-n"`。

## 進度

- [x] Phase 0：research.md
- [x] Phase 1：data-model.md、contracts/、quickstart.md
- [ ] Phase 2：tasks.md（`/speckit-tasks`）
