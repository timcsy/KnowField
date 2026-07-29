# Data Model：對話的「由來」存檔

**新增一張表 `conversations`**（第一個落庫的對話產物）。其餘沿用。

## 新表 `conversations`
| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | INTEGER PK | |
| `title` | TEXT | 自動「由來」標題（一句摘要） |
| `messages` | TEXT（JSON） | 整段訊息序列（role/content/sources） |
| `why_node_id` | INTEGER（可空） | 連到的核心理解（冊封時連同存）；無 FK 約束（刪根因不崩，D3） |
| `created_at` | TEXT | 建立時間 |

## 新實體 `Conversation`（記憶體）
| 欄位 | 型別 |
|------|------|
| `id` | int |
| `title` | str |
| `messages` | list[dict]（role/content/sources） |
| `why_node_id` | int \| None |
| `created_at` | str |

## 沿用（不變）
- `why_nodes`（已冊封根因）——本層讓它**可被連到**（一對可選連結，從 conversations 側指過去）。
- `build_field_system_prompt(roots)`——**只吃已冊封根因**，不碰 conversations（守純度，不改）。

## 契約摘要
- `save_conversation(title, messages, why_node_id=None) -> int`
- `list_conversations() -> list[Conversation]`（新到舊）
- `get_conversation(cid) -> Conversation | None`
- `why_node_provenance() -> dict[int, int]`（{why_node_id: conversation_id}，供 /roots 由來連結）
- `FieldChat.title(messages) -> str`（自動由來標題；失敗退回）
