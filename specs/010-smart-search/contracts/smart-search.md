# Contract：智慧搜尋

## `SmartSearch.run(query: str) -> SmartResult`（`search/smart.py`）

**輸入**：非空 query。**輸出**：`SmartResult`（見 data-model）。

- **MUST** 先用 `embedder` 對 `query` 與每則結果 `title+snippet` 算 cosine、**排序**全部結果（最相關在前）。
- **MUST** 對排序後**前 N 則**呼叫注入的 `fetch`（預設 `fetch_url`）抓內文；**單則失敗 MUST 退回
  該則 snippet**（snippet 空→title），不中斷。
- **MUST** 把前 N 則包成 `CorpusEntry(entry_id=序位, title, url, body=內文/snippet)`，呼叫
  `answerer.answer(query, passages, "繁體中文")` 產生 `overview`。
- **MUST** 對 `overview` 跑 `_is_no_material`；命中 → `no_material=True`、`sources=[]`。
- **MUST** 回傳**排序後完整** `results`（不只前 N），供頁面每則可收進。
- **依賴全部可注入**（web_search／embedder／answerer／fetch）→ 離線 stub 零外部呼叫可測。

## `make_smart_search(config) -> SmartSearch`（`backends/factory.py`）

- 組 `make_web_search(config)`＋`make_embedder(config)`＋`make_answerer(config)`＋`fetch_url`＋
  `config.smart_search_topn`（預設 4）。

## `GET /search?q=<query>`（擴充）

- **q 空**：維持階段 9（不搜、不整理）。
- **q 非空**：
  1. 取搜尋結果失敗（`SourceUnavailable`）→ 友善繁中 `err`、不整理（同階段 9）。
  2. 搜尋成功 → 呼叫 `app.state.smart_search_factory(q)` 取 `SmartResult`。
     - **整理階段拋錯 MUST 被攔**：頁面 `overview_error` 顯示友善繁中，**但仍列出結果（可收進）**。
  3. 渲染：頂端 `overview`（`[n]`→`#res-n`）＋下方**排序後**結果卡（每則 `id="res-n"`、含「收進」）。
- **MUST NOT** 落庫任何搜尋結果或整理；**MUST NOT** 回 500 或露 traceback。
- `app.state.smart_search_factory` 可被測試覆寫（注入假 SmartResult）。

## 契約測試（離線、零外部呼叫）

1. `/search?q=X` → 頁面含**整理段**＋每則結果卡有 `id="res-n"`＋「收進」表單。
2. 整理段的 `[n]` 是連到 `#res-n` 的連結。
3. **排序**：注入 embedder 使某則最相關 → 它排在結果清單第一、且 `[1]` 指向它。
4. **單則抓不到**：注入 fetch 對某 url 拋錯 → 整理仍產生（用 snippet）、頁面不崩。
5. **整理整體失敗**：注入 smart_search_factory 拋錯 → 頁面顯示友善繁中整理錯誤、**仍列原始結果**、非 500。
6. **無材料**：注入 answerer 回「沒有相關材料」→ 頁面顯示無材料、**不列 `[n]` 來源**。
7. **收進不變**：對一則結果 POST /ingest → 成種子（同 spec 009 US2，真實離線 ingest）。
8. `SmartSearch.run` 單元：排序正確、passages 轉接（entry_id/title/url/body）、降級、no_material。
