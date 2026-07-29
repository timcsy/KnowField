# Research: 對話的可找回性

## D1：標題「凍在第一句」的成因＝取材截頭
- **事實**：`FieldChat.title` 餵 `convo = "\n".join(...)[:2000]`——70 句 129k 字的對話，`[:2000]` 只涵蓋**開頭數輪**，
  故標題永遠反映開頭主題（＝19 份全叫「Flow Matching」的機械成因）。
- **決定**：抽純函式 `title_material(messages, head_chars, tail_chars)`＝**首段＋尾段並取**（尾段為主，因落點在尾）；
  提示改為「描述這段對話**最後得出／聊到什麼（落點）**與整體在講什麼，當標題」。
- **可測**：`title_material` 純函式——測「尾段內容有進取材」（開頭 A 大量＋結尾 B → 取材含 B）。LLM 部分注入 stub。
- **駁回**：全對話丟給 LLM——長對話成本高、且截斷問題只是搬家；首尾並取足夠點出落點、成本可控。

## D2：章節切分＝可注入 segment＋純正規化，且不落庫
- **決定**：`FieldChat.segment(messages) -> list[章節]`（backend 判語意轉折）＋`_parse_chapters(text)`＋純函式
  `normalize_chapters(raw, n_messages)`：把 LLM 給的粗範圍**clamp 到 [1,n]、排序、補洞、去重疊**，保證涵蓋全對話不重疊；
  空/過短/失敗→**整段一章**（教訓 3）。stub backend 回確定性章節→離線可測。
- **不落庫**：`POST /conversations/{cid}/segment` 即時算、渲染大綱（跳讀錨點），**不寫表、可重算**。
- **理由（原則 6 過度擬合守）**：章節切分較投機——先做**輕量、on-demand、可注入**版本驗有沒有用；有用再談進化，
  沒用直接廢、**零結構債**。落庫/版本是「還沒驗到 payoff 就先蓋重的」＝過度抽象，排除。

## D3：每章動作＝range 切片複用既有
- **決定**：`conversation_export` 加 `from/to`（`messages[from-1:to]` 再走 spec 024 匯出）；
  「整理這章」`POST /conversations/{cid}/distill?from=&to=`→切片→`distill_factory`→既有候選/冊封頁（人閘門）。
- **理由**：章節就是「訊息範圍」——每章動作＝對切片套既有匯出/整理，最省、複用最大化。

## D4：重命名＝UPDATE title，人閘門
- **決定**：`rename_conversation(cid, title)`（UPDATE）；`POST .../rename`（手動輸入）＋`POST .../retitle`（重生自動標題）。
  **不自動改既有**——人按才改（原則 5）。標題失敗退首句（教訓 3）。
- **理由**：改名是既有欄位更新、最小變更（教訓 8）；重生＝對既有 messages 重跑改好的 title。

## 未解問題
- 具體 head/tail 字數與門檻於實作定、封在純函式；切分演算法不綁定（交注入後端）。無 NEEDS CLARIFICATION。
