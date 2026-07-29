# Research：跟你的場聊天

無 NEEDS CLARIFICATION——2026-07-29 現場示範即參考實作。記關鍵抉擇。

## D1：多輪 chat 抽象（不複用 answerer）
- **決策**：新 `ChatBackend.reply(messages)`（Stub＋OpenAI）；`_post` 直接吃 messages list。
- **理由**：既有 `make_answerer` 是一次性 RAG（`answer(question, passages, lang)`），語義是「對一問合成」，
  不是多輪對話。硬套會扭曲。沿用 `_post`／注入／stub **模式**，但抽象專為多輪。
- **否決**：把對話塞進 answerer 的 question——單輪、無脈絡累積，棄。

## D2：多輪狀態＝client 帶回 history（無 server session）
- **決策**：對話歷史存 `chat.html` 的 hidden field（JSON），每 POST 帶回，server append 後重繪。
- **理由**：stateless、無 session 狀態機、無新表——守 YAGNI（憲章 IV）。個人單使用者工具，不需並發 session。
- **否決**：server 端 session 存對話——多一套狀態管理與清理，個人工具不值得。棄。

## D3：冊封候選＝結構化 distill，不解析自由文字
- **決策**：對話回應是自由文（膜式，可在文中「建議冊封」）；**另有** `distill` 用結構化提示把對話蒸餾成
  `CandidateDraft(claim, ladder, evidence_urls)`，供人**審＋編輯**後按「冊封」。
- **理由**：從自由文字解析結構化候選很脆；分開「聊」與「提候選」→ 候選由專門的結構化呼叫產、可編輯、
  人閘門在兩處（要 distill＋按冊封）。robust 且守原則 5。
- **否決**：在對話文中用分隔符標候選、再 parse——版面一變就壞，脆。棄。

## D4：佐證按需、不自動每輪搜（原則/成本）
- **決策**：`/chat/cite` 由使用者對某主張觸發 → `make_web_search` 撒幾個佐證 query → 附引用；查無誠實說。
- **理由**：自動每輪搜昂貴且多數輪不需要；按需＝省成本、守「深淺分明」。與 /worth 的獵心得同源、更輕。
- **否決**：自動 tool-use 迴圈（LLM 每輪自決要不要搜）——複雜度大跳、成本不可控，MVP 不值得。棄（後續）。

## D5：永不自動改 bedrock（原則 5）
- 對話短暫、不落庫；**唯有人按「冊封」才** `add_why_node`+`anoint`。示範/想出聲的不自動收（呼應本次
  「這只是示範」的邊界）。膜 prompt 也明令「只提候選、冊封是人按」。
