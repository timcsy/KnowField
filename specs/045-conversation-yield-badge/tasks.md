# Tasks：對話清單的由來徽章讀對欄位（spec 045）

- [ ] T001 `tests/unit/test_conversation_yield.py` —— **先紅**
      ① 有 2 條核心理解指向的對話 → count=2
      ② 沒有指向的 → 0
      ③ ⚠️ **走 `promote_conversation` 那條路**（冊封的真實路徑）也算得到
         —— 這條是缺陷的本體：舊做法在這條路上永遠是 0
      ④ ⚠️ **查詢次數不隨對話數增長**（假 conn 數 execute）
- [ ] T002 `repository.conversation_yield_counts() -> dict[int,int]`（一次 GROUP BY）
- [ ] T003 ⚠️ 反向攻擊：改成逐筆查詢，確認 ④ 轉紅
- [ ] T004 `tests/contract/test_conversations_yield.py`：`/api/conversations` 帶 `yield_count`；
      ⚠️ 其餘欄位逐字不變（比對寫死的鍵集合）
- [ ] T005 `app.py`：`/api/conversations` 用它
- [ ] T006 前端：`ConversationsPage.tsx`／`ConversationSidebar.tsx` 徽章改讀 `yield_count`，帶數量
- [ ] T007 `uv run pytest -q` ＋ `npm run build` ＋ `npm run test -- --run` 綠
- [ ] T008 真跑：本機看徽章；⚠️ **部署後對正式庫驗 SC-001（要 ＝ 12，不是 4）**
- [ ] T009 反流 → 出貨（`ship-knowfield`）
