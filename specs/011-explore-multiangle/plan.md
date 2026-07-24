# Implementation Plan: 探索（多角度擴展搜尋）

**Branch**: `011-explore-multiangle` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/011-explore-multiangle/spec.md`

## Summary

在 SmartSearch（spec 010）前加一層 **fan-out**：opt-in 開啟時，`QueryExpander` 把 query 拆成
3–5 子角度 → 各搜一次（既有 `WebSearch`）→ 依 url 合併去重 → 把合併池餵進**既有整理管線**
（排序＋抓 top-N＋grounded 整理）。只做 (a) 多角度、單輪有界。**opt-in 預設關**＋子角度上限
＋抓取沿用 top-N＝成本雙閘（根公理）。新面極小：一個可插拔 `QueryExpander`＋SmartSearch 加
`explore` 參數＋`/search` 一個開關。

## Technical Context

- **語言/執行**：Python 3.12＋、uv；web 這層既有。核心零相依（urllib）。
- **復用**：
  - `search/smart.py` `SmartSearch`（排序/抓取/整理/`[n]` 全複用，spec 010）。
  - `search/websearch.py` `WebSearch`／`make_web_search`（spec 009）。
  - `backends/openai_api.py:36` `_post(base_url,"/chat/completions",key,payload)`——拆解 query 複用。
  - `backends/factory.py`、`config.py`、`web/app.py:/search`、`templates/search.html`。
- **新增**：
  - `search/expand.py`：`QueryExpander` Protocol＋`StubQueryExpander`（離線確定性）＋
    `OpenAIQueryExpander`（`_post` 拆解、解析、上限、失敗退回）。
  - `backends/factory.py` `make_query_expander(config)`。
  - `config.explore_max_subqueries`（預設 5）。
  - `SmartSearch` 加 `expander` 注入＋`run(query, explore=False)`；explore 時 fan-out＋合併去重。
  - `/search` 加 `explore` 開關（checkbox）＋路由把 explore 傳進 `smart_search_factory`。
- **測試**：unit（expander stub／解析／上限／失敗退回；SmartSearch explore fan-out＋去重）＋
  contract（`/search` 有開關、勾選走多角度、去重、失敗退回單 query、預設關＝增量 b）。全離線。

## Constitution Check

| 憲章／原則 | 檢查 | 結果 |
|---|---|---|
| 根公理 成本要極低 · 憲章 IV YAGNI | opt-in 預設關＋子角度≤5＋抓取沿用 top-N；單輪有界 | 🟢 正中 |
| 教訓 1 可插拔離線 stub | `QueryExpander` 離線確定性 stub、零外部呼叫可測 | 🟢 |
| 教訓 3 外部失敗攔截 | 拆解失敗／逾時 → 退回單 query、友善繁中 | 🟢 |
| 原則 3/4/5 | 整理沿用 grounded／可回溯／不落庫／人挑（複用 spec 010） | 🟢 |
| 教訓 8 免動已出貨表 | 不新增 schema、不改 answerer 對外行為 | 🟢 |
| 憲章 II 全繁中 · IV 零相依 | 面向使用者全繁中；拆解用既有 chat（urllib），不加 pip | 🟢 |

**Gate：通過**，無違憲、無 NEEDS CLARIFICATION。

## Phase 0：research（見 [research.md](./research.md)）
## Phase 1：design（見 [data-model.md](./data-model.md)／[contracts/](./contracts/)／[quickstart.md](./quickstart.md)）

## 進度
- [x] Phase 0：research.md
- [x] Phase 1：data-model.md、contracts/、quickstart.md
- [ ] Phase 2：tasks.md（`/speckit-tasks`）
