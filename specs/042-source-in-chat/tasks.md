# Tasks：來源直接對話（spec 042 · 階段 38）

**TDD（憲章 I）**：每個測試任務先看紅燈。
⚠️ FR-003（不依賴撒網）與 FR-007（去重）是**沉默失效**型——寫對與根本沒接上在綠燈下長得一樣，
所以兩條都要**反向攻擊**（`experience.md`：沒被錯誤實作撞過的測試不知道自己在測什麼）。

## Phase 1：Foundational — 選段（純函式，好測）

- [ ] T001 `tests/unit/test_source_context.py`：`select_source_context()` 的性質 —— **先紅**
      ① 短來源＝全文、`excerpted=False`
      ② 長來源＝開頭 ＋ 命中段落，`excerpted=True`，且 `total_units`／`shown_units` 正確
      ③ ⚠️ **沒有任何一段是被硬切的**（每段都與某個原始塊逐字相等）
- [ ] T002 `src/knowfield/chat/source_context.py`：實作 `select_source_context(chunks, ranked_idx, cap, head)`
      —— 純函式，檢索名次由呼叫端算好傳進來（讓它零外呼可測）

## Phase 2：分層注入（field_chat）

- [ ] T003 `tests/unit/test_field_chat_source.py` —— **先紅**
      ① 帶 source → 脈絡含原文
      ② ⚠️ **source 不進 `history`**（脈絡衛生，沿用 041 的形狀）
      ③ bare → 不注入（FR-008）
      ④ 未帶 source → 訊息與現況**逐字相同**（FR-011／SC-007）
      ⑤ 節錄時脈絡**明講**「共 M 段、此處 j 段」（FR-005）
      ⑥ 脈絡明講「頁面上看到的可能是轉換後的版本，以下是原文」（FR-004）
- [ ] T004 `src/knowfield/chat/field_chat.py`：`_messages(..., source=None)` ＋ 一手素材層措辭；
      `reply`／`reply_stream` 透傳
- [ ] T005 ⚠️ 反向攻擊 T003④：故意在未帶 source 時多塞一則訊息，確認 ④ 由綠轉紅

## Phase 3：路由（US1 的本體）

- [ ] T006 `tests/contract/test_chat_source.py` —— **先紅**
      ① ⚠️ **撒網停用**時帶 `source_url`，模型仍收到該來源內容（FR-003／SC-002）
      ② ⚠️ 撒網也命中同一份時，脈絡中該來源**只出現一份**（FR-007／SC-005）
      ③ 來源不存在 → 安靜當作沒帶，不 5xx
      ④ 原文逐字不變（FR-009）
- [ ] T007 `src/knowfield/web/app.py`：`/chat/stream` 與 `/api/chat` 接 `source_url`；
      取原文 → 份內檢索 → `select_source_context` → 注入；撒網結果依 url 去重；記一行 log
- [ ] T008 ⚠️ 反向攻擊 T006①：把注入改成「只有撒網命中才注入」，確認 ① 轉紅
- [ ] T009 ⚠️ 反向攻擊 T006②：拿掉去重，確認 ② 轉紅

## Phase 4：前端（形狀沿用，零新控制項）

- [ ] T010 `frontend/src/lib/api.ts`：`streamChat` 帶 `source_url`
- [ ] T011 `frontend/src/ChatPage.tsx`：把 article 分支泛化成「帶入物」（文章／來源共用同一段呈現）；
      ⚠️ **不得**新增任何 041 沒有的控制項（FR-002／SC-006）
- [ ] T012 `frontend/src/pages/SourcePage.tsx`：一顆「💬 帶著這份聊」→ `/?source=<url>&stitle=<標題>`
- [ ] T013 `npm run build` 綠（⚠️ 用 `npm run build`，不是 `npx tsc --noEmit`——那兩者不同管線）

## Phase 5：驗收

- [ ] T014 `uv run pytest -q` 全綠（SC-008）
- [ ] T015 ⚠️ 瀏覽器真跑：來源頁 → 帶著這份聊 → 問一個**只有這份講過**的細節，看它答不答得出來；
      並比對呈現與文章版**無形狀差異**
- [ ] T016 反流（history／experience）→ push → 部署 k3s（核對 digest）
