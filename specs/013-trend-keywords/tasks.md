# Tasks：趨勢讀數（首頁熱詞 chips）

**功能目錄**：`specs/013-trend-keywords/`　｜　**TDD 強制**　｜　基準測試：234（不回歸）
**設計源**：`draft/2026-07-24-趨勢熱詞發現.md`(B)、`concepts/有吸引子的場.md`（趨勢＝盆地通量）

依 spec 的 US 分期。`[P]`＝可並行（不同檔、無未完成相依）。

## Phase 1：Setup

- [x] T001 唯讀盤點復用點：`store/repository.py`（匯整讀取、`SEEDS_DATE` 排除樣式）、
  `web/app.py:138` `home` route、`templates/digest.html`、`/pull?topic=`（既有）。

## Phase 2：Foundational（阻擋所有 US）

- [x] T002 `config.py`：加 `trend_top_n`（8）、`trend_recent_digests`（3），`from_env` 讀
  `LEARNNEWS_TREND_TOPN`／`LEARNNEWS_TREND_RECENT`。

## Phase 3：US1 首頁看「在紅什麼」（P1，萃取核心）

> 獨立測試：`trend_keywords(titles)` 純函式——高頻排序、中英混合、停用詞/門檻過濾；零外部呼叫。

### 測試先行（TDD）
- [x] T003 [P] [US1] `tests/unit/test_trend_keywords.py`：高頻詞排前（重複出現）、`top_n` 裁切、
  同分保原序。
- [x] T004 [P] [US1] `tests/unit/test_trend_keywords.py` 續：中英混合（英文詞＋中文 bigram 都成熱詞）；
  停用詞（的/model/AI）與 `count<min_count` 被濾；全被濾 → `[]`。

### 實作
- [x] T005 [US1] 新增 `src/learnnews/trend/keywords.py`：`trend_keywords(titles, top_n=8,
  stopwords=None, min_count=2)`——英文詞（`[A-Za-z0-9][A-Za-z0-9+\-.]*`、len≥2、小寫）＋中文相鄰
  bigram；跨標題計數；過濾內建 `STOPWORDS`∪傳入；count≥min_count；降序取 top_n（stable）。內建
  `STOPWORDS`（英文常見＋中文常見＋領域泛詞）。

## Phase 4：US2 點擊深挖＋US3 優雅省略（P1/P2，串首頁）

> 獨立測試：首頁顯示 chips＋連 /pull?topic=；無匯整/算不出 → 不顯示區塊、非 500。

### 測試先行
- [x] T006 [P] [US1] `tests/unit/test_recent_titles.py`：`recent_digest_titles(k)` 只取真實匯整標題、
  排除種子容器（`SEEDS_DATE`）。
- [x] T007 [P] [US2] `tests/contract/test_trend.py`：種幾份匯整（標題含重複主題詞）→ `GET /` 頁面含
  熱詞 chips、chip 連 `/pull?topic=`（url 編碼）。
- [x] T008 [P] [US3] `tests/contract/test_trend.py` 續：無匯整（或算不出）→ `GET /` **不含**熱詞區塊、
  其餘正常、非 500。

### 實作
- [x] T009 [US2] `store/repository.py`：`recent_digest_titles(k=3)`（最近 K 份 `date != SEEDS_DATE`
  匯整的 `digest_entries.title`）。
- [x] T010 [US2] `web/app.py`：`home` route 取 `recent_digest_titles(config.trend_recent_digests)`
  → `trend_keywords(..., top_n=config.trend_top_n)` → context 加 `chips`。
- [x] T011 [US2] `templates/digest.html`：頂端加熱詞區塊——`chips` 非空才渲染（描述性標題「🔥 今日
  高頻」＋每個 chip `<a href="/pull?topic={{ c|urlencode }}">`）；空則不渲染（FR-005）。

## Phase 5：Polish

- [x] T012 [P] 更新 `docs/usage.md`：首頁熱詞 chips（趨勢讀數、統計法、點擊深挖、可溯源）。
- [x] T013 全套 `uv run pytest` 綠、不回歸（≥234＋新測）；快速手測首頁（有/無匯整）。

## 相依與 MVP

- **相依**：T002 → T005；T009 → T010 → T011。測試先於實作。
- **MVP**：Phase 3（`trend_keywords` 純函式可測）＝核心；Phase 4 串首頁即可交付。
- **並行**：unit（T003/T004/T006）、contract（T007/T008）各 `[P]`（同檔內順序）。
- **範圍守恆**：**無 LLM 萃取、無竄升排序、無成核、無全量池落庫、無 live web 熱詞、無 CLI**；
  不新增/不改資料表。
