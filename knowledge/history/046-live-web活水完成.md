# 046：live web 活水（階段 13）完成——治「追不到剛紅新聞」

> 日期：2026-07-25　｜　承接 history/045（promote＋①擴名冊）

## 轉移
vision 階段 13 **由「已 commit」→「已完成」**。spec 015 按 TDD 實作完：`WebSearchAdapter` 把開放
網路搜尋當成一個來源接進每日 digest——對「AI 最新」查詢跑既有 `WebSearch` 後端、把 `SearchResult`
映成 `Item` 餵進**既有 digest 管線**（去重/依興趣排序/消化）。**根治使用者核心痛點「追不到剛紅
AI 趨勢、連 Opus 5 都漏」**（①擴名冊止血 history/045、②本階段根治）。測試 **249→257**、零回歸。
commit `57a573e`。

## concept 反濾泡投影落地
concept「固定名冊訊噪比高但看不到剛紅」「第 3 層反濾泡/驚訝力＝伸手到策展名冊之外」——
`WebSearchAdapter` 就是這投影的 code：digest 不再只吃固定名冊，也主動搜開放網路。

## 關鍵設計（research）
- **adapter 化最省**：`WebSearchAdapter` 實作既有 `SourceAdapter.fetch` → 直接進 `build_adapters`／
  digest 管線，**零改管線**。它用搜尋後端而非 HTTP endpoint，故自訂 `__init__`。
- **金鑰閘做進 build_adapters**（FR-003）：`build_adapters(sources, config=None)`——web_search 源
  **只在 config＋搜尋金鑰齊時才建**（否則跳過），避免無金鑰時用 StubWebSearch 假結果污染 digest。
  config 缺（pull 呼叫）也跳過 → web 活水只在 digest/refresh 生效、pull 保持專注。
- **opt-in 預設停用**（原則 5＋成本閘）：`web-ai-trends` 源 `enabled=False`；使用者啟用＋設金鑰才生效。
- **web 是流非種子**（原則 5）：web `Item` 進 `digest_entries`（當日流），**不進種子容器**；要留靠「收進」。
- **失敗→缺漏**（教訓 3）：adapter 搜尋拋 `SourceUnavailable` → digest `build` 既有 `except` 攔成
  `missing_sources`、匯整照常。
- **零 schema**（教訓 8）：web 源＝`sources` 表一列（`access_method="web_search"`＋`ACCESS_METHODS` 加它）。

## ①擴名冊（止血，history/045、commit 141923e）
同一痛點的即時解：加 OpenAI Blog／TechCrunch／The Verge／HN AI／Reddit LocalLLaMA 進預設名冊。
與②互補：①加更多**固定**源、②伸手到名冊**之外**。

## 其他路線（否決）
- 無金鑰時用 stub 假結果：會污染 digest → 金鑰閘跳過。
- web 結果自動變種子：違原則 5、污染 KB → 只當流、收進才留。
- 硬抓 Threads/X：無公開 API/合規 → HN/Reddit 代理＋web 活水。

## 產物
- `sources/websearch_adapter.py`（`WebSearchAdapter`）、`cli/fetchers.py`（`build_adapters(…,config)`＋
  `_parse_queries`＋`web-ai-trends` 源）、`models`（`ACCESS_METHODS` 加 `web_search`）、呼叫處傳 config。
- 測試：`test_websearch_adapter`(3)、`test_build_adapters_web`(3)、`test_live_web_digest`(2)。
- 規格：`specs/015-live-web-digest/`。

## 出口
- 階段 13 完成。趨勢 draft live 活水段**已完成**。web 進水口三態齊：固定名冊（擴充）＋訂閱＋live 活水。
- 後續：興趣驅動查詢、竄升/成核、web 結果日期過濾。
