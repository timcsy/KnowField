# Web 契約：`/search`（web 搜尋）

## GET /search?q=<查詢>
- 無 q → 顯示查詢框＋提示。
- 有 q → 呼叫 `web_search_factory(q)` 取結果，列出（標題、可點原文網址、摘要），每則一個「收進」鈕。
- 查無結果 → 明確提示（FR-006）。
- 後端失敗/未設金鑰 → **頁內友善繁中**、頁面正常、無 traceback（FR-005）。
- **結果不落庫**（FR-003）。

## 收進（復用既有 POST /ingest）
- 每則結果：`<form action="/ingest" method="post"><input type=hidden name="ref" value="{url}"><button>收進</button></form>`。
- 走 `SeedService.ingest(url)`：抓取→消化→嵌入→種子；去重、失敗友善、溯源（spec 006）。
- 收進後該篇 `ask` 可檢索到；**未收進的結果不落庫**。

## 不變式（對映 FR）
- 結果短暫、人冊封才留（FR-003，原則 5）；收進復用 ingest（FR-002/007）。
- 可插拔：離線 Stub 可測、真實 urllib 零 pip 相依（FR-004）。
- 後端失敗友善繁中（FR-005）；全繁中（FR-008）。
