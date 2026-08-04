# 技術方案：來源管理／原文檢視／清理／rich-paste（spec 031）

**規格**：[spec.md](./spec.md)｜**分支**：`031-source-management`

## 核心決策：零新表，「來源」＝同 url 塊的邏輯分組
一來源的塊本來就共用 `url`（spec 030）。管理/檢視用來源、檢索仍用塊。圖片以行內 `![](url)` 承載於塊文（hotlink）。守教訓 8（無新表）。

## 實作
- `ingest/chunk.py`：`stitch_chunks(chunks)` 純函式——依序拼回、去塊間重疊（詳情頁看原文）。
- `ingest/web.py`：`extract_article_markdown` 擴充——`<img>`→行內 `![alt](src)`（`//`補 https）。
- `ingest/clean.py`：`clean_markdown(text, backend)`——LLM 嚴格「只剝 UI、逐字保留正文」、失敗退回原文（US4 選用）。
- `ingest/service.py`：`ingest_text(text, title, html, clean)`——html 非空走 `extract_article_markdown`（rich-paste，含圖、剝 boilerplate）；clean=True 走 `clean_markdown`。加 `chat_backend`。
- `store/repository.py`：`list_source_groups`（GROUP BY url）／`get_source_chunks`／`source_title`／`delete_source(url)`／`set_source_class_by_url`。
- `web/app.py`：`/library`→列來源；`/source?u=`→拼回 render；`/library/remove`＋`/library/reclassify` 改按 url。
- 模板：`library.html`（歸一列、塊數 badge、檢視/刪除/重分類）、`source.html`（marked render＋圖 error fallback）、`ingest.html`（rich-paste 擷取 clipboard HTML＋🧹清理 toggle）。

## Constitution
- I TDD：stitch/img/clean 純函式＋repo 分組＋web 皆測；既有 library 契約測更新（entry_id→url）。
- IV 零相依：stitch/extract 純 stdlib；clean 走既有後端可注入 stub。**無新表**。
- II 全繁中。
