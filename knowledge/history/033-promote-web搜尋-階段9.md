# 033：promote web 搜尋 → vision 階段 9
> 日期：2026-07-25

## 轉移
使用者選「暖身做 web search」（雖較重）。promote `趨勢熱詞發現` draft 的 **A（web 搜尋 adapter）**。

- **vision 階段 9（已 commit）**：web `/search`——query→可插拔搜尋後端→結果→每則「收進」冊封成種子。
  第三口進水（web search＝臨時大網/反濾泡）。**B（趨勢讀數）留後續**。
- 沿用 OpenAI 後端款（urllib 呼叫、可插拔、預設離線 stub）→ **不加 Python 相依**（憲章 IV 站得住），
  只多一個可選外部服務。

## 範圍與復用
- 復用：spec 006 ingest（`fetch_url`/SeedService）＝「收進成種子」；web ingest 工廠樣式；config 後端。
- 新增：可插拔 WebSearch 後端（search(query)→結果；stub/真實 API）、config（搜尋 API）、`/search` 頁。
- 概念：搜尋結果=短暫流、人冊封才留（原則 5）；搜尋=AI 撒網、冊封=人挑（與 2b 同模式）。

## 下一步
`/speckit-specify`。cautions：教訓 1（stub 離線可測）、教訓 3（後端失敗友善）、原則 5（結果短暫、
人冊封才留）、原則 3（結果帶網址）。

## 狀態
✅ 已 promote（使用者 2026-07-25 確認）
