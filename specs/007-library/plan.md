# Implementation Plan: 知識庫管理（前端策展／修剪）

**Branch**: `007-library` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-library/spec.md`

## Summary

加 web `/library` 頁：列出／刪除／重分類**種子**（照既有 `/interests` 的 GET 列出＋POST 操作
模式）。三個新 repository 方法：`list_seeds`（只撈種子容器）、`delete_seed`（連 `entry_embeddings`
清、且**僅限種子容器內**）、`set_seed_class`。**每日流唯讀由 repo 方法結構保證**（WHERE
digest_id = 種子容器），不靠 UI。無新 schema、無新模組、無外部呼叫——純 DB CRUD，離線全可測。

## Technical Context

**Language/Version**: Python 3.12+（uv）

**Primary Dependencies**: 既有 FastAPI/Jinja2（web 層）；核心零相依；**不新增相依**

**Storage**: SQLite（既有）；**無 schema 變更**——操作既有 `digest_entries`（種子容器）＋`entry_embeddings`

**Testing**: pytest；契約測試離線（純 DB CRUD，零外部呼叫）

**Target Platform**: 本機 web

**Project Type**: 單一專案（web＋核心函式庫）

**Performance Goals**: 管理操作即時（個人 KB 數十～低百則）

**Constraints**: 只碰種子、每日流唯讀（FR-005，repo 層結構保證）；刪除連清嵌入無孤兒（FR-003、
教訓 8）；離線可測（教訓 1）；全繁中（憲章 II）

**Scale/Scope**: 個人種子數十～低百則

## Constitution Check

*GATE：Phase 0 前必過；Phase 1 後複查。* 依 constitution v1.2.0：

- **I. TDD**：✅ 先寫失敗契約/單元測試再實作。
- **II. 繁體中文**：✅ 所有面向使用者文字繁中。
- **III. 規格驅動**：✅ 由 spec 007 展開，FR↔測試對映。
- **IV. YAGNI／最小相依**：✅ 復用 `/interests` CRUD、`CorpusEntry`、種子容器；**無新 schema／
  模組／相依**；無回收桶（後續再議）。
- **V. 可觀測性／錯誤處理**：✅ 空狀態提示、刪除冪等、不噴未處理錯誤。
- **VI. 決策主權**：✅ 使用者可檢視/刪除/重分類自己冊封的（原則 5 的另一半）；每日流受保護。

**結論：無違規**，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/007-library/
├── plan.md          # 本檔
├── research.md      # Phase 0：技術決策
├── data-model.md    # Phase 1：實體與存取
├── quickstart.md    # Phase 1：驗證指引
├── contracts/
│   └── web-library.md
└── tasks.md         # /speckit-tasks 產出
```

### Source Code (repository root)

```text
src/knowfield/
├── store/repository.py       # +list_seeds／delete_seed／set_seed_class（皆僅限種子容器）
├── web/
│   ├── app.py                # +GET /library、POST /library/remove、POST /library/reclassify
│   └── templates/
│       ├── library.html      # 新增：種子清單＋刪除／重分類表單
│       └── base.html         # 導覽加「知識庫」
└── （無新模組）

tests/
├── unit/test_seed_management.py   # list_seeds 只列種子、delete_seed 連清嵌入＋拒每日流、set_seed_class
└── contract/test_web_library.py   # GET 列出/空狀態、POST remove、POST reclassify、每日流不現身
```

**Structure Decision**：單一專案；管理是 web 薄層＋三個 repo 方法，零新模組。

## Complexity Tracking

> 無違規，免填。
