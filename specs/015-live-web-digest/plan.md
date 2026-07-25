# Implementation Plan: live web 活水（開放網路進每日 digest）

**Branch**: `015-live-web-digest` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/015-live-web-digest/spec.md`

## Summary

新增 `WebSearchAdapter`（實作 `SourceAdapter.fetch`）——對一組固定查詢跑既有 `WebSearch` 後端、
把 `SearchResult` 映成 `Item`、依 url 去重。`build_adapters` 加 `config` 參數＋特例 `web_search`：
**只在有 config＋搜尋金鑰時建**（否則跳過＝FR-003）。加預設**停用**的 `web-ai-trends` 源。
digest／refresh 傳 config → web 活水生效；pull 不傳 config → 跳過（保持專注）。**零 schema、複用
整條 digest 管線。**

## Technical Context

- **語言/執行**：Python 3.12＋、uv。核心零相依（urllib）。
- **復用**：`sources/base.py` `SourceAdapter`＋`_finalize`、`cli/fetchers.py` `build_adapters`／
  `_ADAPTERS`／`DEFAULT_SOURCES`、`search/websearch.py` `WebSearch`／`make_web_search`（spec 009）、
  `models.Item`、整條 digest 管線（`DigestBuilder` 已 `except SourceUnavailable`→`missing`）、
  `sources` 表／`/sources`（spec 008）、`config.search_api_*`。
- **新增**：
  - `sources/websearch_adapter.py` `WebSearchAdapter(source_id, web_search, queries)`：`fetch(since)`
    → 每 query `search()`→ 映 `Item`→ 依 url 去重→ `_finalize`。搜尋失敗 → 拋 `SourceUnavailable`
    （digest 攔成 missing）。
  - `cli/fetchers.py`：`build_adapters(sources, config=None)`——`access_method=="web_search"` 且
    config＋金鑰齊 → 建 `WebSearchAdapter(s.id, make_web_search(config), _parse_queries(s.endpoint))`；
    否則跳過。DEFAULT 加 `web-ai-trends`（`enabled=False`、endpoint＝換行分隔查詢）。
  - digest／refresh 呼叫改 `build_adapters(sources, config)`；pull 維持 `build_adapters(sources)`。
- **測試**：unit（adapter 映射/去重/失敗；`build_adapters` 有無金鑰）＋integration（`run_digest`
  帶 `WebSearchAdapter(stub)`→ 匯整含 web 材料）＋源預設停用。全離線、零外部呼叫。

## Constitution Check

| 憲章／原則／concept | 檢查 | 結果 |
|---|---|---|
| 根公理 成本要極低 | 治痛點（追不到剛紅）；discovery | 🟢 正中 |
| concept 反濾泡/驚訝力 | 伸手到策展名冊之外 | 🟢 |
| 原則 5 主權＋成本閘 | opt-in 預設停用＋需金鑰；web 是流非種子（收進才留） | 🟢 |
| 原則 3 溯源 | web 材料帶原文網址 | 🟢 |
| 教訓 3 外部失敗攔截 | adapter 拋 `SourceUnavailable`→ digest 既有 `missing_sources` | 🟢 |
| 教訓 1 可插拔離線 stub | `StubWebSearch`→ adapter 離線可測 | 🟢 |
| 教訓 8 免動已出貨表 | web 源＝sources 表一列，零新 schema | 🟢 |
| 憲章 II 全繁中 · IV 零相依 | 全繁中；複用搜尋後端，不加 pip | 🟢 |

**Gate：通過**，無違憲、無 NEEDS CLARIFICATION。

## Phase 0：research（見 [research.md](./research.md)）
## Phase 1：design（見 [data-model.md](./data-model.md)／[contracts/](./contracts/)／[quickstart.md](./quickstart.md)）

## 進度
- [x] Phase 0：research.md
- [x] Phase 1：data-model.md、contracts/、quickstart.md
- [ ] Phase 2：tasks.md（`/speckit-tasks`）
