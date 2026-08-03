# Contracts: 對話暫時存檔＋TTL 衰減

## A. 純核心（`src/learnnews/chat/capture.py`，零相依）

### `expired_temp_ids(convos: list, now: str, ttl_days: int = 7) -> list[int]`
- `convos` 每筆 dict/物件含 `id/temporary/last_activity_at`。回 `temporary` 為真且 `now - last_activity_at > ttl_days`
  的 id。時間 parse 失敗/缺 → **不選**（保守、不誤刪）。純函式、離線可測。

### `cheap_title(messages: list) -> str`
- 首個 user 訊息截斷（≤20 字）；空→「（暫存對話）」。純、不呼 LLM。

## B. Repository（`src/learnnews/store/repository.py`）

### `autosave_temporary(temp_id, messages, now) -> int | None`
- 空 messages → None（不存）。`temp_id` 給定且存在 → `UPDATE messages, last_activity_at=now`（同筆）→ 回 temp_id；
  否則 INSERT（temporary=1、`cheap_title`、last_activity=now、created_at=now）→ 回新 id。

### `touch_conversation(cid, now) -> bool`
- `UPDATE last_activity_at=now WHERE id=cid`（接回時重設計時）。

### `promote_conversation(cid, title=None, why_node_id=None) -> bool`
- `UPDATE temporary=0`（＋title、＋why_node_id 若給）。人按才呼叫。

### `purge_expired_temporary(now, ttl_days=7) -> int`
- 取 `list_conversations()` → `expired_temp_ids` → `DELETE`。回刪除數。**只刪過期暫存**。

### `list_conversations()` / `get_conversation()` / `Conversation`（改）
- 帶 `temporary`、`last_activity_at`。（`save_conversation` 維持 spec 025 dedup、temporary=0＝永久。）

## C. Web（`src/learnnews/web/app.py`＋模板）
- `POST /chat/autosave`（Form: `history`、`temp_id?`）→ `autosave_temporary` → 回 `temp_id`（純文字/JSON）。best-effort。
- `/chat/save`：有 `temp_id` → `promote_conversation(temp_id, 落點標題)`；無 → `save_conversation`（建永久）。先 purge。
- `/chat/anoint`（save_convo）：有 `temp_id` → promote 該筆＋連 wid；無 → 既有 save_conversation(…, wid)。
- `POST /conversations/{cid}/promote` → `promote_conversation(cid, 落點標題)`（「轉永久」鈕）。
- `/conversations`：先 `purge_expired_temporary(now)`；模板分「永久／暫存（會自動清除）」；帶「最近暫存」給 `/chat` 接回橫幅。
- `/conversations/{cid}/resume`：`touch_conversation`（重設計時）＋帶回 `temp_id`（續聊 autosave 更新同筆）。
- `chat.html`：串流 `done` 後 best-effort `fetch('/chat/autosave')`、把回傳 `temp_id` 記 hidden＋localStorage；載入若有暫存→接回橫幅。

## D. 測試契約
- **單元**（`test_capture_core.py` 擴）：`expired_temp_ids`（過期選中/未過期不選/永久不選/邊界剛好 7 天/計時重設後不選/缺時間不選）；`cheap_title`（首句/空）。
- **web**（`test_temp_save_web.py`）：
  - autosave：連 3 輪 → **只 1 筆**暫存（upsert）、messages 更新；空 history→不存；temp_id 帶回。best-effort（factory 失敗不 500 給前端流程）。
  - 懶清：種過期暫存＋永久 → 載 `/conversations` 後**過期暫存被刪、永久仍在**。
  - 升永久：autosave 得 temp_id → `/chat/save`(temp_id) → 同筆 `temporary=0`＋落點標題、`list_conversations` **不新增**；冊封連同存(temp_id)→該筆永久＋連根因。
  - 守衛：存含 SECRET_FANTASY 的**暫存**後，新 `/chat` system prompt 不含它（不注入回場）。
  - 既有 spec 023 存檔升級後＝永久（temporary=0）、provenance 不回歸。
