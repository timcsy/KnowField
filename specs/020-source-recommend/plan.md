# 實作計畫：場驅動來源推薦

**分支**：`020-source-recommend` ｜ **日期**：2026-07-26 ｜ **規格**：[spec.md](./spec.md)

## 摘要

一個 opt-in 動作「幫我找新來源」→ `WebSearch` 撒網搜 roundup（一般搜尋、`news=False`）→ 抽候選
網域 → **複用 spec 008** `discover_feed`＋`validate_feed`（擋死/幻覺）→ **場驅動排序**（候選文字嵌入
與 `list_field_attractors` 的 cosine 最大值＝最強訊號）→ 推薦清單 → 每項「訂閱」**複用 `/sources/add`**。

新程式集中在一個純函式模組 `sources/recommend.py`（串接既有零件）＋一條 web 路由＋sources.html 一塊。
**零新相依、零新表、不改既有訂閱/搜尋/嵌入邏輯。**

## Technical Context

**Language/Version**：Python 3.12+
**Primary Dependencies**：stdlib（urllib）；web 層 FastAPI＋Jinja2（既有，不新增）
**Storage**：SQLite（沿用 `sources` 表；推薦候選**短暫、不落庫**，除非人訂閱）
**Testing**：pytest（現 298 綠）
**Project Type**：web（本增量只動 web 層＋一個 sources 純函式模組）
**Constraints**：離線可注入替身零外部呼叫可測；opt-in／按需；人訂閱才進名冊

## Constitution Check

| 原則 | 判定 | 理由 |
|------|------|------|
| I. TDD | ✅ | 先寫紅測（recommend_sources 排序/驗證濾除/已訂閱標示、路由 opt-in、失敗友善）再實作 |
| II. 全繁中 | ✅ | 按鈕、推薦理由、錯誤訊息全繁中 |
| III. 規格驅動 | ✅ | spec 020→plan→tasks→impl，可追溯 FR |
| IV. 簡潔／YAGNI | ✅ | **零新相依/零新表**；一純函式模組＋一路由＋模板塊；串既有零件 |
| V. 可觀測／錯誤處理 | ✅ | 搜尋/抓 feed 失敗 `_log.error`＋友善繁中（教訓 3） |
| VI. 使用者決策主權 | ✅ | 原則 5：人按訂閱才進名冊、opt-in、推薦不自動觸發 |

**無違反、無複雜度追蹤項。**

## 技術方案

### 新模組 `src/learnnews/sources/recommend.py`（純函式、可注入）
```
@dataclass CandidateSource:
    domain: str; homepage: str; feed_url: str | None; name: str
    reason: str; field_score: float; list_hits: int
    has_feed: bool; already_subscribed: bool

recommend_sources(web_search, embedder, repo, *, http_get=default_http_get,
                  queries=None, limit=8) -> list[CandidateSource]
```
流程：
1. **撒網**：對每條 roundup query 跑 `web_search.search(q, news=False)`（預設 3~4 條 query 常數，可
   config 覆寫）；蒐集 `SearchResult`。失敗 → 拋 `SourceUnavailable`（路由攔）。
2. **抽候選網域**：從結果 url 取 netloc（去 www），**跨結果計數**＝`list_hits`（跨清單重複訊號）。
   去重成唯一候選（homepage=`https://<domain>/`）。
3. **feed 探測＋驗證（複用 spec 008）**：對每候選 `discover_feed(homepage)`→有 feed 再 `validate_feed`；
   驗證有料＝`has_feed=True, feed_url=…`；**探到但驗證失敗/空＝死/幻覺→丟棄**（FR-002）；
   探不到 feed＝`has_feed=False`（保留、標「無 RSS，靠 web 活水/收進補」，FR-010，不報錯）。
   每候選以 try/except `SourceUnavailable` 包住（單一站掛掉不拖垮整批，同 digest build 韌性）。
4. **場驅動分數（複用 spec 005/018）**：`attractors=list_field_attractors()`；
   `vecs=ensure_embeddings(attractors, embedder, tag)`；候選文字（name＋snippet）`embed`→對所有
   attractor `cosine` 取**最大值**＝`field_score`。無 attractor → 全 0（退回後續訊號）。
5. **已訂閱標示**：`already_subscribed`＝`_source_id(feed_url)` 已在 `repo.list_sources()`（FR-007）。
6. **排序（FR-005）**：key＝`(field_score, has_feed, list_hits)` 由大到小——**場驅動 ＞ 有活 feed ＞
   跨清單重複**。`reason` 據最強命中訊號組繁中理由。取前 `limit`。

### Web 路由 `POST /sources/recommend`
- `app.state.recommend_factory`（預設用 `make_web_search`＋`make_embedder`＋repo 建
  `recommend_sources`；測試覆寫）。
- 成功 → render `sources.html`，context 加 `recommendations`；空結果→友善「這次沒找到可訂的新來源」；
  `SourceUnavailable`/`OpenAIError`→`_log.error`＋友善 `err`（教訓 3）。
- **訂閱動作複用 `/sources/add`**：候選「訂閱」表單 POST `url=feed_url`（`discover_feed` 對 feed url
  會 `_looks_like_feed` 短路，不重抓）。無需新訂閱路由。

### sources.html
- 既有「追蹤」表單下加「🔎 幫我找新來源」表單（POST `/sources/recommend`）。
- 新增推薦區塊：`{% if recommendations %}` 逐項顯示 網域＋feed 狀態＋理由＋場驅動標記；有 feed→
  「訂閱」表單（POST `/sources/add`，`url=feed_url`）；已訂閱→標「已在名冊」；無 feed→標「無 RSS」。

### config（小旋鈕）
- `source_recommend_queries`（預設常數 roundup query 清單）、`source_recommend_limit`（預設 8）。

**不動**：`subscribe.py`、`websearch.py`、`ranking/embeddings.py`、`list_field_attractors`、schema、
既有 `/sources/add|toggle|remove`。

## Project Structure

### 受影響檔案
```text
src/learnnews/sources/recommend.py          # 新：CandidateSource + recommend_sources（純函式）
src/learnnews/web/app.py                     # 新路由 POST /sources/recommend + recommend_factory
src/learnnews/web/templates/sources.html     # 「幫我找新來源」表單 + 推薦區塊
src/learnnews/config.py                       # source_recommend_queries/limit（小旋鈕）
tests/unit/test_source_recommend.py           # 純函式測（排序/驗證濾除/已訂閱/無 attractor）
tests/contract/test_source_recommend_web.py   # 路由測（opt-in/friendly/訂閱複用 add）
```

## 複雜度追蹤
無。零新相依、零新表；串接既有零件（spec 008 subscribe＋009/016 websearch＋005/018 embedding）。

## 技能複用
`knowledge/skills/evaluate-and-add-source`（實測可用性→挑高訊號）：其「實測可用性」＝步驟 3 的
`validate_feed`（已體現）；「挑高訊號」＝步驟 6 場驅動排序。**沿用其精神，不重寫。**
