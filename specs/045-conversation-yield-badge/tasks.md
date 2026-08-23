# Tasks：對話清單的由來徽章讀對欄位（spec 045）

- [X] T001 `tests/unit/test_conversation_yield.py` —— **先紅**
      ① 有 2 條核心理解指向的對話 → count=2
      ② 沒有指向的 → 0
      ③ ⚠️ **走 `promote_conversation` 那條路**（冊封的真實路徑）也算得到
         —— 這條是缺陷的本體：舊做法在這條路上永遠是 0
      ④ ⚠️ **查詢次數不隨對話數增長**（假 conn 數 execute）
- [X] T002 `repository.conversation_yield_counts() -> dict[int,int]`（一次 GROUP BY）
- [X] T003 ⚠️ 反向攻擊：改成逐筆查詢，確認 ④ 轉紅
- [X] T004 `tests/contract/test_conversations_yield.py`：`/api/conversations` 帶 `yield_count`；
      ⚠️ 其餘欄位逐字不變（比對寫死的鍵集合）
- [X] T005 `app.py`：`/api/conversations` 用它
- [X] T006 前端：`ConversationsPage.tsx`／`ConversationSidebar.tsx` 徽章改讀 `yield_count`，帶數量
- [X] T007 `uv run pytest -q` ＋ `npm run build` ＋ `npm run test -- --run` 綠
- [X] T008 真跑：本機看徽章；⚠️ **部署後對正式庫驗 SC-001（要 ＝ 12，不是 4）**
- [X] T009 反流 → 出貨（`ship-knowfield`）


## 真跑（2026-08-23，本機）

`/api/conversations` 經**真實 proxy**（5173 → 8001）取回：新徽章 5 段、舊做法 4 段。
其中 `#22 LLM可拆分，但模組不等於Agent`（`yield=1`、`why_node_id=None`）**本來完全看不見**。
畫面上 5 個徽章，帶著數量：15／6／2／1／1——那是布林值從來沒能傳達的資訊。

⚠️ 本機落差只有 5 vs 4，**正式庫才是 12 vs 4**（SC-001 要在部署後對正式庫驗）。
