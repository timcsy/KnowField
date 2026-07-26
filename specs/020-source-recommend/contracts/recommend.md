# 契約：場驅動來源推薦（spec 020）

## `recommend_sources(web_search, embedder, repo, *, http_get=default_http_get, queries=None, limit=8) -> list[CandidateSource]`（新）
- **撒網**：對每條 roundup `queries` 跑 `web_search.search(q, news=False)`；蒐集結果。全失敗→拋 `SourceUnavailable`。
- **抽候選**：結果 url 取 netloc（去 www）去重；`list_hits`＝跨結果出現次數。
- **驗證（複用 spec 008）**：`discover_feed(homepage, http_get)`→`validate_feed(feed_url, http_get)`；
  - 有料 → `has_feed=True, feed_url` 設定。
  - **探到但驗證失敗/空 → 丟棄該候選**（死/幻覺，FR-002）。
  - 探不到 feed → `has_feed=False`（保留、標「無 RSS」，FR-010）。
  - 單一候選拋 `SourceUnavailable` → 跳過該候選、不拖垮整批。
- **場驅動（複用 spec 005/018）**：`field_score`＝候選文字 embed 對 `list_field_attractors` 的 cosine 最大值；無 attractor→0。
- **已訂閱**：`already_subscribed`＝`_source_id(feed_url)` 在 `repo.list_sources()`。
- **排序**：`(field_score, has_feed, list_hits)` 由大到小；取前 `limit`。
- **不落庫**：純讀＋純函式；候選只有經人訂閱才進 `sources`。

---

# 契約：web 路由（spec 020）

## `POST /sources/recommend`（新）
- **輸入**：無（opt-in 按鈕）。
- **行為**：`recommend = app.state.recommend_factory()`；渲染 `sources.html` 加 `recommendations`。
  - 空清單 → 友善提示「這次沒找到可訂的新來源」。
  - `SourceUnavailable`/`OpenAIError` → `_log.error`＋友善 `err`（教訓 3），頁不崩。
- **不自動**：只有此路由（人按）觸發；**不**接 digest 管線（FR-006 opt-in）。

## 訂閱候選（複用既有 `POST /sources/add`）
- 候選「訂閱」表單 POST `/sources/add`，`url=feed_url`（`discover_feed` 短路不重抓）；
  走既有驗證＋`upsert_source`＋「已在追蹤」判斷。**無新訂閱路由。**

## sources.html
- 「追蹤」表單下加「🔎 幫我找新來源」表單（POST `/sources/recommend`）。
- 推薦區塊：每項 網域＋feed 狀態＋理由＋場驅動標記；有 feed→「訂閱」（POST `/sources/add`）；
  已訂閱→「已在名冊」；無 feed→「無 RSS，靠 web 活水/收進補」。
