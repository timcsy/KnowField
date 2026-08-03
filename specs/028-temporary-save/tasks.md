# 任務清單：對話暫時存檔（自動、TTL 衰減）＋永久存檔（人閘門）

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`028-temporary-save`

TDD 強制：先紅後綠。**核心零新相依**；conversations 加 `temporary`＋`last_activity_at`（冪等 migrate、回填既有=永久）。純核心 `expired_temp_ids`／`cheap_title` 為基石。優先序 US1（自動暫存）＋US2（TTL 衰減）皆 P1、US3（升永久）P2。

---

## Phase 1：Setup／Schema

- [X] T001 `src/learnnews/store/schema.py`：`conversations` 的 `SCHEMA` 加 `temporary INTEGER DEFAULT 0`＋`last_activity_at TEXT`；`_migrate` 冪等——`PRAGMA table_info(conversations)` 無欄則 `ALTER TABLE ADD COLUMN`，並**回填**既有列（`temporary=0`、`last_activity_at=created_at`）。`models/__init__.py` 的 `Conversation` 加 `temporary`、`last_activity_at`；`repository._row_to_conversation`／`list_conversations`／`get_conversation` 帶新欄。

## Phase 2：Foundational（純核心，阻塞 US1/US2）

- [X] T002 [P] `tests/unit/test_capture_core.py` 擴 `expired_temp_ids` 紅測：過期暫存選中／未過期不選／`temporary=0` 永久不選／剛好 7 天邊界／last_activity 更新後不選（計時重設）／缺或壞時間保守不選。
- [X] T003 [P] `tests/unit/test_capture_core.py` 擴 `cheap_title` 紅測：取首個 user 訊息截斷（≤20）；空→「（暫存對話）」；缺 content 不崩。
- [X] T004 `src/learnnews/chat/capture.py`：實作 `expired_temp_ids(convos, now, ttl_days=7)`（stdlib datetime parse/比較）＋`cheap_title(messages)`。跑 T002/T003 轉綠。

**檢查點**：TTL 判準與便宜標題純函式、離線可測、缺項保守不誤刪。

---

## Phase 3：US1（P1）——自動暫存（一筆 upsert）

- [X] T005 [P] [US1] `tests/unit/test_temp_save_web.py` 寫 autosave 紅測：連 3 次 `POST /chat/autosave`（同 temp_id）→ `list_conversations` **只 1 筆**（temporary=1、messages 更新為最新）；空 history→不存、無 temp_id；autosave 產生的 temp_id 回傳給 client。
- [X] T006 [US1] `repository.py` 加 `autosave_temporary(temp_id, messages, now)`（空→None；temp_id 存在→UPDATE messages＋last_activity；否則 INSERT temporary=1＋`cheap_title`）＋`touch_conversation(cid, now)`；`app.py` 加 `POST /chat/autosave`（回 temp_id、best-effort）。跑 T005 轉綠。
- [X] T007 [US1] `chat.html`：串流 `done` 後 best-effort `fetch('/chat/autosave')`（帶 history＋temp_id）、把回傳 temp_id 記 hidden 欄＋localStorage；autosave 失敗**不擋聊天**（catch 靜默）。

**檢查點**：每輪自動存一筆、可 upsert、失敗不擋、空不存、temp_id 記得住。

---

## Phase 4：US2（P1）——TTL 衰減（懶清）

- [X] T008 [P] [US2] `test_temp_save_web.py` 寫懶清紅測：種一筆過期暫存（last_activity 8 天前）＋一筆永久＋一筆新暫存 → `GET /conversations` 後 **過期暫存被刪、永久與新暫存都在**；`purge` 只刪過期暫存。
- [X] T009 [US2] `repository.py` 加 `purge_expired_temporary(now, ttl_days=7)`（`list_conversations`→`expired_temp_ids`→DELETE、回數）；`app.py` 的 `GET /conversations` 與存檔動作先呼叫它（懶清、**不開背景排程**）。跑 T008 轉綠。

**檢查點**：閒置 >7 天暫存被清、永久零誤刪、計時可重設、無背景工作。

---

## Phase 5：US3（P2）——升永久＋分區 UI＋接回

- [X] T010 [P] [US3] `test_temp_save_web.py` 寫升永久紅測：autosave 得 temp_id → `POST /chat/save`(temp_id) → 同筆 `temporary=0`＋落點標題（注入 title_factory）、`list_conversations` **不新增**；`POST /conversations/{id}/promote` 同效；冊封連同存(temp_id)→ 該筆永久＋連根因（provenance）。
- [X] T011 [P] [US3] 寫**不注入回場守衛**紅測（原則 6）：`autosave_temporary`(含 SECRET_FANTASY) → 之後 `POST /chat`（spy backend）system prompt **不含**該暫存內容（比照 spec 023）。
- [X] T012 [US3] `repository.py` 加 `promote_conversation(cid, title=None, why_node_id=None)`（UPDATE temporary=0＋title＋wid）；`app.py`：`/chat/save`＋`/chat/anoint`(save_convo) 收 `temp_id`→有則 promote（生 title_factory 落點標題）、無則退回既有 save_conversation；加 `POST /conversations/{cid}/promote`；`/conversations/{cid}/resume` touch＋帶回 temp_id。跑 T010/T011 轉綠。
- [X] T013 [US3] `conversations.html` 分「永久」「暫存（會自動清除）」兩區、暫存每筆「轉永久」鈕；`chat.html`＋`app.py`：`/chat` 載入若有最近暫存→「上次還沒存的對話還在，接回嗎？」橫幅（連 resume）。

**檢查點**：升永久同一筆＋落點標題不重複、冊封連同存=永久、分區顯示、可接回、暫存不注入回場。

---

## Phase 6：Polish＋回歸

- [X] T014 [P] 全繁中檢查（橫幅/分區/鈕文案）＋範圍守住（**無**背景排程、**無**暫存自動 LLM 標題、**無**跨對話關聯/全文搜尋、**無** CLI）＋既有 spec 023 存檔升級後=永久、provenance/dedupe（025/026）零回歸。
- [X] T015 跑 `uv run pytest tests/unit/test_capture_core.py tests/unit/test_temp_save_web.py -q` 全綠；再 `uv run pytest -q` 全綠（現 441 ＋ 本增量）；驗 `_migrate` 冪等（既有 db 重跑不重複回填、既有存檔=永久）。

---

## 依賴與平行

- **Schema（T001）→ 純核心（T002-T004）→ US1 自動暫存（T005-T007）→ US2 懶清（T008-T009）→ US3 升永久/UI（T010-T013）→ Polish**。
- US1 與 US2 皆依純核心；US1（autosave repo/前端）與 US2（purge repo/路由）改不同處、可並行。
- **MVP＝US1＋US2**（自動存＋自動流走是一體：解損失又不囤積）；US3 升永久為加值。
- 紅測多可 `[P]`。
