# 任務清單：個人內容進料——貼上＋PDF（spec 030）

**規格**：[spec.md](./spec.md)｜**方案**：[plan.md](./plan.md)｜**分支**：`030-content-ingest`

TDD 強制：先紅後綠。**核心零新相依、無新表**（切塊純函式、轉檔藏介面後、收進落既有 digest_entries）。最硬＝切塊（原子塊不切）。US1 貼上＝最薄 MVP。

---

## Phase 1：Foundational（切塊純函式，阻塞全部）

- [X] T001 [P] `tests/unit/test_chunk.py` 寫 `chunk_markdown` 紅測：長文→多塊；fenced code```/`$$`數學/markdown 表格**不被切半**（各自完整落在單一塊）；有 `#` 標題→在標題處起新塊；短文→一塊；中文長串（無空格）也切得動、按字元數。
- [X] T002 `src/knowfield/ingest/__init__.py`＋`chunk.py`：實作 `chunk_markdown(md, target=400, overlap=40)`——原子塊偵測（```/`$$`/表格連續 `|`）保完整、`^#{1,6} ` 章節優先切點、章節內 prose 按字元切＋重疊、空→[]。跑 T001 轉綠。

**檢查點**：切塊純函式離線可測、原子塊守得住。

---

## Phase 2：US1（P1）——貼上收進、可被聊天引用（最薄 MVP）

- [X] T003 [P] [US1] `tests/unit/test_content_ingest.py` 寫紅測：`ContentIngestService.ingest_text("很長的文字…")`（注入 stub embedder）→ 回 `count>1`、`digest_entries` 多筆、`retrieve_corpus` 查得到；空字串→`status="empty"`、不新增。
- [X] T004 [US1] `src/knowfield/ingest/service.py`：`store_chunks(repo, embedder, title, url, chunks, source_class="ordinary")`（逐塊 `ingest_seed`＋批次 `ensure_embeddings`，回塊數）＋`ContentIngestService.ingest_text(text, title="")`（chunk→store，空→empty）。跑 T003 轉綠。
- [X] T005 [P] [US1] `tests/unit/test_ingest_web.py` 寫紅測：`POST /ingest/paste`（含「貓要吃貓砂」）→ 302/200 收進；再 `POST /chat`（注入 stub chat 回 `[1]`、`corpus_search_for_test` 用真 `retrieve_corpus`）→ 引用、標「你收藏的」。空貼上→友善不新增。
- [X] T006 [US1] `app.py`：`POST /ingest/paste`（`text`,`title`）→ `ContentIngestService.ingest_text`（用 `make_embedder`）；失敗攔 `(SourceUnavailable, OpenAIError)`→頁內友善。`ingest.html`：加「貼上文字/markdown」textarea 表單、結果顯示收了幾塊。跑 T005 轉綠。

**檢查點**：貼一段→聊天引用得到、標「你收藏的」（MVP 可用）。

---

## Phase 3：US2（P1）——PDF 收進（含 >30 頁不崩）

- [X] T007 [P] [US2] `test_content_ingest.py` 加紅測：`ingest_pdf` 注入 **stub converter**（回固定 markdown，含一個表格與 `$$` 公式）→ 切塊存進、`retrieve_corpus` 查得到、表格/公式塊完整；converter 拋例外→`SourceUnavailable`（best-effort，不崩）。
- [X] T008 [US2] `src/knowfield/ingest/convert.py`：`DocConverter` 協定＋`MistralDocConverter`（gateway `/v1/ocr`；>30 頁走 `pdftoppm` 逐頁 `image_url` 合併；真實 adapter 不進單元測試）。`service.py`：`ContentIngestService.ingest_pdf(pdf_bytes=None, pdf_url=None, title="")`（converter→chunk→store；轉檔失敗→`SourceUnavailable`）。跑 T007 轉綠。
- [X] T009 [P] [US2] `test_ingest_web.py` 加紅測：`app.state.doc_converter` 注入 stub → `POST /ingest/pdf`（url 或上傳）→ 收進、`/chat` 引用；converter 失敗→頁內友善、不噴 500。
- [X] T010 [US2] `app.py`：`app.state.doc_converter`（預設 `MistralDocConverter(config)`）；`POST /ingest/pdf`（`file` 上傳或 `url`）→ `ingest_pdf`；失敗攔友善。`ingest.html`：加「PDF 上傳/URL」表單。跑 T009 轉綠。

**檢查點**：PDF→markdown→切塊→可引用；轉檔失敗 best-effort、不崩。

---

## Phase 4：US3（P1）——純度守衛（原則 6）

- [X] T011 [P] [US3] `test_ingest_web.py` 加**守衛**紅測：`POST /ingest/paste` 收含 `SECRET_外部觀點` 的內容 → `build_field_system_prompt(list_why_nodes("anointed"))` **不含** `SECRET_外部觀點`；`list_why_nodes` 數量**不因收進而增**。跑轉綠（天然成立＝收進存 corpus、不寫 why_nodes）。

**檢查點**：收進＝證言、絕不進地基、不自動變核心理解。

---

## Phase 5：Polish＋回歸

- [X] T012 [P] 全繁中檢查（貼上/PDF 表單、收了幾塊提示、來源標記）＋範圍守住（**無** URL 抓取/YouTube/擴充/手機分享/Office/影音/hybrid/rerank/視覺檢索/檢索調參 UI/CLI/新表）。
- [X] T013 跑 `uv run pytest -q` 全綠（現 277 ＋本增量）；spec 022/023/025/028/029 零回歸。真後端手動抽驗：貼一段＋收一份繁中 PDF → `/chat` 引用得到、標「你收藏的」。

---

## 依賴與平行
- 切塊（T001-2）→ US1 貼上（T003-6）→ US2 PDF（T007-10）→ US3 守衛（T011）→ Polish。
- **MVP＝US1**（貼上）；US2 PDF 為已驗證第二張嘴；US3 守衛不可省。
- 紅測多可 `[P]`。
