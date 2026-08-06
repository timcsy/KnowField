# 任務清單：對話的可找回性——落點重命名＋章節切分

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`027-conversation-recall`

TDD 強制：先紅後綠。**核心零新相依、無新表**（US1 只 UPDATE title；章節不落庫）。純核心 `title_material`／`normalize_chapters` 為基石；語意層 title/segment 可注入。優先序 US1（MVP，真解找不回）＞US2＞US3。

---

## Phase 1：Foundational（純核心，阻塞 US1/US2）

- [X] T001 [P] `tests/unit/test_capture_core.py` 擴 `title_material` 紅測：開頭大量「A」＋結尾「B」→ 取材**含 B**（尾段有進，不只開頭）；空 messages→空字串；缺 content 不崩。
- [X] T002 [P] `tests/unit/test_capture_core.py` 擴 `normalize_chapters` 紅測：粗/越界/亂序/重疊 raw → clamp 到 [1,n]、排序、補洞去重疊、**涵蓋 [1,n] 不重疊**；空/壞 raw 且 n≥1→整段一章；n≤0→[]。
- [X] T002b `src/knowfield/chat/capture.py`：實作 `title_material(messages, head_chars=600, tail_chars=1600)`＋`normalize_chapters(raw, n_messages)`。跑 T001/T002 轉綠。

**檢查點**：取材含尾段、章節正規化涵蓋不重疊、缺項不崩。

---

## Phase 2：US1（P1）——落點重命名（MVP，真解找不回）

- [X] T003 [P] [US1] `tests/unit/test_recall_web.py` 寫紅測：注入 `title_factory` 回「落點B」→ `POST /chat/save`（開頭A落點B）後 `list_conversations` 標題含 B；`POST /conversations/{id}/rename`（title=新名）→ 標題改為新名；`POST /conversations/{id}/retitle`→ 重生標題；title_factory 拋例外→存檔仍成功、退回不崩；`GET /conversations/{id}` 檢視**不改**標題（不自動）。
- [X] T004 [US1] `src/knowfield/chat/field_chat.py`：`title()` 改用 `title_material`＋落點提示（「描述最後得出/聊到什麼與整體」）；`src/knowfield/store/repository.py` 加 `rename_conversation(cid, title)->bool`；`src/knowfield/web/app.py` 加 `POST /conversations/{cid}/rename`＋`POST /conversations/{cid}/retitle`（用 title_factory）。跑 T003 轉綠。
- [X] T005 [US1] `conversation.html` 加改名欄＋「重新命名」鈕；`conversations.html` 每則加行內改名（送 rename）。

**檢查點**：新標題反映落點、可手動改名、既有可重生、失敗退回、不自動改。

---

## Phase 3：US2（P2）——章節切分（on-demand、不落庫）

- [X] T006 [P] [US2] `tests/unit/test_field_chat.py`（或 test_recall_web）寫 `segment` 紅測：注入 stub backend 回 2 章文字 → `FieldChat.segment(messages)` 回 2 章（各含 title/start/end/summary、經 normalize 涵蓋不重疊）；backend 拋例外/對話過短 → 整段一章、不崩。
- [X] T007 [P] [US2] `test_recall_web.py` 寫切章渲染紅測：注入 `segment_factory` 回 2 章 → `POST /conversations/{id}/segment` → 頁面含 2 章小標＋跳讀錨點（第 N–M 句）；且 `get_conversation` 的 title/messages **未因 segment 改變**（不落庫守衛）。
- [X] T008 [US2] `field_chat.py` 加 `segment(messages)`（backend＋`_parse_chapters`＋`normalize_chapters`＋失敗退整段）；`app.py` 加 `app.state.segment_factory`（預設 `FieldChat.segment` with make_chat_backend）＋`POST /conversations/{cid}/segment`（算章節、渲染大綱）；`conversation.html` 加「整理成章節」＋章節大綱（每章小標/範圍/摘要＋跳讀錨點連結）。跑 T006/T007 轉綠。

**檢查點**：切出小標＋範圍＋摘要、可跳讀、涵蓋不重疊、可注入、退回不崩、不落庫。

---

## Phase 4：US3（P3）——每章匯出／整理

- [X] T009 [P] [US3] `test_recall_web.py` 寫每章動作紅測：`GET /conversations/{id}/export?as=md&from=N&to=M` 只含該章訊息（範圍外不在）；`POST /conversations/{id}/distill?from=N&to=M`→ 出候選但 `list_why_nodes` **不增**（不自動冊封，人閘門）。
- [X] T010 [US3] `app.py`：`conversation_export` 加 `from/to`（切 `messages[from-1:to]` 再走既有匯出）；加 `POST /conversations/{cid}/distill`（切片→`distill_factory`→渲染候選頁）；`conversation.html` 每章加「📋 複製 Markdown／🔗 佐證網址（該章）」＋「整理這章成重點」。跑 T009 轉綠。

**檢查點**：每章單獨匯出只含該章；整理這章走既有冊封流、不自動冊封。

---

## Phase 5：Polish＋回歸

- [X] T011 [P] 全繁中檢查（鈕/大綱/提示）＋範圍守住（**無**自動切分/自動命名、**無**章節落庫/版本、**無**跨對話關聯/全文搜尋、**無** CLI）＋人閘門守衛（改名/切分/整理皆人按、不自動）。
- [X] T012 跑 `uv run pytest tests/unit/test_capture_core.py tests/unit/test_recall_web.py -q` 全綠；再 `uv run pytest -q` 全綠（現 423 ＋ 本增量）；既有 spec 022/023/024/025/026 零回歸。

---

## 依賴與平行

- **純核心（T001-T002b）→ US1（T003-T005）→ US2（T006-T008）→ US3（T009-T010）→ Polish**。三 US 皆依純核心；US1 改 title/repo，US2 加 segment，US3 擴匯出/distill——大致改不同處。
- **MVP＝US1**（重命名）：單獨即解核心痛點「找不回」。US2/US3 為增量。
- 紅測多可 `[P]`。
