# Phase 0 Research：web 搜尋 技術決策

## R1：搜尋結果即算即棄（FR-003、原則 5）
- **Decision**：`GET /search?q=` 每次呼叫搜尋後端取結果、**只在該次回應渲染，不寫任何表**。
  只有使用者對某則按「收進」才經 ingest 落庫成種子。
- **Rationale**：搜尋＝AI 撒網（短暫流）、收進＝人挑（冊封）。不落庫＝零污染 KB、零新 schema、
  守原則 5。像 `/ask` 一樣 GET＋query，無狀態。

## R2：「收進」復用既有 ingest（FR-002/007，零新碼）
- **Decision**：每則結果一個 `<form action="/ingest" method="post"><input name="ref" value="{url}">`。
  按下走**既有 `/ingest`**（`SeedService.ingest(url)`：fetch_url→消化→嵌入→種子）→ 顯示既有 ingest
  結果頁。
- **Rationale**：`ingest` 已支援任意 URL、去重、失敗友善、溯源、離線可測——全複用，收進零後端新碼。
- **Alternatives rejected**：新 `/search/ingest` 路由——多餘；`/ingest` 已是「URL→種子」的正解。

## R3：可插拔搜尋後端（FR-004、憲章 IV）
- **Decision**：`search/websearch.py`：`SearchResult(title,url,snippet)`；`WebSearch` 協定
  `search(query)->list[SearchResult]`；`StubWebSearch`（離線、回固定假結果）；真實後端以 stdlib
  urllib POST 到 `config.search_api_url`（帶金鑰），解析回結果。`make_web_search(config)`：有
  `search_api_url`＋`search_api_key`→真實，否則 Stub。
- **Rationale**：同 embedder/answerer/article 後端的可插拔樣式；urllib＝**零 pip 相依**（同 OpenAI 後端）。
- **請求格式（2026-07-25 對準 Tavily）**：POST `https://api.tavily.com/search`，**`api_key` 放
  請求 body**（非 Bearer header），`{api_key,query,max_results,include_answer:false}`；回應解析寬鬆。
- **服務選型**：預設對 **Tavily 形狀**（`{results:[{title,url,content}]}`，為 LLM 設計、回乾淨內文）；
  端點/金鑰 config 可調 → 換 Brave/自架亦可。實作對回應做**寬鬆解析**（title/url/snippet 欄位容錯）。

## R4：失敗處理（FR-005、教訓 3）
- **Decision**：真實後端對「未設金鑰／逾時／服務錯誤」拋 `SourceUnavailable`（復用既有例外，附繁中）；
  `GET /search` 攔成**頁內友善提示**、頁面正常、不噴堆疊。Stub 永不失敗（離線可測）。
- **Rationale**：復用專案既有「外部不可用」例外與頁內攔截樣式（同 /sources 加來源）。

## R5：web 注入點（離線可測，FR-004）
- **Decision**：`app.state.web_search_factory = lambda q: make_web_search(config).search(q)`；測試覆寫成
  回假結果或拋 `SourceUnavailable`。契約測試零外部呼叫；「收進」測試沿用 `seed_ingest_factory`/
  假 `http_get`（spec 006 樣式）。

## R6：config
- `search_api_url: str = ""`、`search_api_key: str = ""`（env `LEARNNEWS_SEARCH_API_URL`／
  `LEARNNEWS_SEARCH_KEY`）。未設 → StubWebSearch。
