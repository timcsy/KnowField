# Phase 0 Research：種子 ingest 技術決策

## R1：種子的「家」——種子容器 digest（vs 獨立表）

- **Decision**：種子存入一個**哨兵「種子容器」digest**（`digests.date = '__種子__'`），種子即
  該容器的 `digest_entries`。`digest_entries` 加 `source_class TEXT DEFAULT 'ordinary'`（種子解說文
  存 `'explainer'`）。
- **Rationale**：復用 `digest_entries` → **`entry_id` 空間仍唯一**，`entry_embeddings.entry_id`
  （增量 1 已落庫）**免動、免遷移**；`list_corpus_entries` 幾乎不改就撈得到種子。最小改動、YAGNI。
- **Alternatives rejected**：**獨立 `seeds` 表**——其 id 與 `digest_entries.id` **撞** `entry_embeddings`
  的主鍵（entry_id），得改增量 1 已出貨的嵌入表結構（加 kind 欄或改 TEXT 鍵），侵入性高。
- **代價（誠實記）**：種子「假裝成 digest」語義略醜；以哨兵 date 隔離、`--today` 明確排除來緩解。

## R2：`--today` 與種子的關係

- **Decision**：`list_corpus_entries(today=True)` ＝**最近一份『真實』每日匯整**
  （`MAX(id) WHERE date != '__種子__'`）；`today=False`（累積）＝**所有 digest_entries 含種子**。
- **Rationale**：`--today`＝「今天這批分診」，種子不屬於某天的分診；但種子是 KB 深度，累積問答
  本就該含。避免種子容器搶走 `MAX(id)`。

## R3：依 ID/URL 抓單篇（arXiv adapter 只依類別查）

- **Decision**：新增 `seed/fetch.py`：
  - `fetch_arxiv_by_id(id, http_get)`：組 `export.arxiv.org/api/query?id_list=<id>`，**複用 arXiv
    Atom 解析**取第一筆 → `Item`（title/abstract/url）。
  - `fetch_url(url, http_get)`：抓 HTML，用 stdlib `html.parser` **淺抽** `<title>`＋主文段落文字
    → `Item`（abstract 級）。取不到正文 → 拋 `SourceUnavailable`。
  - `http_get(url) -> str` **可注入**（測試給 fixtures，生產用 urllib）——比照既有 `fetch_raw`
    可注入樣式（`sources/base.py`），離線可測（教訓 1）。
- **Rationale**：複用既有 Atom 解析與可注入取得樣式；URL 淺抽守 YAGNI（深 readability 後續）。
- **Alternatives rejected**：引入 readability/bs4 第三方——違零相依；本增量 abstract 級足夠。

## R4：識別正規化與去重（FR-004/007）

- **Decision**：arXiv 多寫法（`2407.12345`／`arXiv:2407.12345`／`.../abs/2407.12345`／含版本 `v2`）
  正規化為裸 id 當 `external_id`；一般 URL 用既有 `canonical_url`。去重用既有
  `content_hash(external_id, title, url)`——ingest 前查種子容器內是否已存，已存則回「已在庫」不重插。
- **Rationale**：直接復用 `sources/base.py` 既有去重工具，行為與每日去重一致。

## R5：解說文品質權重接進檢索（FR-005）

- **Decision**：`CorpusEntry` 加 `source_class`；`RagService` 排序改
  `weighted = cosine(q,e) * weight(e.source_class)`（`explainer`→`config.rag_explainer_weight`
  預設 1.5、其餘 1.0）。**相關度門檻仍套在原始 cosine**（`cosine >= min_score` 才入選），
  **權重只影響入選者的排序**——解說文不會把不相關內容擠進來。
- **Rationale**：門檻把關相關性（不被權重繞過）、權重決定「同樣相關時誰優先」＝「一篇打敗
  五十篇」。權重 env 可調（`KNOWFIELD_RAG_EXPLAINER_WEIGHT`）。
- **Alternatives rejected**：把權重乘進門檻——會讓解說文的弱相關內容混進答案，違 FR-004 精神。

## R6：消化與嵌入複用

- **Decision**：種子 `Item` → `ArticleBuilder.build(item, matched_topic='', with_image=False)`
  → `Article`（body/headline）；存為種子 entry 後，`ensure_embeddings` 批次嵌入落庫（沿用增量 1）。
- **Rationale**：種子與每日匯整消化格式一致 → `ask` 零改即可檢索；嵌入走既有惰性回填。

## R7：失敗不半殘（FR-006）

- **Decision**：`SeedService.ingest` 先**抓取＋消化成功**才寫入；任一步失敗（`SourceUnavailable`
  ／`OpenAIError`）→ **不寫任何 row**、由 CLI 攔成友善繁中、退出碼 1。
- **Rationale**：交易式——半殘種子會污染 KB 且無法溯源；寧可整篇失敗重來。
