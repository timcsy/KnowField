# Phase 1 Data Model：來源訂閱

## Schema
**無變更**——復用 `sources` 表（`id/name/type/access_method/endpoint/enabled/…`）。

## 新模組 `sources/subscribe.py`
- `discover_feed(url, http_get) -> str | None`：url 當 feed 可解析→用；否則 HTML 找 alternate link；無→None。
- `validate_feed(feed_url, http_get) -> list[Item]`：`RssAdapter` 實抓，≥1 條才有效，否則拋/空。
- `subscribe(url, http_get=default) -> Source`：discover→validate→建 Source（id=網域 slug、name=feed 標題）；
  失敗拋 `SourceUnavailable`（繁中）。
- `_FeedLinkParser(html.parser.HTMLParser)`：找 `<link rel=alternate type=…rss/atom… href>`。

## Repository
- 既有：`upsert_source`（ON CONFLICT(id) 更新）、`set_source_enabled(id, bool)`、`list_sources(enabled_only)`。
- 新增：`delete_source(source_id) -> None`（`DELETE FROM sources WHERE id=?`）。

## Web 路由（照 /interests /library CRUD）
- `GET /sources`：`repo.list_sources()` → `sources.html`（名稱/類型/狀態＋加來源框）。
- `POST /sources/add`（Form `url`）：`subscribe_factory(url)` → 已存則提示「已在追蹤」、否則 `upsert_source`；
  失敗攔 `SourceUnavailable` → 頁內友善訊息、不落庫。→ 303 `/sources`（或帶結果重繪）。
- `POST /sources/toggle`（Form `source_id`, `enabled`）：`set_source_enabled` → 303。
- `POST /sources/remove`（Form `source_id`）：`delete_source` → 303。
- `app.state.subscribe_factory`（測試可注入）；導覽加「來源」。

## 資料流（加一個來源）
```
貼 url → subscribe_factory(url)：discover_feed → validate_feed(≥1 條) → Source
   ├ 有效且未追蹤 → upsert_source（啟用）→ 下次 digest 由 build_adapters 自動抓
   ├ 已追蹤（同 id）→ 「已在追蹤」不重加
   └ 無 feed/無料/網路失敗 → SourceUnavailable → 頁內友善繁中、不落庫
```
