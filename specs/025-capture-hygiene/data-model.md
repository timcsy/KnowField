# Data Model: 對話收料的漏

## 結構變更（唯一）：`why_nodes` 加一欄
- `why_nodes.conversation_id INTEGER`（可空，無 FK）——該根因的「由來」對話。多條根因可**共用同一 cid**。
- `SCHEMA` 的 `why_nodes` 加此欄；`_migrate` 冪等：`PRAGMA table_info` 無此欄則 `ALTER TABLE ADD COLUMN`，
  並**回填**——把既有 `conversations.why_node_id` 對應到 `why_nodes[wid].conversation_id`（既有「← 由來」不斷）。
- **不新增表**；`conversations` 表不動（`why_node_id` 欄保留為歷史相容、首作者記錄，不再是事實來源）。

## 衍生值（不落庫）
- **內容指紋** `conversation_fingerprint(messages) -> str`：訊息序列（role＋content，忽略 sources 等易變欄）
  的穩定雜湊。純函式。用於去重識別「同一段」。
- **收尾缺口** `distill_gap(total, last_captured, min_total, gap_threshold) -> None | (from, to)`：純值，不落庫。

## 既有實體（沿用）
- **對話 Conversation**（spec 023）：id/title/messages/why_node_id(歷史)/created_at。
- **根因 WhyNode**：加 `conversation_id`。其餘不變。
- **provenance**：`{wid: cid}`——**改由 `why_nodes.conversation_id` 產生**（多條可映到同一 cid）。

## 不變量
- **去重只加不刪**：`save_conversation` 冪等——同指紋回既有 id，不插入、不刪改既有列。
- **多對一**：多條根因 `conversation_id` 可相同；一份對話服務多條根因。
- **刪根因不孤兒**：`delete_why_node` 清該根因（含其 conversation_id 連結）；對話列仍在、其他根因連結不動。
- **人閘門**：提醒與去重皆不自動冊封、不自動存全部（原則 5）。
