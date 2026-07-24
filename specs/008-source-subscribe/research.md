# Phase 0 Research：來源訂閱 技術決策

## R1：feed 探測（URL → feed URL）
- **Decision**：`discover_feed(url, http_get)`：①先把 url 當 feed——`RssAdapter` 能解析出條目就用；
  ②否則抓 HTML，用 stdlib `html.parser` 找 `<link rel="alternate" type="application/rss+xml|atom+xml"
  href="…">`，相對路徑以 `urljoin` 解析；③找不到 → 回 None（→ 友善提示「找不到 RSS」）。
- **Rationale**：多數部落格（Substack/Medium/WordPress）首頁都有 alternate link；stdlib 零相依。
- **Alternatives rejected**：feedparser/bs4 第三方——違零相依；猜常見路徑（/feed、/rss）——脆、易誤判。

## R2：加前驗證有料（FR-003、教訓 7）
- **Decision**：`validate_feed(feed_url, http_get)`：以 `RssAdapter("_probe", lambda since: http_get(
  feed_url)).fetch(now)` 實抓；**回條目數 ≥1 才算有效**；`SourceUnavailable`/0 條 → 無效。
- **Rationale**：復用既有 RSS 解析（不另寫 parser）；「實測有料才落庫」＝保證做進程式，不靠使用者
  保證 URL 對。死 feed 永不入庫 → 匯整不會一直對它報錯。

## R3：Source 生成與去重（FR-007）
- **Decision**：`subscribe(url, http_get) -> Source`：discover→validate→建
  `Source(id=slug(domain), name=feed 標題 or domain, type='news', access_method='rss',
  endpoint=feed_url, enabled=True)`。`id` 用網域 slug（穩定、可去重）；加前先 `list_sources` 查同 id
  → 已存回「已在追蹤」不重加（web 層判斷）；落庫用既有 `upsert_source`（ON CONFLICT(id) 更新）。
- **Rationale**：網域 slug 讓同站多次貼歸一；名稱優先取 feed `<title>`（人看得懂）。

## R4：加後自動帶入匯整（FR-005）＋刪除被尊重
- **Decision**：不改抓取管線——`build_adapters(repo.list_sources(enabled_only=True))` 已消費 DB
  sources（`_ADAPTERS['rss']=RssAdapter`）。停用＝`set_source_enabled(id,False)`；刪除＝新
  `delete_source(id)`。digest 僅在 `list_sources()` **全空**才重種 DEFAULT_SOURCES → **刪除被尊重**。
- **Rationale**：現成，零改管線；符合使用者主權（刪了不自動補回）。

## R5：web 注入點（離線可測）
- **Decision**：`app.state.subscribe_factory = lambda url: subscribe(url, default_http_get)`（預設真實
  urllib，復用 `seed.fetch.default_http_get`）；測試覆寫成回假 Source 或拋 `SourceUnavailable`。
- **Rationale**：比照 spec 006/web ingest 的工廠注入樣式，契約測試零外部呼叫。

## R6：失敗處理（FR-004、教訓 3）
- **Decision**：`subscribe` 對「無 feed／驗證無料／網路失敗」統一拋 `SourceUnavailable`（附繁中原因）；
  web `POST /sources/add` 攔成頁內友善訊息、**不落庫任何來源**、不噴堆疊。
