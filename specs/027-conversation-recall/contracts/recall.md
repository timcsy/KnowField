# Contracts: 對話的可找回性

## A. 純核心（`src/learnnews/chat/capture.py`，零相依）

### `title_material(messages: list, head_chars=600, tail_chars=1600) -> str`
- 回「首段＋尾段」取材字串（尾段為主、標出落點）。空→空字串。缺 content 視為空、不崩。
- 保證：長對話的**尾段內容有進取材**（不再只看開頭）。

### `normalize_chapters(raw: list, n_messages: int) -> list[dict]`
- 把 raw（`[{title,start,end,summary}]`，範圍可能粗/越界/重疊）→ clamp 到 `[1,n]`、依 start 排序、補洞去重疊，
  保證**涵蓋 [1,n] 且不重疊**。空/壞/`n<=0` → 合理退回（`n>=1` 時整段一章；`n<=0` 回 `[]`）。純函式。

## B. 語意層（`src/learnnews/chat/field_chat.py`，可注入 backend）

### `FieldChat.title(messages) -> str`（改）
- 用 `title_material` 取材＋落點提示。失敗→退回首個 user 訊息截斷（教訓 3）。

### `FieldChat.segment(messages) -> list[dict]`（新）
- backend 判語意轉折→`_parse_chapters`→`normalize_chapters`。失敗/過短→整段一章。回章節清單。

## C. Repository（`src/learnnews/store/repository.py`）
### `rename_conversation(cid, title) -> bool`
- `UPDATE conversations SET title=? WHERE id=?`；回是否有更新。不碰其他欄。

## D. Web（`src/learnnews/web/app.py`＋模板）
- `POST /conversations/{cid}/rename`（Form `title`）→ `rename_conversation`→ redirect。空標題→不改、友善。
- `POST /conversations/{cid}/retitle` → 對 conv.messages 跑 `title_factory`→ rename → redirect。
- `POST /conversations/{cid}/segment` → `segment_factory(conv.messages)`→ 渲染 conversation.html 帶章節大綱（跳讀錨點）。
- `GET /conversations/{cid}/export?as=&from=&to=` → 切 `messages[from-1:to]` 再走既有 `_export_conversation`（spec 024）。
- `POST /conversations/{cid}/distill?from=&to=` → 切片→`distill_factory`→ 渲染候選（複用 chat.html 候選/冊封，人閘門）。
- 注入點：`app.state.segment_factory`（預設 `FieldChat.segment`）。
- `conversation.html`：改名欄＋「重新命名」＋「整理成章節」＋章節大綱（每章：小標/範圍/摘要＋跳讀＋複製 md/網址＋整理這章）。
- `conversations.html`：每則加行內改名。

## E. 測試契約
- **單元**（`test_capture_core.py` 擴）：`title_material`（尾段有進、空/缺不崩）；`normalize_chapters`（涵蓋/不重疊/clamp 越界/排序/空→整段一章/n<=0→[]）。
- **web**（`test_recall_web.py`）：
  - US1：注入 title 回「落點B」→ 存檔/重生後標題含 B；`POST rename` 改成使用者輸入；標題 factory 拋錯→退回不崩；不自動改既有（GET 檢視不改標題）。
  - US2：注入 segment 回 2 章→ `POST segment` 頁面顯示章節小標＋跳讀錨點；segment 拋錯→整段一章不崩；章節不落庫（DB title/messages 不因 segment 變）。
  - US3：`GET export?from=&to=` 只含該章訊息；`POST distill?from=&to=` 出候選但**不自動冊封**（why_nodes 不增）。
