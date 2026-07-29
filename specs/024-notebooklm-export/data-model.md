# Data Model: 匯出給 NotebookLM

**本功能不新增資料表、不改 schema**——只**讀**既有實體、輸出**衍生產物**（不落庫）。

## 既有實體（唯讀）

### 對話 Conversation（`src/learnnews/models`，spec 023）
- `id: int`、`title: str`、`messages: list[dict]`、`why_node_id: int | None`、`created_at: str`
- `messages` 每則：`{"role": "user"|"assistant", "content": str, "sources"?: list[dict]}`
  - `sources` 每項：`{"n": int, "url": str, "title": str}`（**逐訊息各自從 1 編號**）

### 根因 WhyNode（`src/learnnews/rootcause/extract.py`）
- `claim: str`（最底層 aha）、`ladder: list[str]`（表面 → bedrock，每層一句）、
  `evidence_urls: list[str]`、`status`（本功能只匯出 `anointed`／`/roots` 呈現者）

## 衍生產物（不落庫，即時組出送剪貼簿）

### 對話 → Markdown（`conversation_to_markdown`）
```
# {title}

**你：** {user content}

**副手：** {assistant content（保留行內 [n]）}

來源：
- [1] {title} — {url}
- [2] {title} — {url}

**你：** …
```
- 空 messages → 僅標題（或「（無內容）」）；某則無 sources → 略過該則「來源：」塊；缺 content → 空字串。

### 對話 → 佐證網址清單（`conversation_evidence_urls`）
- 跨全訊息收集 `sources[*].url`、**去重保序** → `list[str]`。無來源 → `[]`。

### 根因 → Markdown（`why_node_to_markdown`）
```
# {claim}

## 為何（階梯：表面 → bedrock）
1. {ladder[0]}
2. {ladder[1]}
…

## 佐證
- {url1}
- {url2}
```
- 空 ladder → 略過階梯段；空 evidence_urls → 略過佐證段。

### 根因 → 佐證網址清單
- `dedup_urls(evidence_urls)` → 去重保序 `list[str]`。

## 不變量
- **唯讀**：不 INSERT／UPDATE／DELETE 任何表。
- **無副作用**：formatter 純函式；相同輸入 → 相同輸出（保序去重故可測）。
- **不注入回場**：匯出產物不進 `build_field_system_prompt`（原則 6 守衛測）。
