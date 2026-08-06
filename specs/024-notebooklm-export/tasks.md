# 任務清單：匯出給 NotebookLM（複製 Markdown＋複製佐證網址）

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`024-notebooklm-export`

TDD 強制：先寫紅測（Red）→ 實作轉綠（Green）。**核心零新相依、無新表、只讀既有 `conversations`／`why_nodes`**。formatter 純函式（primitives 進、字串／清單出）為可測核心。

---

## Phase 1：Setup

- [X] T001 建 `src/knowfield/export/` 套件：`__init__.py`＋`notebooklm.py` 骨架（4 函式簽名 `conversation_to_markdown`／`conversation_evidence_urls`／`why_node_to_markdown`／`dedup_urls`，先 `pass`／回空，讓測試可 import）。

## Phase 2：Foundational（跨三頁共用 UI infra，阻塞各頁鈕）

- [X] T002 [P] 在 `src/knowfield/web/templates/base.html` 加共用 `copyExport(url, opts)`＋toast：`fetch`（GET 或帶 body 的 POST）取 `text` → `navigator.clipboard.writeText` → 顯示「已複製，可貼進 NotebookLM」；`as=urls` 空 → 提示「（無佐證網址）」；複製/抓取失敗 → 明確繁中提示、不靜默（FR-004、教訓 3）。複用既有 clipboard 慣例。

**檢查點**：共用複製助手就緒，三頁鈕可掛。

---

## Phase 3：US1（P1）——對話 → Markdown（核心價值）

- [X] T003 [P] [US1] 在 `tests/unit/test_export_notebooklm.py` 寫 `conversation_to_markdown` 紅測：多則 user/assistant＋含來源 → 標題、「**你：**／**副手：**」標示、內文保留行內 `[n]`、**每則來源塊接在該則之後**（`- [n] 標題 — url`）；空 messages → 只標題；缺 `content` → 空字串不崩；缺 title → 「（未命名對話）」；缺 source 標題 → 用 url。
- [X] T004 [US1] 在 `src/knowfield/export/notebooklm.py` 實作 `conversation_to_markdown(title, messages)`。跑 T003 轉綠。
- [X] T005 [P] [US1] 在 `tests/unit/test_export_web.py` 寫端點紅測（`as=md`）：`POST /chat/export`（帶 `history` JSON）回 `text/plain` 的對話 Markdown；`GET /conversations/{cid}/export?as=md` 存在→回 Markdown、不存在→404。（注入測試用 repo／factory，沿用既有 web 測慣例。）
- [X] T006 [US1] 在 `src/knowfield/web/app.py` 加 `POST /chat/export`（`_parse_history`→formatter，`PlainTextResponse`）＋`GET /conversations/{cid}/export`（`repo.get_conversation`；404）——先接 `as=md` 分支。跑 T005 轉綠。
- [X] T007 [US1] `chat.html`（送出區）＋`conversation.html`（標題列）各加「📋 複製 Markdown」鈕，接 `copyExport`（chat 帶 `history_json`＋POST；conversation 走 GET）。

**檢查點**：`/chat`、`/conversations/{id}` 皆能一鍵複製乾淨對話 Markdown（貼 NotebookLM 文字來源可讀）。

---

## Phase 4：US2（P2）——對話 → 佐證網址清單

- [X] T008 [P] [US2] 在 `test_export_notebooklm.py` 寫 `conversation_evidence_urls`＋`dedup_urls` 紅測：跨全訊息收集來源 url、**去重保序**；跨訊息重複只留一；缺 url 的 source 略過；無來源 → `[]`。
- [X] T009 [US2] 實作 `conversation_evidence_urls(messages)`＋`dedup_urls(urls)`。跑 T008 轉綠。
- [X] T010 [P] [US2] 在 `test_export_web.py` 寫 `as=urls` 紅測：`POST /chat/export?as=urls`、`GET /conversations/{cid}/export?as=urls` 回**每行一個 url、去重**的 `text/plain`；無來源 → 空。
- [X] T011 [US2] `app.py` 兩端點加 `as=urls` 分支（`"\n".join(conversation_evidence_urls(msgs))`）。跑 T010 轉綠。
- [X] T012 [US2] `chat.html`＋`conversation.html` 各加「🔗 複製佐證網址」鈕，接 `copyExport(..., as=urls)`。

**檢查點**：同兩頁皆能一鍵複製去重佐證網址清單（貼 NotebookLM URL 來源）。

---

## Phase 5：US3（P3）——根因匯出（Markdown＋網址）

- [X] T013 [P] [US3] 在 `test_export_notebooklm.py` 寫 `why_node_to_markdown` 紅測：主張 `# {claim}`＋「## 為何（階梯…）」數字列表＋「## 佐證」清單；空 ladder／空 evidence → 略過該段；空 claim → 「（未命名根因）」。
- [X] T014 [US3] 實作 `why_node_to_markdown(claim, ladder, evidence_urls)`。跑 T013 轉綠。
- [X] T015 [P] [US3] 在 `test_export_web.py` 寫 `GET /roots/{wid}/export?as=md|urls` 紅測：自 `list_why_nodes` 取 `id==wid`；md→根因 Markdown、urls→`dedup_urls(evidence_urls)` 每行一個；不存在 wid→404。
- [X] T016 [US3] `app.py` 加 `GET /roots/{wid}/export`（md／urls 分支，`text/plain`）。跑 T015 轉綠。
- [X] T017 [US3] `roots.html` 每條根因加「📋 複製 Markdown」＋「🔗 複製佐證網址」兩顆鈕（帶 `w.id`），接 `copyExport`。

**檢查點**：`/roots` 每條根因能一鍵匯出主張＋階梯＋佐證／佐證網址。

---

## Phase 6：Polish＋唯讀守衛＋回歸

- [X] T018 [P] 寫**唯讀守衛**紅測（核心，原則 6）：呼叫各匯出端點後，`conversations`／`why_nodes` 內容不變、且存過含發想內容的對話後匯出，`build_field_system_prompt` 產物**不因匯出而變**（場脈絡只來自冊封根因）。FR-006／SC-004。
- [X] T019 全繁中檢查（鈕文字／提示）＋範圍守住（**無**下載 `.md` 檔／LLM 蒸餾 brief／直推 NotebookLM API／對話全文搜尋／CLI）。
- [X] T020 跑 `uv run pytest tests/unit/test_export_notebooklm.py tests/unit/test_export_web.py -q` 全綠；再 `uv run pytest -q` 全綠（現 368 ＋ 本增量新測），既有路由零回歸。

---

## 依賴與平行

- **Setup（T001）→ Foundational（T002）→ US1→US2→US3→Polish**。US 間大致獨立（各自的純函式＋端點分支＋鈕），但共用同兩個端點（`/chat/export`、`/conversations/{cid}/export`）與 `copyExport`，故同檔任務循序、跨檔 `[P]` 可平行（紅測多可 `[P]`）。
- **MVP＝US1**（對話→Markdown）：單獨即可交付「把場的蒸餾內容帶進 NotebookLM」的核心價值。
- 每個 US 完成即為可獨立展示的增量。
