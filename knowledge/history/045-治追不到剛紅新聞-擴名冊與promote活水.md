# 045：治「追不到剛紅 AI 趨勢」——① 擴名冊止血 ＋ ② promote live 活水

> 日期：2026-07-25

## 緣起（使用者核心痛點）
使用者：「常常追不到最新 AI 趨勢，像昨天出 Opus 5，社群（Threads 等）也有心得，但工具連 Opus 5
都沒有。」診斷：**固定名冊偏論文骨幹（arXiv/HF）＋週刊策展（Import AI/Last Week in AI），對即時
產品新聞＋社群討論覆蓋幾乎為零**——arXiv 抓不到產品發布、週刊差一週、無官方源、無社群源。
正中 concept「固定名冊訊噪比高但看不到剛紅」。使用者選「都加」。

## ① 擴名冊（止血，已完成 commit `141923e`）
加 5 個 **2026-07-25 實測活**的 feed 進 `DEFAULT_SOURCES`（並 upsert 進使用者現有 db）：
- OpenAI Blog（官方）· TechCrunch AI · The Verge AI（即時產業/產品新聞）
- Hacker News AI 搜尋 · Reddit r/LocalLLaMA（社群發布與心得，以 `blog` 類收錄）
- **否決/擱置**：Anthropic 無官方 RSS（404）；Reddit r/singularity 間歇 429。這類靠 HN／新聞源／
  live web 補。
- 代價：社群源雜訊高 → 靠興趣過濾/排序把關；每次 digest 多抓幾個源（可接受）。

## ② promote live web 活水 → vision 階段 13（根治）
擴名冊只是加更多**固定**源；根治是**伸手到名冊之外**——把 web 搜尋接進每日 digest。
- **決策**：`WebSearchAdapter`（實作 `SourceAdapter.fetch`）對「AI 最新」query 跑 `WebSearch.search`
  → 映成 `Item` → 交**既有 digest 管線**（去重/排序/消化）。零改管線。
- **opt-in 預設停用**＋需金鑰（控成本、原則 5 主權）；web 進的是**流非種子**（種子只經「收進」）。
- **三面對齊**：根公理（discovery 根治痛點）；concept 反濾泡/驚訝力第 3 層；原則 3 溯源、原則 5
  主權；教訓 1（stub 可測）/3（失敗→missing_sources）/8（源＝表一列，零 schema）。

## 其他路線（否決）
- 每次 digest 無條件自動搜：成本失控 → opt-in 預設停用。
- web 結果直接當種子：違原則 5、污染 KB → 只當流、收進才留。
- 硬抓 Threads/X：無公開 API、成本/合規問題 → 用 HN/Reddit 當社群代理＋live web。

## 出口
- 趨勢 draft live 活水段轉 in-flight（階段 13）；draft 不刪。
- 下一步：`/speckit-specify` 開 spec 015。驗收見 vision 階段 13。
