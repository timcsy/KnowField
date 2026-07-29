# 任務清單：對話的「由來」存檔（episodes 層）

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`023-conversation-provenance`

TDD 強制：先寫紅測（Red）→ 實作轉綠（Green）。核心零新相依；一張新表（conversations，正當新實體）。

---

## Phase 1：Setup／Schema

- [X] T001 在 `src/learnnews/store/schema.py`：`SCHEMA` 加 `CREATE TABLE IF NOT EXISTS conversations`（id/title/messages JSON/why_node_id 可空/created_at）；`_migrate` 也加同一 `CREATE TABLE IF NOT EXISTS`（既有 DB 冪等補表，不動既有表）。

## Phase 2：Foundational（repository＋自動標題，阻塞路由）

- [X] T002 [P] 在 `tests/unit/test_conversations.py` 寫 repo 紅測：`save_conversation(title, messages, why_node_id)`→`list_conversations`（新到舊）／`get_conversation(id)` 取回 messages＋title＋why_node_id；`why_node_provenance()` 回 `{why_node_id: conversation_id}`（僅有連結者）。
- [X] T003 [P] 在 `tests/unit/test_conversations.py` 寫**刪根因不崩**紅測：冊封根因→save_conversation 連它→`delete_why_node(wid)`→該對話仍在 `list_conversations`（獨立）、`why_node_provenance` 不再含它、不崩（FR-007/D3）。
- [X] T004 建 `Conversation` dataclass（`models/__init__.py`）＋`src/learnnews/store/repository.py`：`save_conversation`／`list_conversations`／`get_conversation`／`why_node_provenance`。跑 T002/T003 轉綠。
- [X] T005 [P] 在 `tests/unit/test_field_chat.py` 寫 `FieldChat.title` 紅測：注入假 backend 回一句標題→得該標題；backend 拋例外→退回首個 user 訊息截斷/非空 fallback（不崩，教訓 3）。
- [X] T006 在 `src/learnnews/chat/field_chat.py` 加 `FieldChat.title(messages)->str`（一句摘要提示；失敗退回）。`StubChatBackend` 已有 reply→標題離線確定性。跑 T005 轉綠。

**檢查點**：對話可落庫/取回、provenance 對應、刪根因不崩、自動標題可退回；離線可測。

---

## Phase 3：US1+US2（P1）——兩存檔點

- [X] T007 [P] 在 `tests/contract/test_conversation_web.py` 寫**冊封時連同存**紅測：注入假 title_factory → `POST /chat/anoint`（claim/ladder＋`save_convo=1`＋`history`）→ 冊封一條根因＋存下一段對話**連到該根因**（`why_node_provenance` 有；`get_conversation` 取得整段）。`save_convo` 未給 → 只冊封、不存對話。
- [X] T008 [P] 寫**獨立存**紅測：`POST /chat/save`（history）→ `list_conversations` 多一段（why_node_id 空）、有自動標題；空 history → 友善不存（清單不增）。
- [X] T009 [US1] 在 `src/learnnews/web/app.py`：`app.state.title_factory`（預設 `FieldChat.title` with `make_chat_backend`）；`POST /chat/anoint` 擴充收 `save_convo`＋`history`（冊封得 wid 後，save_convo→存對話連 wid）。跑 T007 轉綠。
- [X] T010 [US2] 加 `POST /chat/save`（獨立存整段＋自動標題）；`chat.html` 送出區加「💾 存這段對話」＋冊封候選表單加「連同這段對話存成由來」checkbox＋hidden history。跑 T008 轉綠。

**檢查點**：兩存檔點都能存；冊封時連同存連得上根因；獨立存有標題。

---

## Phase 4：US3（P1）——查閱＋守純度

- [X] T011 [P] 寫**不入地基守衛**紅測（核心）：`save_conversation(含發想內容)` → 之後 `POST /chat`（spy backend）→ system prompt **不含**該對話內容（場脈絡只來自已冊封根因）。FR-004/SC-003。
- [X] T012 [P] 寫查閱紅測：`GET /conversations` 列出已存（標題/時間）；`GET /conversations/{id}` 回單篇含整段；`GET /roots` 對有由來的根因帶「← 由來」連結（provenance 注入頁）。
- [X] T013 [US3] 加 `GET /conversations`（清單）＋`GET /conversations/{id}`（單篇，`.md-render` 渲染）；`GET /roots` 帶 `why_node_provenance()`；建 `conversations.html`＋`conversation.html`；`roots.html` 加「← 由來」連結；`base.html` 導覽加「對話存檔」。跑 T011/T012 轉綠。

**檢查點**：根因→由來連得回；清單/單篇讀得到；存下的對話不進場脈絡（守純度）。

---

## Phase 5：US4＋Polish＋回歸

- [X] T014 [P] [US4] 寫友善紅測：title_factory 拋例外 → `/chat/save` 仍存成功（退回標題）、不噴 Traceback。
- [X] T015 跑 `uv run pytest tests/unit/test_conversations.py tests/contract/test_conversation_web.py -q` 全綠。
- [X] T016 跑 `uv run pytest -q` 全綠（現 348 + 本增量新測）；確認範圍守住（無自動存全部/注入回對話/全文搜尋/跨對話關聯/編輯-版本/CLI）。既有路由零回歸。
- [X] T017 真後端驗（若金鑰在）：重啟 server、`/chat` 聊一段→①獨立「存這段對話」看自動標題＋`/conversations` 讀得到；②冊封時連同存→`/roots` 該根因「← 由來」連得回。並確認新對話場脈絡不含存下的對話。

---

## 依賴與執行順序
- Schema（T001）→ Foundational（T002–T006）阻塞路由。T004 阻塞 T009/T010/T013。
- US1/US2（T007–T010）：兩存檔點，依 T004/T006。
- US3（T011–T013）：查閱＋守純度，依 T004。
- US4/Polish（T014–T017）最後。

## 平行機會
- T002‖T003‖T005；T007‖T008；T011‖T012；T014。
- 實作 T004（repo）、T006（chat）、T009/T010/T013（app＋模板）順序觸同批檔案，序執行。

## MVP
**T001–T013**＝兩存檔點＋自動標題＋根因由來連結＋查閱頁＋**不入地基守衛**。US4 友善為邊界，薄。
