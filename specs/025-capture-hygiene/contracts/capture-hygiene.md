# Contracts: 對話收料的漏

## A. 純核心（`src/knowfield/chat/capture.py`，零相依）

### `conversation_fingerprint(messages: list) -> str`
- 由訊息序列（每則 `role`＋`content`，忽略 sources 等易變欄）算穩定雜湊字串（stdlib `hashlib`）。
- 同內容 → 同指紋；順序/內容不同 → 不同。空 messages → 穩定的空指紋。缺 `content` 視為空、不崩。

### `distill_gap(total: int, last_captured: int, min_total: int, gap_threshold: int) -> tuple[int,int] | None`
- 回 `(from, to)`＝`(last_captured+1, total)` 當 `total >= min_total` 且 `total - last_captured >= gap_threshold`；
  否則 `None`。`last_captured` 為負/None 視為 0；`total<=0` → `None`。純函式、不崩。

## B. Repository 契約（`src/knowfield/store/repository.py`）

### `save_conversation(title, messages, why_node_id=None) -> int`（改為指紋冪等）
- 算 `conversation_fingerprint(messages)`；若已有同指紋對話 → 取其 `cid`（**不插入**）；否則插入新列得 `cid`。
- 若 `why_node_id` 給定 → 設 `why_nodes[why_node_id].conversation_id = cid`。
- 回 `cid`。**不刪改既有列**。

### `why_node_provenance() -> dict`（改讀 why_node 側）
- 回 `{wid: cid}`，來源＝`why_nodes` 中 `conversation_id` 非空、且該 cid 對話仍存在者。多條可映同一 cid。

### `delete_why_node(wid) -> bool`（沿用＋清連結）
- 刪根因；其 `conversation_id` 連結隨列消失。對話列與其他根因連結不受影響。

### schema `_migrate`（冪等）
- `why_nodes` 無 `conversation_id` → `ALTER TABLE ADD COLUMN`；回填既有 `conversations.why_node_id`。

## C. Web 契約（`src/knowfield/web/app.py`＋`chat.html`）

- **#1 去重**：`/chat/anoint`（`save_convo=1`）沿用呼叫 `save_conversation` → **自動去重**（前端零改）。
- **#2 提醒**：chat 頁以 `distill_gap` 判斷是否顯示「尾段未收」提醒；`last_captured` 由 client（localStorage
  記「上次按整理/冊封時訊息數」）提供；顯示時標區間、可點既有「整理成重點」入口、可忽略。**不自動冊封**。
- 全繁中；提醒文案如「自上次整理後又聊了一段（約第 N–M 句）還沒收，要不要現在整理？」。

## D. 測試契約

- **單元**（`test_capture_core.py`）：`conversation_fingerprint`（同/異/空/缺欄位/忽略 sources）；
  `distill_gap`（長且未收→區間、短→None、剛收滿→None、邊界、負/None last_captured）。
- **web**（`test_capture_hygiene_web.py`）：
  - 同段連 3 次 anoint（save_convo）→ `list_conversations` 只增 1、3 條根因 provenance 皆同一 cid。
  - 異段各 anoint → 兩份不誤併；單獨冊封（不連同存）→ 存檔不增。
  - **spec 023 不回歸**：save_conversation(t,m,wid)→provenance[wid]==cid；刪根因→provenance 無它、對話仍在。
  - 提醒：長且尾段未收 → 頁面出現提醒；短 → 無。**守衛**：提醒/去重皆不自動冊封（why_nodes 數不因看頁/去重而增）。
