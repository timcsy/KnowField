# 072：收進來源的管理／原文檢視／清理／rich-paste 完成（spec 031）

> 日期：2026-08-04。承接 071（個人內容進料）。spec 031 出貨（323 測綠、零回歸）。
> 源＝真實使用照出 spec 030 進料的四個漏（使用者貼了一篇知乎文，被切 28 塊）。

## 真實使用照出的四個漏（experience：真實使用才驗收）
一篇長文收進後：①知識庫每塊佔一行、28 行「很難管理」；②「看不到原文」；③貼上夾一堆網站雜訊（導覽/評論/UI）；④想帶原文圖片。
——引擎（切塊→檢索）對，漏全在**下游的管理/可讀/保真**。又一次「引擎好 ≠ 收料好」，這次在「進料產物的呈現面」。

## 核心決策：零新表，「來源」＝同 url 塊的邏輯分組
一來源的塊本來就共用 `url`。**管理/檢視用來源、檢索仍用塊**（canonical 來源 vs derived 檢索索引，呼應 G2）。
守教訓 8——不新增表，靠既有 `url` 分組。圖片以**行內 `![](url)`** 承載於塊文（hotlink）＝#4 也不用存圖表。

## 關鍵決策
1. **rich-paste 一石多鳥**：前端擷取 `clipboardData` 的 `text/html` → 後端用既有 `extract_article_markdown`（本就剝 nav/script/footer）→ **同時**解決 #3 結構過濾＋#4 圖片（`<img>`→`![](url)`）。純文字貼上向後相容。
2. **詳情頁靠 `stitch_chunks` 去重疊拼回**：塊間 40 字重疊，拼回時找最長重疊前後綴去掉；全相同字元是退化不可解、真實內容無虞。
3. **LLM 清理選用、謹慎**：`clean_markdown` 嚴格「只剝 UI、逐字保留正文、不改寫」、預設不跑、失敗退回原文——「捕捉」工具防幻覺改寫（原則：保真優先）。
4. **管理改按 url**：`/library` 列來源、刪/標解說文整份套用；既有 library 契約測 entry_id→url 更新。

## 產物
- `ingest/chunk.py`（stitch_chunks）、`ingest/web.py`（<img> 擴充）、`ingest/clean.py`（新）、`ingest/service.py`（ingest_text html/clean）。
- `repository.py`：list_source_groups/get_source_chunks/source_title/delete_source/set_source_class_by_url（皆按 url、限種子容器）。
- `web/app.py`：/library 列來源、/source 詳情、remove/reclassify 按 url；`library.html`/`source.html`/`ingest.html`。
- 測試：test_source_mgmt.py＋stitch/img 測；311→323。真後端驗：真 DB 的 28 塊知乎文歸一列。
- 規格：`specs/031-source-management/`。

## 教訓（沿用）
- 真實使用才驗收（第 N 次）：單輪功能對＋測綠，不保證**產物呈現面**衛生（管理/可讀/保真）。
- 教訓 8 無新表：邏輯分組（url）＋行內圖片 URL 承載，避開新表。
- 原則 6/保真：清理走 LLM 也要「不改寫」，捕捉工具最忌幻覺改原文。

## 收束
進料層四張嘴 → 一 pipeline → 現在「一份來源」有了管理/檢視/清理/圖片。draft `2026-08-04-進料轉檔選型.md` 四張嘴＋此管理層皆落地；
剩 #4-進階（圖片下載存檔、瀏覽器擴充帶圖）與 ⑤真影音，未做、記 draft。
