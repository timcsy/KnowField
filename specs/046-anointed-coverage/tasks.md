# Tasks：對話裡看得見冊封狀態（spec 046 · 階段 41）

- [ ] T001 `tests/unit/test_conversation_anointed.py` —— **先紅**
      `conversation_referrers` 帶回 `src_from/src_to`；沒範圍的回 0/0；不影響既有 `{id, claim}` 鍵
- [ ] T002 `repository.conversation_referrers` 加兩欄（既有鍵不動）
- [ ] T003 `tests/contract/test_conversation_anointed.py` —— **先紅**
      `/api/conversations/{cid}` 回 `anointed`；`referrers` 等既有欄位**逐字不變**
- [ ] T004 `app.py`：詳情路由回 `anointed`
- [ ] T005 `frontend/src/lib/coverage.ts` ＋ `__tests__`：`coveredSet(ranges) -> Set<number>` —— **先紅**
      ⚠️ 測試 MUST 含一個**中間的洞**（9–26 ＋ 31–44 → 27–30 未收）：
      **水位線實作會通過沒有洞的測試**，那條測試就沒有牙齒（SC-002）
- [ ] T006 ⚠️ 反向攻擊：把 `coveredSet` 換成水位線（`1..max(to)`），確認 T005 轉紅
- [ ] T007 `ChatPage.tsx`：逐則標覆蓋 ＋ 頂部摘要（「46 則中 40 則已收，6 則還沒」）；
      沒範圍的冊封只在摘要層級講（FR-003）
- [ ] T008 `ChatPage.tsx`：候選卡改為可編輯（主張 `<Input>` ＋ 層次按鈕），沿用來源頁形狀；
      `anointOne` 送**改過的**值
- [ ] T009 `tests/contract/`：改過文字 → 新增一條；相同文字 → 不新增（釘住 FR-006/007，
      擋日後被「順手」改成 upsert）
- [ ] T010 `uv run pytest -q` ＋ `npm run build` ＋ `npm run test -- --run` 綠
- [ ] T011 ⚠️ 真跑：開對話 #44（46 則、缺 3–8），確認那 6 則標為未收；改一條候選文字再收
- [ ] T012 反流 → 出貨（`ship-knowfield`）
