# 實作計畫：對話的「由來」存檔（episodes 層）

**分支**：`023-conversation-provenance` ｜ **日期**：2026-07-29 ｜ **規格**：[spec.md](./spec.md)

## 摘要

新增 tool 的 episodes 層：兩個存檔點（冊封時連同存＋獨立存）把整段對話落庫、自動生「由來」標題、
`/roots` 每條核心理解連回它的由來對話、一個「存下的對話」清單/單篇頁。**守純度**：存下的對話唯讀、
**不進 `build_field_system_prompt`**（場脈絡只來自已冊封根因，既有行為不改）——寫守衛測釘死。

**第一個落庫的對話產物**：需一張新表 `conversations`（教訓 8 記一筆：這是正當的新實體）。其餘全複用
（冊封流不變、chat 後端生標題、既有 `/chat`＋`/roots` 頁擴充）。核心零新相依。

## Technical Context

**Language/Version**：Python 3.12+
**Primary Dependencies**：stdlib；web 層 FastAPI＋Jinja2（既有，不新增）
**Storage**：SQLite——**新表 `conversations`**（id/title/messages JSON/why_node_id 可空/created_at）
**Testing**：pytest（現 348 綠）
**Project Type**：web
**Constraints**：離線可注入替身可測；原則 5（人按才存）；原則 6（存下的對話不入地基）

## Constitution Check

| 原則 | 判定 | 理由 |
|------|------|------|
| I. TDD | ✅ | 先寫紅測（save/list/get、連同存連根因、自動標題退回、**不入地基守衛**、刪根因不崩）再實作 |
| II. 全繁中 | ✅ | 頁面、標題提示、訊息全繁中 |
| III. 規格驅動 | ✅ | spec 023→plan→tasks→impl，可追溯 FR |
| IV. 簡潔／YAGNI | ✅ | 核心零新相依；**一張新表**（正當：第一個落庫對話產物，教訓 8 記錄）；串既有 |
| V. 可觀測／錯誤處理 | ✅ | 自動標題失敗 `_log.error`＋退回時間/首句（教訓 3） |
| VI. 使用者決策主權 | ✅ | 原則 5：人按才存、不自動存全部；原則 6：存下的對話唯讀不入地基 |

**無違反；新表在複雜度追蹤記一筆（第一個落庫的對話產物）。**

## 技術方案

### 新表 `conversations`（schema.py SCHEMA ＋ _migrate 冪等）
```sql
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,                 -- 自動「由來」標題
    messages TEXT DEFAULT '[]', -- JSON：整段訊息（role/content/sources）
    why_node_id INTEGER,        -- 可空：連到的核心理解（冊封時連同存）
    created_at TEXT
);
```
既有 DB：`_migrate` 加 `CREATE TABLE IF NOT EXISTS conversations(...)`（不動既有表）。

### repository 新方法
- `save_conversation(title, messages: list, why_node_id=None) -> int`（純寫，人按才呼叫）。
- `list_conversations() -> list[Conversation]`（新到舊）。
- `get_conversation(cid) -> Conversation | None`。
- `why_node_provenance() -> dict[int, int]`（{why_node_id: conversation_id}，供 `/roots` 顯示由來連結）。
- **刪根因不崩**：`conversations.why_node_id` 不設 FK 約束；根因被刪 → 該對話仍在 `list_conversations`
  （自然變回「獨立存檔」），只是 `/roots` 不再連得到它。無孤兒崩壞（FR-007）。

### 自動標題 `FieldChat.title(messages) -> str`
一句摘要提示（≤20 字）；`StubChatBackend` 回確定性（首個 user 訊息截斷）；**失敗→退回首句/時間**（教訓 3）。

### Web 路由
- **`POST /chat/anoint`（擴充）**：加 `save_convo`（checkbox）＋`history`。冊封得 `wid` 後，若 `save_convo=1`：
  `title = title_factory(messages)`；`repo.save_conversation(title, messages, wid)`。冊封流本身不變（原則 5）。
- **`POST /chat/save`（新，獨立存）**：`history` → `messages`；`title=title_factory(messages)`；
  `save_conversation(title, messages, None)`；render chat.html 加 `saved_msg`。空對話→友善不存。
- **`GET /conversations`（新）**：`list_conversations` → `conversations.html`（清單：標題＋時間＋是否連著根因）。
- **`GET /conversations/{cid}`（新）**：`get_conversation` → `conversation.html`（用既有 `.md-render` 渲染整段）。
- **`GET /roots`（擴充）**：帶 `provenance = why_node_provenance()`；`roots.html` 每條 anointed 若在 map 內 →
  顯示「← 由來（對話）」連到 `/conversations/{cid}`。
- **導覽**：`base.html` 加「對話存檔」入口。

### 守純度（FR-004，核心）
`build_field_system_prompt(roots)` **只吃已冊封根因**（既有，不改）；`conversations` 表**不被任何對話路徑
讀進場脈絡**。守衛測：存一段對話後，`/chat`（spy backend）的 system prompt **不含**該對話內容。

### chat.html
- 送出區加「💾 存這段對話」（POST `/chat/save`，帶 `history`）。
- 冊封候選表單（`/chat/anoint`）加 checkbox「連同這段對話存成由來」＋ hidden `history`。

**不動**：`build_field_system_prompt`（守純度）、既有冊封/對話核心邏輯。

## Project Structure

### 受影響檔案
```text
src/learnnews/store/schema.py                 # + conversations 表（SCHEMA＋_migrate）
src/learnnews/store/repository.py             # save/list/get_conversation + why_node_provenance
src/learnnews/models/__init__.py（或 chat）    # Conversation dataclass
src/learnnews/chat/field_chat.py              # FieldChat.title（自動由來標題）
src/learnnews/web/app.py                       # /chat/save、/conversations、/conversations/{id}、
                                               #   /chat/anoint 擴充、/roots 帶 provenance、title_factory
src/learnnews/web/templates/chat.html          # 「存這段對話」＋冊封「連同存」checkbox
src/learnnews/web/templates/conversations.html # 新：清單
src/learnnews/web/templates/conversation.html  # 新：單篇（.md-render 渲染）
src/learnnews/web/templates/roots.html         # 加「← 由來」連結
src/learnnews/web/templates/base.html          # 導覽入口
tests/unit/test_conversations.py               # repo save/list/get、provenance、刪根因不崩、title 退回
tests/contract/test_conversation_web.py        # 兩存檔點、/conversations 頁、roots 由來連結、不入地基守衛
```

## 複雜度追蹤
- **新表 `conversations`**：這是第一個落庫的對話產物（episodes 層）；教訓 8「盡量不動既有資料結構」下
  仍屬正當新實體——對話由暫時（client 帶回）升為可持久回溯的場景。無其他複雜度。

## 部署／守純度總結
場脈絡只來自已冊封根因（既有、不改）；`conversations` 唯讀、僅供人讀，**永不注入回對話**（原則 6）。
