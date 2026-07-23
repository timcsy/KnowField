# Phase 1 資料模型：Web 介面

Web 是**呈現層**，不新增領域實體——複用 `Article`、`Figure`、`Digest`、`DigestEntry`、
`PullResult`、`PullEntry`、`InterestProfile`（見階段 1–5 data-model）。此處只記 web 特有的
輕量結構與一個 store 擴充。

## Store 擴充
### `repository.get_last_digest() -> Digest | None`
讀**最近一次落庫匯整**的全部 entries，組回一個 `Digest`（含 date、entries）供首頁渲染。
- 從 `digests` 取 MAX(id)；由 `digest_entries` 讀該匯整所有列（rank、title、url、
  matched_topic、article_body、figure_url、figure_kind）。
- 每列還原成 `DigestEntry`（item.title/url、Article(body, source_url, figure)）。
- 無匯整回 None（首頁顯示空狀態）。

## Web 呈現結構（view models，transient）
### PageEntry
一則在頁面上呈現所需的最小資料（由 Article/DigestEntry/PullEntry 轉出）：
- `headline`：整理過標題（無則原標題）
- `original_title`：原標題（與 headline 不同時顯示為副標）
- `paragraphs`：散文本體切段後的 list[str]（逸出後放 `<p>`）
- `source_url`：一鍵原文
- `figure`：{ `url`, `label`, `is_ai` } 或 None（`is_ai` 決定是否標「AI 示意・非原文」）

### CacheEntry（`web/cache.py`）
- `topic`（正規化）→ { `result`: PullResult, `at`: 時間戳 }；TTL 內命中即回，不打後端（FR-005）。

## 頁面 ↔ 資料流（文字）
```
GET /            → get_last_digest() → [PageEntry] → digest.html
GET /pull?topic  → 快取命中? 回 : run_pull()→存快取 → [PageEntry] → pull.html
GET /interests   → InterestService.list_topics() → interests.html
POST /interests/add|remove → InterestService.add/remove → 重導 /interests
（任一後端呼叫拋 OpenAIError → 例外處理器 → 友善繁中錯誤頁）
```
