# 063：匯出給 NotebookLM 完成（階段 19）

> 日期：2026-07-29。承接 history/062（/chat 真實使用打磨）。spec 024 出貨。

## 由來（為何做這個）
使用者用了 `/chat` 後回饋「會一直想用」，接著問：**這樣不會跟 NotebookLM 很重疊嗎？** 這一問逼出一個
**定位判斷**，比功能本身更重要——記一筆。

## 關鍵決策：不競爭，接力（護城河 × 商品分工）
- **各做強項**：這工具的護城河＝**膜／蒸餾**（不順著你、從 bedrock 推、守純度）；NotebookLM 的強項＝
  **打磨過的輸出**（audio overview／study guide）。**不重蓋 audio**（巨大工程、它做得好），**匯出讓它接力**。
- **膜不是硬技術護城河**——NotebookLM 要加批判模式技術上做得到；差別是**設計哲學**（大眾貼心助手結構上
  不願說「你錯了」）。故定位＝「**共用表面、不同種類**」，非「更好的 NotebookLM」。
- **這是一個可複用的模式**：自己做**差異化的難的部分**，**匯出**讓商品工具做其擅長的其餘（別重蓋商品）。

## 關鍵設計判斷
1. **匯出兩種料、對應兩種吃法**：**蒸餾內容**（貼文字來源＝真價值，NotebookLM 抓不到、活在本機的場）
   ＋**佐證網址**（當 URL 來源、它自己抓，但會踩 403，當附帶）。誠實判準（膜）：**只給網址＝降成書籤
   匯出器、丟了蒸餾**——內容為主、網址為輔。使用者定案：兩顆都要。
2. **來源逐訊息塊、非全域底部清單**：對地面事實查核——來源**逐 assistant 訊息各自從 `[1]` 編號**
   （conversation.html per-message `data-src-prefix`；`_default_chat` 每輪重編）。壓成全域清單會**跨訊息
   撞號**、行內 `[n]` 對不上。故 Markdown 把來源塊接在該則後。（修正 spec「底部來源清單」措辭。）
   ＝**又一次「實作前先查地面事實、別照抽象直覺蓋」**。
3. **最快做到＝純前端複製、零後端**，但**可測核心留在後端純函式**：資料已在頁面，本可全 JS 組裝，但那樣
   **沒有可測 Python 核心**（違 TDD）。折衷＝純 formatter 放後端（primitives 進、離線可測）＋端點回
   `text/plain`＋前端 `fetch→clipboard`。三頁單一機制、單一事實來源。

## 產物
- 純模組 `src/knowfield/export/notebooklm.py`（4 函式：`conversation_to_markdown`／
  `conversation_evidence_urls`／`why_node_to_markdown`／`dedup_urls`，零相依）。
- app.py 3 端點：`POST /chat/export`、`GET /conversations/{cid}/export`、`GET /roots/{wid}/export`
  （`as=md|urls`、`PlainTextResponse`、404 友善）。
- base.html 共用 `copyExport`/`showToast`；chat/conversation/roots 三頁各兩顆鈕。
- 測試：`test_export_notebooklm.py`（15）＋`test_export_web.py`（10，含**唯讀守衛**：匯出後 DB 不變、
  `build_field_system_prompt` 不含發想內容）。368→393。commit `c240795`。

## 教訓再釘
- **零外部相依的功能，離線測即完整驗證**——本階段無 LLM／網路，不像前幾階段需真後端再驗；照實說「無真
  後端待驗」，不硬套流程。
- **原則 6 純度用 code＋守衛測釘住**：匯出只把沉澱物**出**，不把外物**入**；formatter 純函式天然無副作用、
  端點唯讀，守衛測證場脈絡不受匯出影響。
- **定位問題（重疊嗎）用膜答**：不防禦性否認重疊，誠實承認共用表面、指出真差異（膜＋roots-as-bedrock＋
  純度）、並劃界（膜非硬技術護城河、audio 該讓 NotebookLM 做）——最後用「接力＋匯出」把它變成互補。
