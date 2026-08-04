# 任務清單：來源管理／原文檢視／清理／rich-paste（spec 031）

TDD、零新表。US1 管理最痛先做。

## Phase 1：來源分組（管理＋檢視地基）
- [X] T001 [P] `test_chunk.py` stitch_chunks 紅測（去重疊拼回）。
- [X] T002 `ingest/chunk.py` stitch_chunks。
- [X] T003 `repository.py` list_source_groups/get_source_chunks/source_title/delete_source/set_source_class_by_url。
- [X] T004 [P] `test_source_mgmt.py` 分組/刪/重分類/詳情拼回紅測。

## Phase 2：US1 管理＋US2 詳情
- [X] T005 `app.py` /library 列來源、/source 詳情、remove/reclassify 改 url；`library.html`/`source.html`。更新既有 library 契約測（entry_id→url）。

## Phase 3：US3 rich-paste（圖片＋剝雜訊）
- [X] T006 [P] `test_web_extract.py` img→markdown 紅測；`ingest/web.py` <img> 擴充。
- [X] T007 `ingest/service.py` ingest_text(html=)；`ingest.html` 擷取 clipboard HTML。`test_source_mgmt.py` rich-paste 紅測。

## Phase 4：US4 LLM 清理（選用）
- [X] T008 `ingest/clean.py` clean_markdown（謹慎 prompt、失敗退回）；service ingest_text(clean=)；ingest.html 🧹 toggle。`test_source_mgmt.py::TestClean`。

## Phase 5：回歸
- [X] T009 全套綠（311→323）；真後端驗：真 DB 的 28 塊知乎文歸一列。
