# Data Model: 對話的可找回性

**無結構變更**——US1 只 `UPDATE conversations.title`；章節（US2）**衍生、不落庫**；不新增表/欄。

## 純值／衍生
- `title_material(messages, head_chars, tail_chars) -> str`（純）：首段＋尾段並取的取材字串（尾為主）。
- **章節 Chapter**（衍生、不落庫）：`{"title": str, "start": int, "end": int, "summary": str}`——`start/end` 為 1-based 訊息序。
- `normalize_chapters(raw, n_messages) -> list[Chapter]`（純）：clamp/排序/補洞/去重疊 → 涵蓋 `[1,n]` 不重疊；空/壞→`[{title:整段, start:1, end:n, summary:""}]`。
- **章節切片**：`messages[start-1:end]`——供每章匯出（spec 024）與整理（distill）。

## 既有實體（動作對象）
- **對話 Conversation**：US1 更動 `title`（自動更準／手動改名／重生）。其餘不變。

## 不變量
- **章節涵蓋且不重疊**：`normalize_chapters` 保證各章範圍銜接、覆蓋全對話、無漏無疊。
- **不落庫**：章節每次即時算、可重算；不寫任何表。
- **人閘門**：改名/重生/切分/每章冊封皆人觸發；系統不自動改標題、不自動切分、不自動冊封（原則 5）。
- **失敗退回**：title 失敗→首句截斷；segment 失敗/過短→整段一章（教訓 3）。
