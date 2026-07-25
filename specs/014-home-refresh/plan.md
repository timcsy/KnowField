# Implementation Plan: 首頁重新整理（從 web 重跑分診）

**Branch**: `014-home-refresh` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/014-home-refresh/spec.md`

## Summary

首頁加「🔄 重新整理」表單（POST `/digest/refresh`）→ 用啟用中的來源**複用既有 `run_digest`
＋`build_backend_builder`** 重跑分診（當前 UTC 日、`config.digest_limit`）→ `save_digest` 存新匯整
→ 導回 `/`（303）顯示最新（熱詞一併重算）。同步、可注入（離線可測）、失敗友善（不 500）。
**零 schema 變更、複用整條 digest 管線**。

## Technical Context

- **語言/執行**：Python 3.12＋、uv；web/jinja2 既有。
- **復用**：`cli/digest_cmd.py` `run_digest`／`build_backend_builder`；`cli/fetchers.py` `build_adapters`／
  `DEFAULT_SOURCES`；`repo.save_digest`／`list_sources`／`upsert_source`；首頁 `home`（`web/app.py:139`）、
  `digest.html`；全域 `OpenAIError` 攔截器（`web/app.py:131`，後端失敗→友善頁）；階段 11 熱詞（首頁已算）。
- **新增**：`app.state.digest_refresh_factory`（預設實作＋可注入）；`POST /digest/refresh` 路由；
  `home` 讀 `msg` 顯示重整失敗提示；`digest.html` 頂端「重新整理」表單＋成本提示。
- **測試**：contract（注入 stub factory：重整→存新匯整→首頁顯示最新；factory 拋 → 友善、非 500、
  舊匯整不受影響；鈕與成本提示存在；不自動重跑）。全離線、零外部呼叫。

## Constitution Check

| 憲章／原則 | 檢查 | 結果 |
|---|---|---|
| 根公理 成本要極低 | 一鍵重整＝免 CLI 拿最新 | 🟢 |
| 原則 5／主權 | 使用者明確觸發（POST 鈕）、不自動、不刪舊匯整 | 🟢 |
| 憲章 V 可觀測性 | 缺漏來源沿用 `missing_sources` 標示 | 🟢 |
| 教訓 3 外部失敗攔截 | 重整失敗 → 友善繁中、非 500（route＋全域 OpenAIError 攔截） | 🟢 |
| 教訓 1 可插拔離線 stub | `digest_refresh_factory` 可注入、契約測試零外部呼叫 | 🟢 |
| 教訓 8 免動已出貨表 | 用既有 `save_digest`（append），不新增/不改表 | 🟢 |
| 憲章 II 全繁中 · IV 零相依 | 面向使用者全繁中；複用既有管線，不加 pip | 🟢 |

**Gate：通過**，無違憲、無 NEEDS CLARIFICATION。

## Phase 0：research（見 [research.md](./research.md)）
## Phase 1：design（見 [contracts/](./contracts/)／[quickstart.md](./quickstart.md)；無新資料模型）

## 進度
- [x] Phase 0：research.md
- [x] Phase 1：contracts/、quickstart.md（data-model：無新實體，見 research R1）
- [ ] Phase 2：tasks.md（`/speckit-tasks`）
