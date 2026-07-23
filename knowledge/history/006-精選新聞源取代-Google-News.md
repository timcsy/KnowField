# 006：精選 AI 新聞源取代 Google News
> 日期：2026-07-23

## 轉移
- 舊（005）：新聞源＝Google News：AI RSS（通用搜尋，訊噪比低）。
- 新：新聞源＝**Import AI（Jack Clark 策展）＋ Last Week in AI（策展）**——兩個 AI 專門
  策展電子報，皆 Substack RSS、免金鑰、穩定。Google News 移除。

## 為什麼變
005 的 Google News 是通用新聞搜尋，雜訊多（政治、財經、非 AI 內容混入），違背根公理
「跟上趨勢的成本要極低」——使用者還得自己濾雜訊。改用**研究早已點名**的策展電子報
（見 `draft/2026-07-23-競品地貌與差異化.md`），訊噪比高、且與 spec「少量精選新聞」的
來源決策一致。

## 為什麼是這兩個
實測九個候選 RSS：Import AI、Last Week in AI、HF blog、BAIR、MIT Tech Review、
Ars Technica、The Gradient、DeepMind blog 皆可用；The Batch 404。選 Import AI ＋
Last Week in AI 因為**最貼「AI 新聞策展」**（週報式彙整，而非單篇），訊噪比最高。
其餘（MIT/Ars/DeepMind…）留給使用者按需自行 `sources add`（主權在使用者，憲章原則 VI）。

## 影響
- 真跑驗證：`missing_sources` 空；新聞與論文**真實混合**進匯整——「AI 政策治理」興趣
  拉出 Import AI 的政策議題（核能 LLM、網路戰、電子戰），純論文給不了。**廣度差異化
  首次展現實際價值**。
- 為長文新聞加 embedding 輸入截斷（2000 字）省成本。
- commit 見下方；程式碼 `src/learnnews/cli/fetchers.py`。

## 待續
Import AI／Last Week in AI 為**週報**，單日可能無新內容（論文源補足每日新鮮度）。
若要更即時的產業新聞，可再加 Ars Technica AI 等日更源。

## 狀態
✅ 已採用（取代 005 的 Google News）
