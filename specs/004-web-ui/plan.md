# Implementation Plan: Web 介面

**Branch**: `004-web-ui` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-web-ui/spec.md`

## Summary

一個薄薄一層的 **FastAPI ＋ Jinja2 ＋ Tailwind** web app，把既有核心（digest／pull／
interests／消化）用瀏覽器好讀地呈現：首頁看今日匯整（散文＋原文圖**內嵌**＋一鍵原文）、
輸入主題**即時拉**（含快取／節流）、管理興趣清單；RWD、全繁中、後端失敗攔成友善頁面。
**核心函式庫仍零相依**，框架相依只在 `web/` 這一層（Complexity Tracking 已提出理由）。
TDD（FastAPI TestClient）全程先行。

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**（**只在 web 層**；`web` extra）:
- **FastAPI**（路由、server-render HTML、例外處理器）＋ **uvicorn**（本機伺服器）
- **Jinja2**（模板）＋ **Tailwind**（RWD；MVP 用 **Play CDN**，零 build）
- 測試：FastAPI `TestClient`（需 `httpx`，dev/web extra）
- 核心（sources／dedup／ranking／summarize／pull／digest／interests／store）**全複用、零改動介面**

**Storage**: SQLite（複用）；首頁讀**最近一次落庫的匯整**（`digest_entries`：標題／原文連結／
散文／圖），需新增 `repository.get_last_digest()`（小幅擴充）。

**Testing**: `unittest` ＋ FastAPI `TestClient`；路由、快取、錯誤邊界皆離線可測（後端用 stub）。

**Target Platform**: 本機瀏覽器（`uvicorn` 起 server）；桌面＋手機 RWD。

**Project Type**: 單一專案＋新增 `web/` 層（FastAPI app＋templates）。

**Performance Goals**: 本機單人；即時拉以**記憶體 TTL 快取**避免重打後端（SC-004）。

**Constraints**: RWD（FR-007）；繁中（FR-008）；每則一鍵原文（FR-002）；AI 圖標示（FR-003）；
後端失敗不噴 500（FR-009）；不重寫核心（FR-010）。

**Scale/Scope**: 本機單一使用者；3 個頁面（匯整／拉取／興趣）。

## Constitution Check

*GATE: Phase 0 前通過，Phase 1 後再檢查。*

| 原則 | 遵守方式 | 狀態 |
|---|---|---|
| I. TDD | 路由以 TestClient 先寫失敗測試；快取／錯誤邊界／渲染皆測；後端 stub | ✅ |
| II. 繁中 | 模板、狀態、錯誤頁全繁中（FR-008） | ✅ |
| III. 規格驅動 | 每項可追溯 spec FR | ✅ |
| IV. 簡潔／YAGNI | 框架相依**只在 web 層**、核心零相依；server-render 無 SPA、Tailwind CDN 無 build；**額外相依已於 Complexity Tracking 提出理由** | ✅（見下表） |
| V. 可觀測 | FastAPI 例外處理器把後端失敗攔成友善繁中頁面、記錄日誌（FR-009） | ✅ |
| VI. 主權 | 興趣清單可在 web 檢視/增/刪（FR-006） | ✅ |
| 原則 3（溯源） | 每則一鍵原文；AI 圖標「示意」 | ✅ |
| 原則 4（消化＋溯源） | web 只換呈現，消化＋來源本質不變 | ✅ |

**Gate 結果**：唯一「額外複雜度」＝引入 web 框架相依，已在 Complexity Tracking 提出理由並限縮於 web 層；無其他違反。

## Project Structure

### Documentation (this feature)
```text
specs/004-web-ui/
├── plan.md · research.md · data-model.md · quickstart.md
└── contracts/
```

### Source Code — 新增粗體，其餘複用
```text
src/knowfield/
├── web/                     # 【新增】只有這層碰框架
│   ├── app.py               #   FastAPI app、路由、例外處理器
│   ├── views.py             #   把 Article/Digest/PullResult 轉成頁面用資料
│   ├── cache.py             #   即時拉的記憶體 TTL 快取／節流
│   └── templates/           #   Jinja2：base.html、digest.html、pull.html、interests.html（Tailwind CDN）
├── store/repository.py      # 微擴充：get_last_digest()（讀最近匯整全部 entries）
├── digest/ pull/ interests/ summarize/ media/ backends/ …   # 全複用、零改動

tests/
├── contract/test_web_routes.py      # 路由契約（TestClient）
├── integration/test_web_*.py        # 首頁/拉取/興趣/錯誤頁 端到端
└── unit/test_web_cache.py, test_web_views.py
```

**Structure Decision**：新增獨立 `web/` 層，是唯一 import 框架之處；核心一行不動、仍零相依。
符合原則 IV（複用、隔離複雜度）與「薄層」架構決策（plan 001）。

## Complexity Tracking

> 憲章原則 IV：額外複雜度須提出理由。

| 違反/複雜度 | 為何需要 | 較簡方案為何被拒 |
|---|---|---|
| 引入 web 框架相依（fastapi/uvicorn/jinja2/httpx） | 使用者明確要 **RWD／好用的 web UI**；手刻 stdlib http.server 做 RWD／模板／即時互動成本高、易錯 | stdlib `http.server`（零相依）——RWD 與模板要手刻，開發便利差、維護負擔高；使用者已選框架。相依**限縮於 `web/` 一層**，核心仍零相依，取捨見 `knowledge/draft/2026-07-23-部署與介面路線.md` |
