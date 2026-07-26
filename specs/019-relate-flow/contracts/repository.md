# 契約：repository 讀取（spec 019）

## `get_entry_material(entry_id: int) -> tuple[str, str, str] | None`（新增）
以 `digest_entries.id` 取任一條目材料（**種子容器或每日流皆可**）。

- **回傳**：`(title, body, url)`，其中 `title = article_headline or title`（headline 優先，溯源）。
- **不存在**：回 `None`（路由據此導回首頁）。
- **不寫庫**：純讀。

## `get_last_digest() -> Digest | None`（既有，變更）
- 每個 `DigestEntry` **新增帶出** `entry_id = digest_entries.id`（SELECT 加 `de.id`）。
- 其餘不變（rank/title/url/article/matched_topic/source_id）。

---

# 契約：web 路由（spec 019）

## `POST /field/relate`（既有，泛化）
- **輸入**：`entry_id`（Form，int）——**任一 `digest_entries.id`**（種子 or 每日流）。
- **行為**：
  1. `material = repo.get_entry_material(entry_id)`；`None` → `303 → /`（導回首頁）。
  2. 有材料 → `field_relate_factory(title, body, exclude_url=url)` 跑既有 forward pass。
  3. 判關係失敗（`SourceUnavailable`/`OpenAIError`）→ `_log.error` ＋ `rel=None`（友善，教訓 3）。
- **輸出**：`field_relate.html`，`context={"material": {"title","url"}, "rel": rel}`（同 spec 018）。
- **不變**：不寫任何庫（原則 5）；種子路徑續用（種子亦一列 `digest_entries`）。

## 首頁條目呈現（`digest.html` → `_entry.html`）
- 每則 `PageEntry.entry_id` 非 None → 顯示「🧭 關聯到我的場」表單（POST `/field/relate`，
  `entry_id={{ e.entry_id }}`）。
- `entry_id` 為 None（pull 即時條目）→ **不顯示**按鈕（FR-005）。
