# Research：live web 活水（階段 13）

## R1：WebSearchAdapter 形狀（複用 SourceAdapter）
- **決策**：`WebSearchAdapter` 繼承 `SourceAdapter`，但 `__init__(source_id, web_search, queries)`
  （不同於其他 adapter 的 `(source_id, fetch_raw)`——它用搜尋後端非 HTTP endpoint）。`fetch(since)`：
  對每個 query `web_search.search(q)` → 映 `Item(source_id="web", title=r.title, url=r.url,
  abstract=r.snippet)` → 依 url 去重 → `self._finalize(item)`（補 content_hash、驗 url）。
- **理由**：實作既有 `SourceAdapter.fetch` 介面 → 直接進 `build_adapters`／digest 管線，零改管線。

## R2：build_adapters 加 config、web_search 特例、金鑰閘（FR-003）
- **決策**：`build_adapters(sources, config=None)`。迴圈中：
  ```
  if s.access_method == "web_search":
      if config is None or not (config.search_api_url and config.search_api_key):
          continue                 # 無 config／無金鑰 → 不觸發（FR-003，行為與現況一致）
      adapters.append(WebSearchAdapter(s.id, make_web_search(config), _parse_queries(s.endpoint)))
      continue
  # 其餘照舊：cls(s.id, _http_fetch_raw(s.endpoint))
  ```
- **理由**：**金鑰閘做進 build_adapters**——沒金鑰就根本不建這個 adapter（不會用 StubWebSearch 的
  假結果污染 digest）。config 缺（如 pull 呼叫）也跳過 → web 活水只在 digest/refresh 生效、pull 保持專注。

## R3：呼叫處
- **決策**：`cli/digest_cmd.py` handle／`web/app.py` refresh → `build_adapters(sources, config)`；
  `web/app.py` pull stream → 維持 `build_adapters(sources)`（不傳 config → web 源被跳過）。
- **理由**：digest／refresh 是「拿當日全貌」該含活水；pull 是「深挖某主題」用其固定查詢無意義。

## R4：預設源（opt-in、預設停用）
- **決策**：`DEFAULT_SOURCES` 加
  `Source("web-ai-trends", "開放網路 AI 趨勢（需搜尋金鑰・opt-in）", "news", "web_search",
  "latest AI model release\nnew open-source LLM\nAI breakthrough announcement\nnew AI product launch",
  enabled=False)`。`_parse_queries(endpoint)`：換行/逗號分隔、strip、去空。
- **理由**：預設停用＝零成本（FR-003、原則 5）；endpoint 存查詢清單（複用既有欄位，零 schema）。

## R5：失敗與去重
- **決策**：`WebSearchAdapter.fetch` 對單一 query 搜尋拋 `SourceUnavailable` → 直接向外拋（digest
  的 `build` 已 `except SourceUnavailable`→ `missing.append(source_id)`）。跨 query 合併後依
  `url`（正規化：去尾斜線/fragment）去重。
- **理由**：沿用 digest 既有缺漏機制（教訓 3、憲章 V）；去重避免重複材料。

## R6：web 是流非種子（原則 5）
- **決策**：web `Item` 走 digest 管線＝當日**流**（存進 `digest_entries`，如同其他來源的匯整條目），
  **不經 ingest_seed**、**不進種子容器**。要留仍靠使用者「收進」（既有 `/ingest`）。
- **理由**：digest 條目本來就是流的紀錄；種子只經人「收進」。web 材料與 arXiv/RSS 材料同級，非種子。

## R7：時間過濾
- **決策**：MVP 不做 `since` 過濾（web 結果無可靠日期）——`fetch(since)` 忽略 since、回全部搜到的。
- **理由**：靠 digest 的興趣相關度排序＋去重把關；日期過濾列後續（需結果帶可靠時間）。

## R8：離線可測（教訓 1）
- **決策**：adapter 測試注入 `StubWebSearch`；integration 測試把 `WebSearchAdapter(StubWebSearch,…)`
  放進 `run_digest` 的 adapters，驗匯整含 web 材料——全零外部呼叫。
- **理由**：`build_adapters` 有金鑰時建的是 `ApiWebSearch`（真實），測試繞過它、直接注入 stub adapter。
