# Tasks：匯整分區（新聞流 vs 基礎知識）

**功能目錄**：`specs/017-digest-sections/`　｜　**TDD 強制**　｜　基準測試：268（不回歸）
**設計源**：`concepts/有吸引子的場.md`（流 vs 吸引子）

依 spec 的 US 分期。`[P]`＝可並行（不同檔、無未完成相依）。

## Phase 1：Setup

- [x] T001 唯讀盤點：`store/schema.py` `_migrate`、`store/repository.py` `save_digest`/`get_last_digest`/
  `list_sources`、`web/app.py` `home`、`web/views.py` `entry_to_page`、`templates/digest.html`、
  `cli/fetchers.py` `DEFAULT_SOURCES`。

## Phase 2：Foundational（條目帶來源 id）

- [x] T002 `store/schema.py`：`digest_entries` 加 `source_id TEXT DEFAULT ''`（SCHEMA＋`_migrate` ALTER 冪等）。

### 測試先行（TDD）
- [x] T003 [P] `tests/unit/test_digest_sections.py`：`save_digest`＋`get_last_digest` → 條目
  `item.source_id` round-trip（存得回得對）；`_section_of`：paper/blog→foundational、news/None/未知→news。

### 實作
- [x] T004 `store/repository.py`：`save_digest` INSERT 補 `source_id=e.item.source_id`；
  `get_last_digest` SELECT `source_id` → 回填 `Item.source_id`。
- [x] T005 分類 helper `_section_of(type)`（`web/app.py` 或小模組）：`type∈{paper,blog}`→foundational、否則 news。

## Phase 3：US1/US2/US3 首頁分兩區（P1，呈現）

### 測試先行
- [x] T006 [P] [US1] `tests/contract/test_sections.py`：種一份匯整含 paper 源與 news 源條目（帶 source_id）
  → `GET /` 有「今日新聞」＋「基礎知識精選」兩區、各條目落對區、皆可回原文。
- [x] T007 [P] [US3] `tests/contract/test_sections.py` 續：只有新聞源條目 → **不顯示**基礎區；
  舊條目（source_id=''）→ 落新聞區、頁面不崩（非 500）。
- [x] T008 [P] [US2] `tests/unit/test_digest_sections.py` 續：`DEFAULT_SOURCES` 的 `hn-ai`、
  `reddit-localllama` type=`news`（重分類）。

### 實作
- [x] T009 [US1] `web/app.py` `home`：取 `get_last_digest`＋`list_sources`（id→type）；逐 entry
  `_section_of` 分 `news_entries`/`foundational_entries`（各 `entry_to_page`）傳模板。
- [x] T010 [US1] `templates/digest.html`：兩區 section——「📰 今日新聞」列 news、「📚 基礎知識精選」
  列 foundational；各區空則不渲染。熱詞 chips／重整鈕不動。
- [x] T011 [US2] `cli/fetchers.py`：`hn-ai`、`reddit-localllama` type `blog→news`。

## Phase 4：Polish

- [x] T012 [P] 更新 `docs/usage.md`：首頁分區（今日新聞 vs 基礎知識精選、流 vs 吸引子）。
- [x] T013 全套 `uv run pytest` 綠、不回歸（≥268＋新測）；upsert 重分類的 HN/Reddit 進使用者 db；
  快速手測首頁分區（離線）。

## 相依與 MVP

- **相依**：T002 → T004 → T009 → T010；T005 → T009。測試（T003/6/7/8）先於實作。
- **MVP**：Phase 2（source_id 帶得到首頁）＋Phase 3（分兩區呈現）＝可交付。
- **並行**：unit（T003/T008）、contract（T006/T007）各 `[P]`。
- **範圍守恆**：**不改匯整產生流程/排序/衰減、不做基礎源→種子候選、不改 UI type、無 CLI 分區**；
  只新增 `source_id` 欄、不改既有欄。
