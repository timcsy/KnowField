# 任務清單：對話收料的漏——去重＋收尾缺口提醒

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`025-capture-hygiene`

TDD 強制：先紅後綠。**核心零新相依**；唯一結構變更＝`why_nodes` 加 `conversation_id` 欄（冪等 migrate、回填、不破 spec 023）。純核心 `chat/capture.py`（指紋＋判準）為可測基石。

---

## Phase 1：Setup／Schema

- [X] T001 `src/learnnews/store/schema.py`：`SCHEMA` 的 `why_nodes` 加 `conversation_id INTEGER`（可空）；`_migrate` 冪等——`PRAGMA table_info(why_nodes)` 無此欄則 `ALTER TABLE why_nodes ADD COLUMN conversation_id INTEGER`，並**回填**（既有 `conversations.why_node_id` → 對應 `why_nodes.conversation_id`，既有「← 由來」不斷）。回填只在欄新加時做一次、冪等。

## Phase 2：Foundational（純核心，阻塞 US1＋US2）

- [X] T002 [P] `tests/unit/test_capture_core.py` 寫 `conversation_fingerprint` 紅測：同內容→同指紋；順序/內容不同→不同；空 messages→穩定空指紋；缺 `content` 不崩；**忽略 sources**（同 role/content、sources 不同 → 同指紋）。
- [X] T003 [P] `tests/unit/test_capture_core.py` 寫 `distill_gap` 紅測：`total>=min_total 且 total-last_captured>=gap` → 回 `(last_captured+1, total)`；短（total<min_total）→None；剛收滿（gap 不足）→None；`last_captured` 負/None 視為 0；`total<=0`→None；邊界值明確。
- [X] T004 建 `src/learnnews/chat/capture.py`：實作 `conversation_fingerprint(messages)`（stdlib `hashlib`，取 role＋content）＋`distill_gap(total, last_captured, min_total, gap_threshold)`。跑 T002/T003 轉綠。

**檢查點**：指紋與收尾判準純函式、離線可測、缺項不崩。

---

## Phase 3：US1（P1）——去重：同段多根因共用一份

- [X] T005 [P] [US1] `tests/unit/test_capture_hygiene_web.py` 寫去重紅測：同一段 history 連 3 次 `POST /chat/anoint`（`save_convo=1`，各不同 claim）→ `list_conversations` **只增 1**、3 條根因 `why_node_provenance` 皆映**同一 cid**；換**不同**内容的 history 再 anoint→ 產生**第二份**（不誤併）；`save_convo` 未給 → 存檔數**不增**。
- [X] T006 [P] [US1] 寫 **spec 023 不回歸**紅測：`save_conversation(title, messages, wid)` → `why_node_provenance()[wid]==cid`；`delete_why_node(wid)` → provenance 不再含 wid、但該對話仍在 `list_conversations`（不孤兒）。
- [X] T007 [US1] `src/learnnews/store/repository.py`：`save_conversation` 改**指紋冪等**（`conversation_fingerprint`；同指紋回既有 cid、不插入）＋若給 `why_node_id` 設 `why_nodes[wid].conversation_id=cid`；`why_node_provenance` 改讀 `why_nodes.conversation_id`（JOIN conversations，僅含仍存在的 cid、多條可映同一 cid）；`delete_why_node` 沿用（連結隨列消）。跑 T005/T006 轉綠。

**檢查點**：同段冊封 N 條只留一份、N 條連同一；異段不誤併；spec 023 行為不回歸。

---

## Phase 4：US2（P2）——收尾缺口提醒

- [X] T008 [P] [US2] `tests/unit/test_capture_hygiene_web.py` 寫提醒紅測：`POST /chat`（或 render 路徑）帶**長** history＋**小** `last_captured` → 回應頁面**含**「尾段未收」提醒（標區間）；`last_captured` 接近 total 或 history 短 → **無**提醒；顯示提醒**不新增** `why_nodes`（不自動冊封，守衛）。
- [X] T009 [US2] `src/learnnews/web/app.py`：chat render（`chat_post`／resume／get）算 `distill_gap(len(messages), last_captured, MIN, GAP)`（門檻設定一處、可調）傳入 context；`chat.html` 加「尾段未收」提醒區塊（標區間、可點既有『整理成重點』入口、可忽略）＋隱藏欄 `last_captured`（JS 從 localStorage 讀）＋按整理/存/冊封時把 localStorage 更新為當前訊息數＋串流完成後客端以同門檻再評估。跑 T008 轉綠。

**檢查點**：長且尾段未收→提醒；短/剛收→不吵；提醒只提醒、不自動收。

---

## Phase 5：Polish＋守衛＋回歸

- [X] T010 [P] 寫**唯讀/人閘門守衛**紅測（原則 5/6）：`save_conversation` 同段呼叫兩次 → 只 1 份、且**既有列不被刪改**（第一份 id 不變、messages 不變）；看 chat 頁與去重流程皆**不新增** `why_nodes`（不自動冊封）。
- [X] T011 全繁中檢查（提醒/鈕文案）＋範圍守住（**無** #3 章節切分/落點重命名、**無**既有 15 份複本清理遷移、**無**對話全文搜尋/跨對話關聯、**無** CLI）。
- [X] T012 跑 `uv run pytest tests/unit/test_capture_core.py tests/unit/test_capture_hygiene_web.py -q` 全綠；再 `uv run pytest -q` 全綠（現 393 ＋ 本增量）；驗 `_migrate` 冪等（既有 db 重跑不重複回填）、既有 spec 023 存檔仍可讀。

---

## 依賴與平行

- **Schema（T001）→ 純核心（T002-T004）→ US1（T005-T007）→ US2（T008-T009）→ Polish**。
- US1 與 US2 皆依賴純核心；US1（去重，改 repo）與 US2（提醒，改 web/前端）**改不同檔、可並行推進**（紅測 `[P]`）。
- **MVP＝US1**（去重）：使用者指定先做、堵住既成囤積 bug、最便宜。
- 每個 US 完成即可獨立展示。
