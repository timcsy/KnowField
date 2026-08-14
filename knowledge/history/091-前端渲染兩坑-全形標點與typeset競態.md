# 091：兩個前端渲染坑——全形標點破 CommonMark flanking、typeset 時機競態

> 日期：2026-08-09。commits `9c3352e`、`7aaa310`。兩個都在 `frontend/src/components/Markdown.tsx`。
> 由來：上線後真實使用（承 `history/088`／`089`）——使用者讀到 AI 回覆時看到**露出的 `**` 星號**、
> 以及**偶爾整段數學卡成 raw LaTeX**。

## 一、中文粗體 `**…**` 露星號：CommonMark 的 flanking 規則對 CJK 系統性失效

**現象**：大部分粗體正常，但像「…完整。**真正…」這種**閉合 `**` 前面是全形句號**的，星號原封吐出來。

**根因**：CommonMark 判斷一個 `**` 能不能**閉合**（right-flanking）的規則是——
前面不是空白，且（前面不是標點 **或** 後面接空白/標點）。中文命中雙重詛咒：
- 全形句號 `。` 被歸類為 **punctuation** → 觸發第二個條件；
- 中文**不用空格分詞** → `**` 後面接的是「真」這種字元，既非空白也非標點 → 條件不成立。
- ∴ 該 `**` 不算合法閉合 → marked 原樣輸出星號。

英文寫作幾乎不會撞（`.` 後面通常是空格）。**這是規範本身以英文書寫慣例為預設所造成的盲區，不是 marked 的 bug。**

**修法**：不跟規範辯論，**繞過它**——在丟給 marked 之前先把 `**…**` 手動抽成 `@@B{n}@@` 佔位，
marked 跑完再還原成 `<strong>`（內容 `escHtml`）。順序講究：**數學 `@@M` 先抽、最後才還原**，
所以「粗體內含數學」也不壞。

**這招不是第一次用**：`store/db.py` 的 SQL 佔位符統一、OCR 的 `![img-N]` 佔位、`@@M` 數學佔位——
**「抽佔位 → 交給不可靠/不合用的處理器 → 還原」已經是這個庫的常備手法**。
（也已被 `draft/2026-08-10-來源翻譯與對照` 預定用來保護翻譯時的數學/程式碼。）

## 二、數學偶發不渲染：`大部分正常、有時跳走` ＝ 時機競態的簽名

**現象**：MathJax 有時沒把 `.mathcopy` 裡的 LaTeX 渲染掉，卡成原始文字；重整就好；不穩定重現。

**根因**：`scheduleTypeset` 是**全域 debounce** —— 一次 `setTimeout` 觸發整頁 typeset。但 DOM 是**陸續晚到**的：
MathJax 還在載、圖片 reflow、串流換節點、長對話的訊息陸續 mount。晚到的那些在那次 typeset **之後**才進 DOM；
而 timer 又被別處的 `clearTimeout` 取消 → 沒有第二次機會 → 永遠卡著。

**修法：兜底重跑抓漏網**——typeset 完成後標記 `data-typeset`，再查 DOM 裡有沒有
`.mathcopy:not([data-typeset])`（＝漏網）；有就 400ms 後再跑，最多 4 次。
**成立的前提是 `typesetPromise` 對已渲染是 no-op ⇒ 重跑無害**（冪等才敢重試）。

## 三、兩坑的共通形狀（why 值得一起記）

兩個修法表面不同，骨架一樣：**別信任上游會替你做對，自己驗結果**。
- flanking：不信 marked 處理得了 CJK → 抽走自己來。
- typeset：不信「我呼叫過 typeset 了」→ **查 DOM 裡還有沒有 raw**，有就再跑。

後者是這個專案骨幹「**別信自報的綠、驗 ground truth**」的第三次投影：
① 跨連線驗 DB 寫入（`history/084`）② 驗 pod 實際 digest 而非 rollout log（`history/089`）
③ 驗 DOM 實際渲染狀態而非「我觸發過」（本篇）。**驗結果，不驗『我做了那個動作』。**

## 四、留下的小債

`tests/unit/test_api_chat.py::test_stream_bare_skips_search` 的註解仍寫「腦力激盪不撒網」——
`988cdd2`（`history/090`）改名時漏改的陳舊註解，非功能問題。
