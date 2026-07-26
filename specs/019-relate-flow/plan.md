# 實作計畫：forward-pass 接每日流（匯整條目也能「關聯到我的場」）

**分支**：`019-relate-flow` ｜ **日期**：2026-07-26 ｜ **規格**：[spec.md](./spec.md)

## 摘要

把階段 15（spec 018）的關聯引擎 `FieldRelate` **原封不動**接到首頁每日匯整條目上：每則加一個
「🧭 關聯到我的場」按鈕 → 用該條目材料跑既有 forward pass（找最近冊封吸引子 → 判延伸/牴觸/無關聯/
成核/場空）→ 顯示既有 `field_relate.html`。**不改引擎、不新增相依、場不自動改**。

技術缺口只有三個接點：①`get_last_digest` 帶出 `digest_entries.id`；②`/field/relate` 從「只找種子」泛化
成「用 id 取任一條目（種子或流）的材料」；③`_entry.html` 加按鈕（有 id 才顯示，pull 即時條目自然無鈕）。

## Technical Context

**Language/Version**：Python 3.12+（現況）
**Primary Dependencies**：stdlib only（urllib）；web 層 FastAPI＋Jinja2（現有，不新增）
**Storage**：SQLite（`digest_entries` 既有表，**不改 schema**）
**Testing**：pytest（現 286 綠）
**Project Type**：CLI＋web（本增量只動 web 層＋repository 讀取＋一個 model 欄位）
**Constraints**：離線可測（stub 判關係＋stub embedder，零外部呼叫）；按需觸發；場不自動改

## Constitution Check

| 原則 | 判定 | 理由 |
|------|------|------|
| I. TDD 不可妥協 | ✅ | 每接點先寫紅測（repo 取材料、路由吃流的 id、`_entry` 有鈕/pull 無鈕）再實作 |
| II. 全繁中 | ✅ | 按鈕文案、結果頁沿用 spec 018 繁中 |
| III. 規格驅動 | ✅ | spec 019→plan→tasks→impl，可追溯 FR |
| IV. 簡潔／YAGNI | ✅ | **零新相依、零新表、不重寫引擎**；只加一欄位＋一 repo 方法＋泛化一路由＋一模板鈕 |
| V. 可觀測／錯誤處理 | ✅ | 沿用 spec 018：判關係失敗 `_log.error`＋友善繁中、不噴 traceback（教訓 3） |
| VI. 使用者決策主權 | ✅ | 原則 5：只提關係、**不寫任何庫**；按需（不自動標每則） |

**無違反、無複雜度追蹤項。**

## 技術方案（三接點）

### 接點 1：`get_last_digest` 帶出條目 id
- `models.DigestEntry` 追加 `entry_id: int | None = None`（尾端有預設，不破壞既有具名建構）。
- `repository.get_last_digest`：SELECT 加 `de.id`（現無），建 `DigestEntry(..., entry_id=r["id"])`。
- `views.entry_to_page`：`PageEntry` 追加 `entry_id: int | None = None`；讀 `getattr(entry, "entry_id", None)`
  （DigestEntry 有 → 帶出；PullEntry 無 → None，pull 頁自然不顯示鈕，滿足 FR-005）。

### 接點 2：`/field/relate` 泛化吃流的條目
- 新增 `repository.get_entry_material(entry_id) -> tuple[str, str, str] | None`：以 `digest_entries.id`
  取任一條目（種子容器 or 每日流皆可），回 `(headline_or_title, body, url)`；不存在→`None`。
- 路由改：`material = repo.get_entry_material(entry_id)`（取代 `list_seeds` 專找種子）。`None`→
  導回首頁。有→`field_relate_factory(title, body, exclude_url=url)`。**排除自己沿用 `exclude_url`**（FR-003）。
- 結果頁 context 的 `material.title/url` 改用取得的材料。**library 種子鈕不受影響**（種子也是
  `digest_entries` 一列，`get_entry_material` 一樣取得）——一條路徑同時服務種子與流。

### 接點 3：`_entry.html` 加按鈕
- `_entry.html` 卡片動作區加 `{% if e.entry_id %}` 的「🧭 關聯到我的場」表單（POST `/field/relate`，
  `entry_id={{ e.entry_id }}`），文案同 library。`digest.html` 兩區（`news_entries`／`foundational_entries`）
  皆 `include "_entry.html"`——一次改、兩區生效（FR-001）。pull.html 也 include 但條目無 `entry_id`→無鈕。

**不動**：`field/relate.py` 引擎、`field_relate.html`、`list_field_attractors`、`make_relation_judge`、
`make_embedder`、`field_relate_factory`、schema。

## Project Structure

### 受影響檔案
```text
src/learnnews/models/__init__.py          # DigestEntry += entry_id
src/learnnews/store/repository.py         # get_last_digest 帶 id；get_entry_material（新）
src/learnnews/web/views.py                # PageEntry += entry_id；entry_to_page 帶出
src/learnnews/web/app.py                  # /field/relate 泛化（get_entry_material）
src/learnnews/web/templates/_entry.html   # 加關聯鈕（{% if e.entry_id %}）
tests/test_relate_flow.py                 # 新測（本增量）
tests/test_field_relate_web.py            # 既有種子路徑回歸不破
```

## 複雜度追蹤
無。零新相依、零新表、零引擎改動。
