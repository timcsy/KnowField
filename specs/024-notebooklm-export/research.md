# Research: 匯出給 NotebookLM

## D1：formatter 放哪？——新純模組 vs repository/web

- **決定**：新模組 `src/knowfield/export/notebooklm.py`，函式收**基本型別**（不 import models/repository）。
- **理由**：核心要「離線可單測、零相依、失敗不崩」。把組裝邏輯自 DB／web 抽離＝可測性最高、耦合最低；符合教訓 1（離線 stub 可測）、憲章 IV。放 repository 會綁 DB／dataclass、放 web 會綁 request，都較難純測。
- **駁回**：純前端 JS 組裝——最省後端，但**沒有可測 Python 核心**、違 TDD 與「可測純 formatter」需求；且三頁會各寫一份 JS 組裝、易漂移。

## D2：來源呈現——逐訊息塊 vs 單一全域底部清單

- **決定**：Markdown 把**每則 assistant 訊息的來源塊接在該則之後**；不做全域底部清單。
- **理由（對地面事實）**：現況來源**逐訊息各自編號** `[1..]`——`conversation.html:21` 每則用 `data-src-prefix="{{ p }}-src"`（`p='v'~loop.index`），`_default_chat` 每輪把 cited-only 來源從 `[1]` 重編。若壓成單一底部清單，行內 `[n]` 會**跨訊息撞號**、對不上。逐訊息塊才忠實。
- **影響**：spec FR-002／US1 措辭「底部來源清單」→ 實作為「逐訊息來源塊」（同一意圖、更正確）；已在 plan 記。

## D3：端點回傳型態與觸發——text/plain＋fetch→clipboard

- **決定**：3 端點回 `text/plain`；前端鈕 `fetch` 取文字後 `navigator.clipboard.writeText`＋toast。`/chat` POST（帶 `history`）、`/conversations/{cid}`／`/roots/{wid}` GET。
- **理由**：三頁**單一機制**、都經受測 formatter（單一事實來源）；複用 base.html 既有 clipboard 慣例（`navigator.clipboard.writeText`，見 base.html:80）。`/chat` 的 live history 只在前端 → 必須 POST 回來讓同一 formatter 處理（不在 JS 另組一份）。
- **駁回**：把已渲染頁面的字串塞進 `data-` 屬性、純前端讀取複製——省一次往返，但兩種機制（靜態頁 embed／chat fetch）並存、且 chat 仍需後端；統一走端點較簡單一致。
- **註**：`writeText` 於 fetch 後同一使用者手勢 async handler 內呼叫，現代瀏覽器允許；失敗 → 明確繁中提示（教訓 3、FR-004）。

## D4：佐證網址清單規則——去重、保序、每行一個

- **決定**：對話＝跨全訊息收集所有來源 URL、**去重保序**；根因＝其 `evidence_urls` 去重保序。回 `list[str]`，端點以 `\n` join。
- **理由**：NotebookLM 只需 URL 集合；保序讓輸出穩定可測。回 list 便於單測斷言，join 留給端點。無 URL → 空清單（端點回空字串或「（無佐證網址）」提示），不崩。

## D5：唯讀守衛——匯出不得污染場

- **決定**：匯出全程唯讀；加守衛測：呼叫任一匯出端點後，`conversations`／`why_nodes` 內容不變，且 `build_field_system_prompt` 產物不因匯出而變（場脈絡只來自冊封根因，spec 023 既有守衛延伸）。
- **理由**：原則 6（複利而不污染）——這層只把**已沉澱物匯出**，絕不把外物匯入或注入回對話。formatter 純函式天然無副作用；守衛測釘住「端點也不寫庫」。

## 未解問題

- 無。需求已定案（兩格式、三匯出點、純唯讀），無 NEEDS CLARIFICATION。
