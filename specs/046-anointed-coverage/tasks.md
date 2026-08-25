# Tasks：對話裡看得見冊封狀態（spec 046 · 階段 41）

- [X] T001 `tests/unit/test_conversation_anointed.py` —— **先紅**
      `conversation_referrers` 帶回 `src_from/src_to`；沒範圍的回 0/0；不影響既有 `{id, claim}` 鍵
- [X] T002 `repository.conversation_referrers` 加兩欄（既有鍵不動）
- [X] T003 `tests/contract/test_conversation_anointed.py` —— **先紅**
      `/api/conversations/{cid}` 回 `anointed`；`referrers` 等既有欄位**逐字不變**
- [X] T004 `app.py`：詳情路由回 `anointed`
- [X] T005 `frontend/src/lib/coverage.ts` ＋ `__tests__`：`coveredSet(ranges) -> Set<number>` —— **先紅**
      ⚠️ 測試 MUST 含一個**中間的洞**（9–26 ＋ 31–44 → 27–30 未收）：
      **水位線實作會通過沒有洞的測試**，那條測試就沒有牙齒（SC-002）
- [X] T006 ⚠️ 反向攻擊：把 `coveredSet` 換成水位線（`1..max(to)`），確認 T005 轉紅
- [X] T007 `ChatPage.tsx`：逐則標覆蓋 ＋ 頂部摘要（「46 則中 40 則已收，6 則還沒」）；
      沒範圍的冊封只在摘要層級講（FR-003）
- [X] T008 `ChatPage.tsx`：候選卡改為可編輯（主張 `<Input>` ＋ 層次按鈕），沿用來源頁形狀；
      `anointOne` 送**改過的**值
- [X] T009 `tests/contract/`：改過文字 → 新增一條；相同文字 → 不新增（釘住 FR-006/007，
      擋日後被「順手」改成 upsert）
- [X] T010 `uv run pytest -q` ＋ `npm run build` ＋ `npm run test -- --run` 綠
- [X] T011 ⚠️ 真跑：開對話 #44（46 則、缺 3–8），確認那 6 則標為未收；改一條候選文字再收
- [X] T012 反流 → 出貨（`ship-knowfield`）


## 真跑（2026-08-25，本機）

⚠️ 本機沒有帶範圍的資料 → 在**本機 dev 沙盒**種一份與正式庫同形狀的（對話 20，60 則，
刻意留洞 [3–8]）。經**真實 proxy** 驗：

- 頂部摘要：「**60 則中 54 則已收（左側有線），還有 6 則沒收**」——講集合大小，不講水位線
- 第一章（第 1–8 則）逐則檢查：`1:已收 2:已收 3~8:未收` ✅ **洞看得見**
- 候選卡可改主張與層次；改過的值有送出（`anointOne` 送 `edits[i]`）

⚠️ **過程中我犯了 `run-knowfield` skill 第 2 步明文警告的錯**：vite 起在 **5178**
（5173–5177 被別的專案佔著），我卻假設 5173，打到了別人的伺服器拿到 404。
skill 早就寫著「**讀它印出來的 port，別假設 5173**」——我沒讀就用。
