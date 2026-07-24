# Implementation Plan: 來源訂閱（自助加／管理來源）

**Branch**: `008-source-subscribe` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-source-subscribe/spec.md`

## Summary

加 web `/sources` 頁（照 `/interests`/`/library` CRUD）：列出來源＋停用/啟用/刪除＋**加來源**
（貼 URL→RSS 探測→**實測有料才落庫**）。新模組 `sources/subscribe.py`（`discover_feed`／
`validate_feed`／`subscribe`，`http_get` 可注入）；repository 加 `delete_source`。**驗證複用
`RssAdapter`**、**加後 digest 自動抓（build_adapters 已吃 DB sources，零改管線）**。無新 schema。

## Technical Context

**Language/Version**: Python 3.12+（uv）

**Primary Dependencies**: 既有 FastAPI/Jinja2（web）；核心 stdlib（urllib、html.parser、xml）；**不新增相依**

**Storage**: SQLite（既有）；**無 schema 變更**——復用 `sources` 表

**Testing**: pytest；契約/單元測試用**可注入 `http_get`**（離線、零外部呼叫）

**Target Platform**: 本機 web

**Project Type**: 單一專案（web＋核心函式庫）

**Performance Goals**: 加來源＝一次探測＋一次驗證抓取；即時回應

**Constraints**: 加前實測有料才落庫（FR-003、教訓 7）；失敗不加壞來源＋友善繁中（FR-004、教訓 3）；
離線可測（教訓 1）；全繁中（憲章 II）；使用者冊封、工具不自動加（FR-008、原則 5）

**Scale/Scope**: 個人追蹤數個～數十來源

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。* 依 constitution v1.2.0：

- **I. TDD**：✅ 先寫失敗單元/契約測試再實作。
- **II. 繁體中文**：✅ 面向使用者文字繁中。
- **III. 規格驅動**：✅ 由 spec 008 展開，FR↔測試對映。
- **IV. YAGNI／最小相依**：✅ 復用 `RssAdapter`（驗證）、`sources` 表、`build_adapters`（抓取零改）、
  CRUD 樣式；探測用 stdlib `html.parser`；**無新 schema、無新相依**。範圍先 RSS，兜底後續。
- **V. 可觀測性／錯誤處理**：✅ 探測/驗證失敗→友善繁中、不加壞來源、不噴堆疊。
- **VI. 決策主權**：✅ 使用者自助冊封水源、可停用/刪除；工具不自動加（FR-008）。

**結論：無違規**，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/008-source-subscribe/
├── plan.md          # 本檔
├── research.md      # Phase 0
├── data-model.md    # Phase 1
├── quickstart.md    # Phase 1
├── contracts/
│   └── web-sources.md
└── tasks.md         # /speckit-tasks 產出
```

### Source Code (repository root)

```text
src/learnnews/
├── sources/
│   ├── subscribe.py          # 新增：discover_feed／validate_feed／subscribe（http_get 可注入）
│   └── rss.py                # 複用 RssAdapter（驗證有料），不改
├── store/repository.py       # +delete_source；upsert_source/set_source_enabled 現成
├── web/
│   ├── app.py                # +GET /sources、POST /sources/{add,toggle,remove}；app.state.subscribe_factory
│   └── templates/
│       ├── sources.html      # 新增：來源清單＋加來源框＋停用/啟用/刪除
│       └── base.html         # 導覽加「來源」
└── cli/fetchers.py           # build_adapters 已吃 DB sources，不改

tests/
├── unit/test_feed_discovery.py     # discover_feed／validate_feed／subscribe（假 http_get）
└── contract/test_web_sources.py    # /sources 列出/加/停用/刪除/去重/失敗不加壞
```

**Structure Decision**：單一專案；訂閱是 `sources/subscribe.py` 薄邏輯＋web 頁＋一個 repo 方法。

## Complexity Tracking

> 無違規，免填。
