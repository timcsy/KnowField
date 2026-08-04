# 技術方案：個人內容進料——貼上＋PDF（spec 030）

**規格**：[spec.md](./spec.md) ｜ **分支**：`030-content-ingest`

## 技術脈絡
- Python 3.12＋stdlib 核心；FastAPI＋Jinja2；SQLite。既有：`SeedService.ingest`（url→種子）、`repo.ingest_seed`（一筆 digest_entry）、`repo.ensure_embeddings`、`retrieve_corpus`（spec 029，讀 `digest_entries`）、`/chat` 引用「你收藏的」（029）。
- **核心洞見**：把「一段內容切成多塊、每塊當一筆 digest_entry 存」即可——`retrieve_corpus`／`/chat` 自動吃到、自動標「你收藏的」、自動不進地基（它只讀 anointed why_nodes）。**無新表**（教訓 8），純度守衛（原則 6）由「存成 corpus 非 why_node」天然成立。

## 架構（新 `src/learnnews/ingest/` 套件）
- `chunk.py`：`chunk_markdown(md, target=400, overlap=40) -> list[str]`。純函式、零相依、離線可測。規則：**原子塊不切**（fenced code ```、`$$` 數學、markdown 表格連續 `|` 行）；**章節（`^#{1,6} `）為優先切點**；章節內 prose 按**字元數**切＋重疊；短內容→一塊。
- `convert.py`：`DocConverter` 協定（`to_markdown(pdf_bytes=None, pdf_url=None) -> str`）＋`MistralDocConverter`（真實：走現有 gateway `/v1/ocr`，`azure/mistral-document-ai-2512`；>30 頁→每頁 `pdftoppm` render 成圖走 `image_url` 逐頁 OCR 合併，避開 30 頁上限與笨切爆脹）。真實 adapter 不進單元測試（比照 make_chat_backend）；**離線靠注入 stub**（教訓 1）。
- `service.py`：`store_chunks(repo, embedder, title, url, chunks, source_class)`＝逐塊 `ingest_seed`＋批次 `ensure_embeddings`，回塊數。`ContentIngestService.ingest_text(text, title)`／`ingest_pdf(pdf_bytes|pdf_url, title)`；空內容→`IngestResult(status="empty")`；轉檔/切塊/embed 失敗攔成友善（教訓 3）。

## web（app.py＋ingest.html）
- `app.state.doc_converter`（預設 `MistralDocConverter(config)`；測試注入 stub）。
- `POST /ingest/paste`（`text`,`title`）→ `ContentIngestService.ingest_text`。
- `POST /ingest/pdf`（檔案上傳 `file` 或 `url`）→ `ingest_pdf`。失敗經既有 `(SourceUnavailable, OpenAIError)` 攔成頁內友善。
- `ingest.html`：既有 url 表單 ＋ 新增「貼上」textarea 表單 ＋「PDF 上傳/URL」表單；結果顯示收了幾塊。
- 每塊 `source_class="ordinary"`（外部證言，非 explainer；原則 6）。

## 資料
- 不新增表。一來源→多筆 `digest_entries`（走 `ingest_seed`）。塊標題＝`{來源標題}（i/n）`、body＝塊文、url＝來源（paste 用 `paste:<hash>`、PDF 用檔名/URL）。embedding 走既有 `ensure_embeddings`。

## Constitution Check
- I TDD：切塊純函式紅測、轉檔注入 stub、貼上→檢索 web 測、純度守衛測、>30 頁 best-effort 測。✅
- II 繁中：介面/提示/來源標記全繁中。✅
- IV 零相依：切塊純 stdlib；轉檔重活（gateway/pdftoppm）藏 `DocConverter` 後、離線 stub。✅
- V 可觀測/錯誤：轉檔/切塊/embed 失敗 best-effort＋log＋友善頁，不噴 500。✅

## 階段
- Phase 0：research.md（切塊策略、轉檔路徑、30 頁對策的決策與替代）。
- Phase 1：data-model.md（Chunk→digest_entry 映射）、contracts（DocConverter 協定、/ingest/paste、/ingest/pdf）、quickstart.md。
