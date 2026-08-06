# 081：來源進料的品質工程——arxiv 路線、數學/圖/標題的確定性修

> 日期：2026-08-07。**決策轉移＋墓碑**：記「為何 arxiv 走 HTML 不走 PDF」「為何結構問題用確定性修不丟 AI」，
> 免得半年後有人又改回去。設計家＝`draft/2026-08-04-進料轉檔選型.md`（它預言的坑，這裡修掉、閉環）。

## 起點
使用者用一陣子後回報收進的來源**不完整**（只抓到幾百字）、**沒圖**、**arxiv 數學跑版**、**標題分錯層次**。
一路修成「文字完整＋圖就位＋數學正確＋結構乾淨」，過程翻案數次（見下教訓）。

## 決策轉移：arxiv 收進路線 PDF-OCR → HTML →（fallback 鏈）
1. **原本**：arxiv 當一般 PDF 走 Mistral OCR（spec 030/`進料轉檔選型` 主路徑）。
2. **轉 HTML**：發現 OCR 端點**吐不出圖**（`include_image_base64` 回空、`pages` 被忽略——是 gateway 沒轉，非 Mistral 不支援）。改走 **arxiv HTML 版**（`arxiv.org/html/{id}`）：figure 是真 `<img>`、走既有 HTML 抽取＋圖片在地化。
3. **關鍵理由（墓碑，別改回 PDF）**：**HTML 的數學是作者原始 LaTeX（source）＝正確；PDF-OCR 是「看圖辨識 LaTeX」＝會猜錯。** 對數學/符號密集的論文，**解析 > 辨識**（見 experience 同名教訓）。HTML 還免費、快、確定性。
4. **fallback 鏈**：`arxiv/html → ar5iv → PDF-OCR`，全部**存回正規 /abs**（由來/去重穩定）。有 HTML 用 HTML、舊論文沒有退 ar5iv、再沒有才 PDF。（`arxiv_urls`／`ingest_url`／`ingest_pdf(store_url=)`）
5. **PDF 這條沒廢、反而補強**：使用者**自己改了 gateway** 讓 OCR 回 `image_base64`（完整 data URI）＋支援 `pages`。於是**一般 PDF（非 arxiv、自上傳）的圖也能就位**——OCR 佔位 `![img-N](img-N)` 在正文對的位置→內嵌 data URI→`media.localize_images` 解碼存 `media/`、改寫 `/media`。arxiv 仍優先 HTML（數學更準），PDF 補「無 HTML 版/非 arxiv」那塊。

## 數學跑版：一個症狀、四層 bug（reflow 成 episode 級偵錯）
`|mathrm`、raw 公式、對齊散開——**逐層追出四個環環相扣**（`ea84263`）：
1. 抽取器把**行內數學連換行一起 emit** → 前端 `$` 配對**連鎖崩壞**（一條壞、後面全歪）。修：行內壓單行。
2. `chunk_markdown` 把**行內 `$..$` 按字數切半**、stitch 用空行接回 → 換行插進數學。修：切點不落在行內數學中（同 `$$`/code/表格的 atomic 精神——正是 `進料轉檔選型` C 節「公式塊不能從中間切」的**行內版補完**）。
3. `stitch_chunks` overlap 去重在**連續 `$$` 邊界誤刪分隔符**；且 arxiv LaTeXML 把**對齊式拆成多個置中 `$$`**。修：`_merge_math_blocks` 合併成單一 `\begin{aligned}`——**一石二鳥**（修對齊＋消連續 `$$`）。
4. 前端 `$..$` 正則禁換行 → 容許單一換行當防禦。

## 標題/字元：確定性修（不丟 AI）
- **標題分錯層次**（`進料轉檔選型` A 節早記「Mistral 標題階層不穩」，HTML 版亦然）：`_normalize_headings`＝移除跟標題重複的 heading＋剩下層級重映射「從 `##` 起連續、保留 nesting」。ycc 整篇 h3 起跳→提頂層、lilianweng 跟標題同級的 h1 sections→收到標題下、arxiv h2 起維持。
- **莫名其妙的符號**：`_clean_chars` 清零寬/BOM/軟連字/格式控制字元、NBSP→空白。
- **為何不丟 AI 整理**（使用者提議「仿貼上先給 AI 整理」）：貼上的 `clean_markdown` 鐵律本就是「**只剝雜訊、逐字保留、不改寫**」；但對 URL/PDF ①內容已結構抽取過、效益邊際 ②**AI 碰密集 LaTeX 很容易砸壞我們剛修好的數學**（承重內容）③成本＋損溯源。→ 結構問題**確定性修**、AI 只在真髒的貼上頁選用。（見 experience「確定性修承重內容 > 丟 AI」）

## 圖片在地化（跨 http 與 PDF）
`media.localize_images`：http 外連圖下載、PDF OCR 的 `data:image;base64` 解碼——都存 `media/`（內容雜湊命名、去重）、改寫 `/media`、**不進 embedding**（存短路徑）、抓不到 best-effort 保留外連。後端 mount `/media`（SPA catch-all 之前）。相對圖片 bug（只留絕對 URL→丟相對）也修了（`urljoin`）。

## 教訓（reflow 到 experience）
- **解析 > 辨識**（新）：有結構化 source 就別讓 AI 辨識。
- **確定性修承重內容 > 丟 AI**（新）：結構雜訊用規則、別讓 AI 碰數學。
- **先實測再斷言**（延伸既有「確定性≠直覺」）：本串至少三次假設錯——「抽取器太弱」（其實重抓就好）、「OCR 不支援 pages/圖」（其實 gateway 沒轉）、「stale cache 當成真 bug」。**每次都靠唯讀查真實 db／實測才翻案。**

## 產物
commits：`704a26f`（圖在地化）、`f3e3fa9`（arxiv HTML）、`ea84263`（數學四層）、`4cb6f72`（PDF 回圖）、
`0839609`（fallback 鏈）、`70a5d8d`（標題/字元）。全程唯讀診斷真實 `knowfield.db`＋臨時 db 實測、備份先行、324 測綠。
