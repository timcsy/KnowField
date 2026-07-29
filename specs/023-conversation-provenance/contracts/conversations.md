# 契約：對話的「由來」存檔（spec 023）

## repository（新）
- `save_conversation(title: str, messages: list, why_node_id: int|None=None) -> int`：落庫，回 id。純寫。
- `list_conversations() -> list[Conversation]`：新到舊。
- `get_conversation(cid: int) -> Conversation | None`。
- `why_node_provenance() -> dict[int, int]`：`{why_node_id: conversation_id}`（僅有連結者）。
- 刪 why_node（既有 `delete_why_node`）**不動 conversations**：對話仍在 list（獨立），/roots 不再連到（D3）。

## `FieldChat.title(messages) -> str`（新）
LLM 一句「由來」標題（≤20 字）；`StubChatBackend` 確定性（首個 user 訊息截斷）；失敗→退回首句/時間。

---

# 契約：web 路由（spec 023）

## `POST /chat/anoint`（擴充，人閘門）
- **既有**：claim/ladder/evidence_urls → `add_why_node`+`anoint`（回 wid）。**不變**。
- **新增輸入**：`save_convo`（"1"＝連同存）、`history`（JSON）。
- **行為**：冊封得 wid 後，若 `save_convo=="1"`：`title=title_factory(messages)`；
  `save_conversation(title, messages, wid)`。冊封仍是唯一寫 bedrock 路徑（原則 5）。

## `POST /chat/save`（新，獨立存）
- **輸入**：`history`（JSON）。
- **行為**：`messages=parse(history)`；空→友善不存；否則 `title=title_factory(messages)`；
  `save_conversation(title, messages, None)`；render chat.html 加 `saved_msg`。

## `GET /conversations`（新）
`list_conversations` → `conversations.html`（標題＋時間＋是否連著根因）。

## `GET /conversations/{cid}`（新）
`get_conversation` → `conversation.html`（用既有 `.md-render` 渲染整段；含各則來源）。

## `GET /roots`（擴充）
帶 `provenance = why_node_provenance()`；`roots.html` 每條 anointed 若 `w.id in provenance` →
「← 由來（對話）」連 `/conversations/{provenance[w.id]}`。

## 守純度（FR-004）
`conversations` **不被任何對話路徑讀進 `build_field_system_prompt`**；場脈絡只來自已冊封根因（不改）。
守衛測：存對話後，`/chat` 的 system prompt 不含該對話內容。

## 導覽
`base.html` 加「對話存檔」入口（→ `/conversations`）。
