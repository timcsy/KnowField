# Phase 0 Research：RAG 問答 MVP 技術決策

## R1：嵌入向量怎麼落庫

- **Decision**：新增獨立表 `entry_embeddings(entry_id, tag, dim, vector_json)`，主鍵
  `(entry_id, tag)`；`entry_id` → `digest_entries.id`，`tag` = embedder 身分
  （`hashing-256` 或 `openai-<model>`），`vector_json` = JSON 陣列。
- **Rationale**：獨立表保持 `digest_entries` 乾淨；`tag` 讓**不同 embedder 的向量共存且不
  互相污染**（離線↔OpenAI 空間不同，不可混比）；可重嵌、可回填。
- **Alternatives rejected**：在 `digest_entries` 加 `embedding` 欄——換 embedder 就得覆寫、
  無法並存；專用向量庫（faiss/sqlite-vss）——個人語料暴力 cosine 已毫秒級，YAGNI。

## R2：舊條目與 embedder 切換的嵌入回填（FR-009 + FR-010）

- **Decision**：**雙軌**——(a) `save_digest` 時對新條目**批次嵌入**並存（FR-009，避免查詢
  時付成本）；(b) 查詢時 `ensure_embeddings(entries, embedder)`：對「查無當前 tag 向量」的
  條目**批次 `embed_many` 補算並落庫**（FR-010 舊資料、embedder 切換、任何缺漏的安全網）。
- **Rationale**：兩軌合一個判斷「(entry_id, tag) 有沒有向量，沒有就批次補」——同時解掉
  FR-009/010 與切後端；**惰性回填免另立一個回填指令**（YAGNI、對使用者透明）。
- **批次**：補算一律走 `embed_many`（一次呼叫多筆），**不在迴圈裡逐一 `embed`**（experience：
  逐一呼叫慢又觸發額度隔離）。
- **Alternatives rejected**：只惰性回填（違 FR-009 首問付全庫嵌入成本）；只 on-save（舊資料
  永遠漏，違 FR-010）。

## R3：答案合成後端（既有介面都不合用）

- **Decision**：新增 `Answerer` 協定 `answer(question, passages, lang) -> str`。
  - `StubAnswerer`（離線、確定性、grounded）：用給定段落組出答案，**逐點標 `[n]`**，只引用
    傳入段落，不編造。供零外部呼叫測試。
  - `OpenAIAnswerer`（複用 `_post` `/chat/completions`）：grounded prompt——「**只根據**編號
    段落作答、**逐點以 [n] 標來源**、**材料不足就說沒有相關材料**、不得引用未提供的內容」。
- **Rationale**：既有 `Summarizer(title,abstract,topic)→(定位,為何)` 與 `ArticleWriter` 都是
  「單則消化」，**沒有「問題＋多段落→帶引用答案」的介面**；RAG 需要新協定。複用 `_post`
  與 factory 樣式，維持可插拔（教訓 1）。
- **Alternatives rejected**：硬套 Summarizer——語義不符、會逼出畸形 prompt。

## R4：溯源如何在結構上保證（原則 3）

- **Decision**：`RagService` 只把**實際檢索到的 top-k 條目**編號為 passages 傳給 Answerer，
  回傳 `RagAnswer{text, sources[], no_material}`；`sources` = 這些條目的 `(編號, 標題, 原文
  連結)`。答案裡的 `[n]` 對應 `sources[n]`。**來源清單由程式端從檢索結果生成，非由模型自報**
  ——模型就算漏標，來源清單仍是真實檢索集合，可回原文（原則 3 鐵律不靠模型自律）。
- **忠實度**：真實後端另做人工抽查（承 SeerGuard 抽查精神）；離線只驗接線。

## R5：相關度門檻與「查無相關」（FR-004）

- **Decision**：`config.rag_min_score`＋`rag_top_k`（預設 6）。載入 scope 語料→嵌問題→cosine
  排序→濾掉低於門檻者→若剩 0（或語料空）→`no_material=True`，回「沒有相關材料」，
  **不呼叫合成後端、不產生任何內容**。
- **門檻依 embedder 尺度校準（T025 真跑修正）**：真實與離線 embedder 的 cosine **尺度不可比**
  （教訓 4 的延伸）。**實測 text-embedding-3-small**：命中≈0.62、鬆散相關 0.10–0.25、
  **完全無關的問題最高才 0.22**。故固定 0.10 太低→什麼都放行。改成 `Config.from_env` 依
  backend 給預設：**openai≈0.30**（濾噪音＋擋無關）、**offline≈0.05**（雜湊尺度低），
  env `KNOWFIELD_RAG_MINSCORE` 可覆寫。
- **Rationale**：門檻是「無來源不出貨」的閘。此校準一併解掉兩個真跑 bug：無關問題正確查無、
  且真命中時只有命中者過關→來源清單只列實際相關的（不再列 6 個噪音來源）。
- **Alternatives rejected**：單一固定門檻——真實/離線尺度不同，一個值服務不了兩邊；相對
  門檻（top×比例）——YAGNI，實測 backend 分流的絕對門檻已夠且可 env 微調。
- **已知限制**：0.30 是對 text-embedding-3-small 校準；換嵌入模型可能要重調（env 可覆寫）。

## R6：範圍過濾（FR-005）

- **Decision**：`repository.list_corpus_entries(today: bool)`：`today=False` 取**所有** digests
  的 entries；`today=True` 僅取 `MAX(digests.id)` 那份。回傳含 `entry_id, title, url,
  article_body, article_headline, digest_date`。
- **Rationale**：「今天」＝最近一份匯整（代表當日分診）；歷史 entries 本就都在 `digest_entries`，
  只需查詢，不需新儲存。

## R7：嵌入哪段文字

- **Decision**：嵌 `article_headline + "\n" + article_body`（整理過標題＋消化散文＝語義最濃）；
  問題單獨嵌。空 body 的舊兩欄式條目則退回 `title`。
- **Rationale**：消化散文是語義最豐處；標題補強主題訊號。
