# Implementation Plan: 趨勢讀數（首頁熱詞 chips）

**Branch**: `013-trend-keywords` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/013-trend-keywords/spec.md`　｜　**設計源**：`draft/2026-07-24-趨勢熱詞發現.md`(B)

## Summary

一個純函式 `trend_keywords(titles, ...)`（stdlib 統計：英文詞＋中文 bigram＋停用詞過濾＋門檻）
＋repo 讀最近 K 份真實匯整標題＋首頁 route 算 chips 傳模板＋`digest.html` 頂端 chips 區塊
（連 `/pull?topic=`）。**零外部呼叫、零相依、零 schema 變更**——用已落庫標題算。

## Technical Context

- **語言/執行**：Python 3.12＋、uv；web/jinja2 既有。核心零相依（純 stdlib `re`/`collections`）。
- **復用**：`digest_entries` 標題（`store/repository.py`）、首頁 `home`（`web/app.py:138`）、
  `/pull?topic=`（既有 pull）、`templates/digest.html`、web 工廠注入樣式。既有 `tokenize`
  （`ranking/embeddings.py:20`）把中文拆成**單字**、不合用 → 本功能自寫「英文詞＋中文 bigram」。
- **新增**：`trend/keywords.py`（`trend_keywords` 純函式＋內建停用詞）；`repository.recent_digest_titles(k)`；
  `config.trend_top_n`（8）；首頁 route 串接；`digest.html` chips 區塊。
- **測試**：unit（`trend_keywords`：高頻排序、中英混合、停用詞/門檻過濾、空輸入）＋contract
  （首頁顯示 chips＋連 `/pull?topic=`；無匯整/算不出 → 不顯示區塊）。全離線、零外部呼叫。

## Constitution Check

| 憲章／原則 | 檢查 | 結果 |
|---|---|---|
| 根公理 成本要極低 | 趨勢讀數＝discovery，使用者不必事先知道趨勢 | 🟢 正中 |
| 原則 3 溯源 | 熱詞點擊 → `/pull` 深挖真實材料，非憑空講趨勢 | 🟢 |
| 原則 4 可回溯＋中性 | 描述性措辭「今日高頻」、可點回；不預言 | 🟢 |
| 教訓 8 免動已出貨表 | 用已落庫標題算，不新增/不改表 | 🟢 |
| 教訓 1 可插拔離線 stub | 純統計 stdlib、零外部呼叫、離線可測 | 🟢 |
| 教訓「列準則≠品質」 | MVP 統計無 LLM 幻覺；LLM 萃取（防幻覺）留後續、不做 | 🟢 |
| 憲章 II 全繁中 · IV 零相依 | 面向使用者全繁中；純 stdlib，不加 pip | 🟢 |

**Gate：通過**，無違憲、無 NEEDS CLARIFICATION。

## Phase 0：research（見 [research.md](./research.md)）
## Phase 1：design（見 [data-model.md](./data-model.md)／[contracts/](./contracts/)／[quickstart.md](./quickstart.md)）

## 進度
- [x] Phase 0：research.md
- [x] Phase 1：data-model.md、contracts/、quickstart.md
- [ ] Phase 2：tasks.md（`/speckit-tasks`）
