# Web 契約：`/sources`（來源訂閱）

## GET /sources
- 列出所有來源：名稱、類型、啟用狀態；每個有停用/啟用、刪除鈕；頂部「加來源」框（貼 URL）。

## POST /sources/add
- Form：`url`。
- `subscribe_factory(url)`：探測 feed→實測有料→回 Source。
  - 有效且新 → `upsert_source`（啟用）→ 成功訊息（含來源名稱）。
  - 已追蹤（同 id）→ 「已在追蹤」，不重加。
  - `SourceUnavailable`（無 feed/無料/網路失敗）→ **頁內友善繁中、不落庫任何來源**（FR-004）。
- → 重繪 `/sources`（帶結果訊息）。

## POST /sources/toggle
- Form：`source_id`、`enabled`（1/0）。`set_source_enabled` → 303 `/sources`。停用後匯整不抓（FR-006）。

## POST /sources/remove
- Form：`source_id`。`delete_source` → 303 `/sources`。刪除被尊重（不自動補回，除非來源全空）。

## 不變式（對映 FR）
- 加前**實測有料才落庫**（FR-003）；失敗**不加壞來源**（FR-004）。
- 加的來源**下次 digest 自動抓**（build_adapters 吃 DB sources，FR-005）。
- 同 feed 不重複（FR-007）；工具不自動加來源（FR-008）。
- 全繁中（FR-009）；探測/驗證離線可注入 fetch（FR-010）。
