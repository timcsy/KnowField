# Implementation Plan: web 搜尋（開放網路進水口）

**Branch**: `009-web-search` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-web-search/spec.md`

## Summary

加 web `GET /search?q=`（像 `/ask`）：query → 可插拔 `WebSearch` 後端回結果（標題/網址/摘要），
即算即棄（**不落庫**）；每則一個「收進」表單 **POST 既有 `/ingest`**（ref=網址）→ 走 `SeedService`
冊封成種子。新增 `search/websearch.py`（`SearchResult`／`WebSearch` 協定／`StubWebSearch` 離線／
真實 urllib 後端）＋config 搜尋欄位＋`make_web_search`。**收進零新碼（復用 spec 006）**、無新 schema、
無新 pip 相依（urllib）。

## Technical Context

**Language/Version**: Python 3.12+（uv）

**Primary Dependencies**: 既有 FastAPI/Jinja2（web）；stdlib urllib（搜尋 API）；**不新增第三方相依**

**Storage**: SQLite（既有）；**無 schema 變更**——搜尋結果不落庫；收進復用種子容器（spec 006）

**Testing**: pytest；契約測試用**可注入假 `WebSearch`＋假抓取**（離線、零外部呼叫）

**Target Platform**: 本機 web

**Project Type**: 單一專案（web＋核心函式庫）

**Performance Goals**: 一次搜尋＝一次外部呼叫；結果即算即棄

**Constraints**: 結果短暫、人冊封才留（FR-003、原則 5）；後端失敗友善繁中（FR-005、教訓 3）；
可插拔離線可測（教訓 1）；無新 pip 相依（憲章 IV）；全繁中（憲章 II）

**Scale/Scope**: 個人偶爾搜尋，每次數則～十數則結果

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。* 依 constitution v1.2.0：

- **I. TDD**：✅ 先寫失敗單元/契約測試再實作。
- **II. 繁體中文**：✅ 面向使用者文字繁中。
- **III. 規格驅動**：✅ 由 spec 009 展開，FR↔測試對映。
- **IV. YAGNI／最小相依**：✅ 搜尋 API 走 stdlib urllib（同 OpenAI 後端）**不加 pip 相依**；
  收進復用 spec 006 ingest；**無新 schema**；結果不落庫（不做搜尋歷史）。
- **V. 可觀測性／錯誤處理**：✅ 後端失敗/未設金鑰 → 頁內友善繁中、不噴堆疊。
- **VI. 決策主權**：✅ 搜尋結果短暫，只有使用者「收進」才成種子；工具不自動落庫（FR-003）。

**結論：無違規**，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)
```text
specs/009-web-search/
├── plan.md · research.md · data-model.md · quickstart.md
└── contracts/web-search.md
```

### Source Code (repository root)
```text
src/knowfield/
├── search/
│   ├── __init__.py
│   └── websearch.py          # SearchResult／WebSearch 協定／StubWebSearch／真實 urllib 後端
├── backends/factory.py       # +make_web_search（stub↔真實）
├── config.py                 # +search_api_url／search_api_key
├── web/
│   ├── app.py                # +GET /search（web_search_factory）；「收進」復用 POST /ingest
│   └── templates/
│       ├── search.html       # 查詢框＋結果清單（每則「收進」表單 → /ingest）＋空狀態/錯誤
│       └── base.html         # 導覽加「搜尋」
└── （seed/service.py、ingest 路由：複用，不改）

tests/
├── unit/test_websearch.py        # StubWebSearch、真實後端解析（假 http）、失敗
└── contract/test_web_search.py   # GET /search 列結果／查無／後端失敗友善；「收進」串接 ingest 成種子
```

**Structure Decision**：單一專案；搜尋是 `search/websearch.py` 薄後端＋一個 GET 頁；收進復用既有 ingest。

## Complexity Tracking
> 無違規，免填。
