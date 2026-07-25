# Contract：匯整分區

## Schema
- `digest_entries.source_id TEXT DEFAULT ''`（SCHEMA＋`_migrate` ALTER，冪等）。

## Repository
- `save_digest(d)`：每則 INSERT 帶 `source_id=e.item.source_id`。
- `get_last_digest()`：回的 `DigestEntry.item.source_id` 已填（讀 source_id 欄）。

## 分類
- `_section_of(type)`：`type in {"paper","blog"}` → `"foundational"`；否則（含 None/未知）→ `"news"`。

## `GET /`（首頁擴充）
- 取 `get_last_digest` 條目＋`list_sources` id→type；逐則 `_section_of(type_by_id.get(source_id))`
  分 `news_entries`/`foundational_entries` 傳模板。
- `digest.html`：「📰 今日新聞」列 news、「📚 基礎知識精選」列 foundational；**各區空則不渲染**。
  熱詞 chips／重整鈕位置不變。

## DEFAULT_SOURCES
- `hn-ai`、`reddit-localllama` type `blog→news`（社群/新聞流）。

## 契約測試（離線、零外部呼叫）
1. `save_digest`＋`get_last_digest` → 條目 `item.source_id` round-trip（存得回得對）。
2. `_section_of`：paper/blog→foundational；news/None/未知→news。
3. 首頁：種一份匯整含 `source_id` 為 paper 源與 news 源的條目 → `GET /` 有「今日新聞」＋
   「基礎知識精選」兩區，各條目落對區。
4. 首頁：只有新聞源條目 → **不顯示**「基礎知識精選」區（空區不渲染）。
5. 首頁：舊條目（source_id=''）→ 落新聞區、頁面不崩。
6. `DEFAULT_SOURCES`：`hn-ai`、`reddit-localllama` type=`news`。
