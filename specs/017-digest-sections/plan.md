# Implementation Plan: 匯整分區（新聞流 vs 基礎知識）

**Branch**: `017-digest-sections` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/017-digest-sections/spec.md`

## Summary

`digest_entries` 加 `source_id` 欄（`_migrate` 冪等）→ `save_digest` 寫 `item.source_id`、
`get_last_digest` 讀回填 `Item.source_id`。首頁用 `sources` 表 `id→type` 映射把條目分兩區
（基礎＝type∈{paper,blog}、新聞＝其餘）。`digest.html` 兩區 section（空區不顯示）。HN/Reddit
重分類 blog→news。**只改呈現＋最小新增欄，不動匯整產生流程。**

## Technical Context

- **語言/執行**：Python 3.12＋、uv；web/jinja2 既有。
- **復用**：`store/schema.py` `_migrate`、`store/repository.py` `save_digest`/`get_last_digest`/
  `list_sources`、`web/app.py` `home`、`templates/digest.html`、`web/views.py` `entry_to_page`、
  `cli/fetchers.py` `DEFAULT_SOURCES`。匯整產生（`DigestBuilder`/`run_digest`）不變。
- **改動**：
  - `schema.py`：`digest_entries` 加 `source_id TEXT DEFAULT ''`（SCHEMA＋`_migrate` ALTER 冪等）。
  - `repository.save_digest`：INSERT 補 `source_id=e.item.source_id`。
  - `repository.get_last_digest`：SELECT `source_id`，回填 `Item.source_id`。
  - `web/app.py` `home`：建 `sources` id→type 映射，分 `news`/`foundational` 兩清單傳模板。
  - `templates/digest.html`：兩區 section（各空則不渲染）。
  - `cli/fetchers.py`：`hn-ai`、`reddit-localllama` type `blog→news`。
  - 分類 helper：`type∈{paper,blog}`＝基礎；其餘（含未知/web）＝新聞。
- **測試**：unit（save/get source_id round-trip；分類 helper）＋contract（首頁分兩區、空區不顯示、
  舊條目落預設區、HN/Reddit 在新聞區）。全離線。

## Constitution Check

| 憲章／原則／concept | 檢查 | 結果 |
|---|---|---|
| concept 流 vs 吸引子 | 分區把「新聞流 vs 基礎常青」在 UI 顯性化 | 🟢 正中 |
| 原則 3 溯源 | 兩區每則帶原文連結（不變） | 🟢 |
| 教訓 8 免動已出貨表 | 只**新增** `source_id` 欄（migrate 冪等）、不改既有欄；不動產生流程 | 🟢 |
| 向後相容 | 舊條目 source_id 空 → 落新聞區、不崩 | 🟢 |
| 憲章 II 全繁中 · IV 零相依 | 全繁中；零新相依 | 🟢 |

**Gate：通過**，無違憲、無 NEEDS CLARIFICATION。

## Phase 0：research（見 [research.md](./research.md)）
## Phase 1：design（見 [data-model.md](./data-model.md)／[contracts/](./contracts/)／[quickstart.md](./quickstart.md)）

## 進度
- [x] Phase 0：research.md
- [x] Phase 1：data-model.md、contracts/、quickstart.md
- [ ] Phase 2：tasks.md（`/speckit-tasks`）
