# Research：反逢迎的「值不值得」副手

無 NEEDS CLARIFICATION——手動探針即參考實作。記關鍵抉擇。

## D1：不套 SmartSearch 全管線（更輕）
- **決策**：新建精簡 `assess_worth`：多角度搜 → 用結果標題/摘要當證據 → 綜合。**不**逐則抓內文、
  **不**嵌入排序。
- **理由**：手動探針證明——心得證據就在**搜尋結果的摘要裡**（HN 反應、早期實測、CodeRabbit 評測都是
  WebSearch 直接回的摘要，沒抓任何一頁）。逐則抓內文昂貴又常被擋（見 D3），對本用途不划算。
- **否決**：複用 SmartSearch（搜→抓 top-N→整理）——多餘的抓取步驟、多數評測頁會擋，且嵌入排序
  對「獵心得」無幫助。棄。

## D2：獵心得 query 用模板、不用 LLM 擴展
- **決策**：`worthit_queries(subject)` 是**確定性模板**（心得/評價、review reddit、vs 缺點 complaints、
  值得嗎 limitations、怎麼用 how to use），不走 `expand.py` 的 LLM。
- **理由**：手動探針的好 query 就是這幾個固定角度；模板**確定性、離線可測、零 LLM 成本/延遲**，
  且 query 品質穩定（LLM 擴展反而可能飄）。價值在**綜合**那段 LLM，不在 query。
- **否決**：LLM 生成 query（expand.py）——不確定、增延遲/成本，對固定角度無增益。棄（YAGNI）。

## D3：收內容口＋主題識別（抓不到不阻斷）
- **決策**：路由收 name／content／url；subject 解析序＝name ＞ content 首行 ＞ url 抓到的標題 ＞ url。
  伺服器 `fetch_url` 抓＝best-effort、包 try/except。
- **理由**：探針 WebFetch 抓 iThome 吃 403、牆內（FB/Threads）更抓不到。**關鍵洞察**：真正的價值來自
  「撒網搜心得」，網頁內文只是拿來認主題——**只要有 subject 字串就能跑**。收內容口讓牆內也送得進來。
- **否決**：強制要能抓到網頁才跑——會讓一大半真實情境（牆內/被擋）直接失敗。棄。

## D4：反逢迎綜合＝新 prompt，不複用 RAG answerer
- **決策**：新 `WorthItSynthesizer`（Stub＋OpenAI），反逢迎 `_SYSTEM`（三層分開、明說炒作、grounded、
  沒料說沒料）。
- **理由**：既有 `make_answerer` 的 `_SYSTEM` 是 RAG 問答式，語氣/結構不對；反逢迎綜合要的是「分官方/
  獨立/用戶、標炒作、給裁決」——不同工作。沿用 `_post`／注入／stub **模式**，但 prompt 專寫。
- **否決**：硬套 answerer.answer(question, passages)——passages 是 CorpusEntry、prompt 是問答式，扭曲。棄。

## D5：不落庫（原則 5）
- 待判物/心得/綜合皆短暫、呈現用；不寫任何庫（收進成種子是設計 B 後續，非本 spec）。
