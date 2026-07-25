# Contract：live web 活水

## `WebSearchAdapter(source_id, web_search, queries).fetch(since) -> list[Item]`
- **MUST** 對每個 query `web_search.search(q)`、把 `SearchResult` 映成 `Item`（title/url/abstract=snippet）。
- **MUST** 依 url 去重（同原文只一則）。
- **MUST** 搜尋拋 `SourceUnavailable` 時向外拋（由 digest `build` 攔成 missing）。
- 每則 `Item` 經 `_finalize`（content_hash、url 非空）。

## `build_adapters(sources, config=None) -> list[SourceAdapter]`（簽名擴充）
- `access_method=="web_search"`：**config 且搜尋金鑰齊 → 建 `WebSearchAdapter`**；否則**跳過**（FR-003）。
- 其他 access_method 行為不變。
- `_parse_queries(endpoint)`：換行/逗號分隔、strip、去空。

## DEFAULT 源
- `web-ai-trends`（`access_method="web_search"`、`enabled=False`、endpoint＝查詢清單）。

## 呼叫處
- digest（`cli/digest_cmd.py`）／refresh（`web/app.py`）→ `build_adapters(sources, config)`。
- pull（`web/app.py`）→ `build_adapters(sources)`（web 源被跳過）。

## 契約測試（離線、零外部呼叫）
1. `WebSearchAdapter(StubWebSearch(), ["q1","q2"]).fetch(...)` → 回 `Item` 清單、每則有 url、依 url 去重。
2. adapter：注入會拋 `SourceUnavailable` 的 web_search → `fetch` 向外拋（不吞）。
3. `build_adapters([web源], config=無金鑰)` → **不含** web adapter（跳過，FR-003）；
   `config=有金鑰` → **含** web adapter。
4. `build_adapters([web源])`（無 config）→ 不含 web adapter（pull 情境）。
5. `web-ai-trends` 在 `DEFAULT_SOURCES` 且 `enabled=False`（預設停用）。
6. **integration**：`run_digest(repo, adapters=[WebSearchAdapter(StubWebSearch,…), …], date, limit)`
   → 匯整 `entries` **含 web 材料**（title/url 對得上）；web 材料**在 `digest_entries`（流）、不在種子容器**。
7. **失敗→缺漏**：`run_digest` 帶會拋 `SourceUnavailable` 的 web adapter → 匯整照常產出、
   `missing_sources` 含該源 id。
