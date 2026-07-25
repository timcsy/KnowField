# 048：web 活水 news 模式（階段 13 增量 b）＋ _canonical 混時區崩潰修正

> 日期：2026-07-26　｜　承接 history/046（live web 活水）

## 緣起（使用者驗證回饋）
啟用 web 活水真跑後，使用者看到帶進的是 SEO 常青清單文（bentoml「Best Open-Source LLMs 2026」、
instaclustr「Top 7 LLMs」），**不是剛紅新聞**。診斷：**通用查詢＋一般搜尋**在開放網路回的就是 SEO
內容。使用者選 **B（news 模式）** 根治。

## ① spec 016：web 活水 news 模式
- `WebSearch.search` 加 **keyword-only** `news=False`、`time_range=None`（向後相容）；`ApiWebSearch`
  news 模式 → Tavily payload `topic="news"`＋`time_range`。`StubWebSearch` 忽略（離線可測）。
- `WebSearchAdapter` 預設 `news=True`＋`time_range`（`config.search_news_time_range` week）；手動
  `/search`（`SmartSearch`）不帶 news → 維持一般搜尋（要廣）。
- **真跑驗證**：web 活水改回真新聞（SecurityWeek「Cisco Launches Low-Cost AI Models」、Axios），
  SEO 清單文消失。

## ② 崩潰修正：_canonical 混時區 published_at
- **真因**：`DigestBuilder._canonical` 以 `min(candidates, key=lambda it: it.published_at or datetime.max)`
  挑代表；`published_at` 混時區——atom/arxiv `fromisoformat`→aware、rss/None/web→naive。同一去重
  群組混到 aware＋naive → `min()` 拋 `can't compare offset-naive and offset-aware datetimes`。
- **後果放大**：`build` 的 per-adapter try **只攔 `SourceUnavailable`**，這個 TypeError 發生在
  dedup 選代表階段（fetch 之後）→ **一個群組壞就拖垮整份 digest**。使用者那次重整整個失敗
  （303 導 refresh_fail、無新匯整）。
- **修**：排序鍵把 aware `astimezone(utc).replace(tzinfo=None)` 轉 naive UTC 再比。`test_canonical_tz`(2)。

## 教訓（提案升 experience，待人確認）
1. **聚合混來源資料要正規化再比較**：跨來源的日期/型別各異（時區有無），比較前**統一正規化**，
   否則 min/max/sort 會炸。是「餵進最底層前先歸一」的家族。
2. **單點失敗不該拖垮整批**：批次聚合的例外攔截要**夠寬**（不只預期的一種），一個壞項→標記
   跳過，別讓整批崩。build 只攔 `SourceUnavailable` 是漏洞（現靠正規化避開，但攔截面偏窄仍是隱患）。

## 產物
- `search/websearch.py`（news/time_range）、`sources/websearch_adapter.py`、`cli/fetchers.py`、
  `config.py`（`search_news_time_range`）、`digest/builder.py`（`_canonical` 時區正規化）。
- 測試：`test_websearch`(+3)、`test_websearch_adapter`(+2)、`test_canonical_tz`(2)。260→267 綠。
- 規格：`specs/016-web-news-mode/`。commit：spec 016 `6d51f45`、崩潰修正（本批）。

## 出口
- 階段 13 增量 b 完成。web 活水現在撈近期新聞、匯整均衡（每來源上限 history/047）、缺漏標具體來源。
- 後續：興趣驅動查詢、竄升/成核、build 攔截面加寬（教訓 2 的隱患）。
