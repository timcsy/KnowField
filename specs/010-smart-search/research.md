# Research：智慧搜尋（階段 9 增量 b）

## R1：整理放哪層？
- **決策**：新模組 `search/smart.py`，與 `websearch.py` 同層；一個 `SmartSearch` 服務注入
  `web_search`／`fetch`／`embedder`／`answerer`，`run(query)->SmartResult`。
- **理由**：智慧搜尋是「搜尋 × RAG × 抓取」的**編排**，不屬任一既有模組；放 search/ 與其資料源
  （websearch）同層最直覺。answerer/embedder/fetch 都以**依賴注入**傳入 → 離線可測、不綁後端。
- **否決**：塞進 `rag/service.py`（RagService 綁 Repository／落庫語料，智慧搜尋不落庫，語義不符）；
  塞進 web 路由（不可單元測試、違教訓 1）。

## R2：排序在抓取前還是後？
- **決策**：**先排序、再抓 top-N 內文**。用 `Embedder` 嵌 query 與每則結果的 `title＋snippet`
  （便宜、免抓網頁），cosine 排序全部結果；只對**排序後前 N 則**呼叫 `fetch_url` 抓內文做整理。
- **理由**：抓網頁貴（N 次 http），排序在前確保「抓的是最相關的」；且排序涵蓋全部結果、整理
  只吃最相關的少數 → 成本與品質雙贏。`[n]` 編號＝排序後序位。
- **否決**：先抓全部再排（浪費抓取）；不排直接抓前 N（可能整理到不相關的）。

## R3：passages 轉接（不改 answerer 介面）
- **決策**：把每則要整理的結果包成 `CorpusEntry(entry_id=n, title=r.title, url=r.url,
  body=抓到的內文 或 r.snippet, headline=r.title)`，丟給 `Answerer.answer(query, passages, "繁體中文")`。
- **理由**：`Answerer` already 吃 `list[CorpusEntry]`、逐點標 `[n]`（見 `StubAnswerer`）；用既有型別
  轉接＝零介面變更、`[n]` 語義天然對齊。`Source(n, title, url)` 供頁面來源清單。
- **注意**：`entry_id` 這裡不是 DB id（不落庫），僅佔位；不會寫回資料庫。

## R4：grounded／無材料（教訓 7 落結構）
- **決策**：整理文字產生後，過 `rag.service._is_no_material(text)`；命中則 `SmartResult.no_material=True`、
  **不出 `[n]` 來源**（同問答頁「說沒材料就不列來源」的矛盾修正）。真實後端沿用 `OpenAIAnswerer`
  的 grounded system prompt。
- **理由**：直接復用 spec 005 已驗證的 grounded 防線與矛盾修正（history/027），不重寫、不靠提示自律。
- **抽出共用**：把 `_is_no_material` 從 `rag/service.py` 提升為可 import 的模組級函式（已是模組級，
  直接 import 即可）。

## R5：降級策略（教訓 3）
- **單則內文抓不到**（`fetch_url` 拋錯）：該則 passage 退回用 `r.snippet`（snippet 也空 → 用 title）；
  **不中斷**整段整理。
- **整體整理失敗**（embedder／answerer／全部抓取失敗、無金鑰逾時）：`/search` 路由**分層攔截**——
  整理段顯示友善繁中「整理暫時無法產生」，**但仍照常列出（未排序或原序）結果、每則可收進**。
- **理由**：整理是加值，搜尋結果是底線；整理掛了不該讓使用者連結果都看不到（FR-008）。

## R6：路由分層攔截
- **決策**：`/search` 先取搜尋結果（既有 try/except `SourceUnavailable`）；**再**在另一個 try 內跑
  `smart_search_factory` 產生整理與排序。搜尋失敗 → 友善錯誤（同階段 9）；**整理失敗 → 整理段錯誤
  但結果照出**。
- **理由**：兩種失敗獨立，攔在不同層才能滿足「整理掛了仍列結果」。

## R7：`[n]` ↔ 結果卡對應（複用 ask 渲染）
- **決策**：結果卡加 `id="res-{{ loop.index }}"`；整理段用 marked＋MathJax 渲染，`[n]` 以 regex 轉成
  `<a href="#res-n" class="cite">n</a>`（複用 `ask.html` 那套 JS／`base.html` 的 `.cite`／`:target`）。
- **理由**：問答頁已有維基式 `[n]` 上標捲動的完整實作，直接沿用、風格一致。整理只引用前 N 則，
  `[n]` 落在排序後前 N，捲到對應卡。

## R8：top-N 值
- **決策**：預設 **N=4**，設 `Config` 可調（`smart_search_topn`，預設 "4"）。
- **理由**：3–4 則足以整理出全貌，再多則 http 成本與延遲上升；使用者單次觸發、4 可接受。離線
  stub 測試不受 N 影響（結果數少）。

## R9：離線可測（教訓 1）
- **決策**：`SmartSearch` 全部依賴可注入；契約測試注入 `StubWebSearch`＋stub fetch（回固定 HTML）＋
  `HashingEmbedder`＋`StubAnswerer`，零外部呼叫驗證整條鏈（排序→抓取→整理→`[n]`）。
- **理由**：教訓 1——真實側坑多，stub 全鏈綠燈是 TDD 底線。
