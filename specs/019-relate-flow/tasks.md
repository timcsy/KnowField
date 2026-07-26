# 任務清單：forward-pass 接每日流（匯整條目也能「關聯到我的場」）

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`019-relate-flow`

TDD 強制：每階段先寫紅測（Red）→ 實作轉綠（Green）。全複用 spec 018 引擎，零新相依/零新表。

---

## Phase 1：Setup
（無——沿用現有專案結構與 spec 018 全部後端；不新增相依。）

## Phase 2：Foundational（阻塞所有 US 的共用前置）

- [X] T001 [P] 在 `tests/test_relate_flow.py` 寫 `get_entry_material` 紅測：種子列（回 `(headline_or_title, body, url)`）、每日流列、不存在 id（回 `None`）三案。
- [X] T002 [P] 在 `tests/test_relate_flow.py` 寫 `get_last_digest` 帶 `entry_id` 紅測：落一份匯整後，`get_last_digest().entries[*].entry_id` 等於該列 `digest_entries.id`。
- [X] T003 在 `src/learnnews/models/__init__.py` 的 `DigestEntry` 追加 `entry_id: int | None = None`（尾端預設）。
- [X] T004 在 `src/learnnews/store/repository.py`：`get_last_digest` 的 SELECT 加 `de.id`（現無），建構 `DigestEntry(..., entry_id=r["id"])`；新增 `get_entry_material(entry_id)->(headline_or_title, body, url)|None`（以 `digest_entries.id` 取任一列，headline 優先，無列回 None）。跑 T001/T002 轉綠。

**檢查點**：repository 能以 id 取任一條目材料、匯整條目帶出 id；全綠。

---

## Phase 3：US1（P1）——今天這則新聞跟我已知的怎麼連 + 排除自己

- [X] T005 [P] [US1] 在 `tests/test_relate_flow.py` 寫 `/field/relate` 吃**流的條目** id 紅測：注入假 `field_relate_factory`，POST 一則每日流條目的 `entry_id` → 回 `field_relate.html`、factory 收到該條目材料（headline＋body）。
- [X] T006 [P] [US1] 寫**排除自己**紅測：POST 一則種子條目 id → factory 收到 `exclude_url=該條目 url`（FR-003）。
- [X] T007 [US1] 在 `src/learnnews/web/app.py`：`/field/relate` 改用 `repo.get_entry_material(entry_id)`（取代 `list_seeds` 專找種子）；`None`→`303 → /`；有材料→`field_relate_factory(title, body, exclude_url=url)`；結果頁 `material` 用取得的 title/url。跑 T005/T006 轉綠。
- [X] T008 [P] [US1] 在 `tests/test_relate_flow.py` 寫 `_entry.html` 渲染紅測：`PageEntry.entry_id` 有值→輸出含「關聯到我的場」表單與 `entry_id`；`entry_id=None`→**不含**該表單（FR-005）。
- [X] T009 [US1] `src/learnnews/web/views.py`：`PageEntry` 追加 `entry_id: int | None = None`，`entry_to_page` 以 `getattr(entry,"entry_id",None)` 帶出；`src/learnnews/web/templates/_entry.html` 卡片動作區加 `{% if e.entry_id %}` 的「🧭 關聯到我的場」表單（POST `/field/relate`，文案同 library）。跑 T008 轉綠。

**檢查點（US1 可獨立驗）**：首頁匯整條目（兩區）皆有關聯鈕、點擊回延伸/牴觸/成核/場空、排除自己；pull 條目無鈕。

---

## Phase 4：US2（P1）——維持深淺分明（按需，不自動）

- [X] T010 [US2] 在 `tests/test_relate_flow.py` 寫「首頁載入不自動關聯」紅測/守衛測：GET `/` 時 `field_relate_factory` **零呼叫**（用 spy factory 計數）。（實作已由 US1 的「按鈕才 POST」保證，此測為防回歸的守衛。）

**檢查點**：首頁載入不觸發任何關聯呼叫。

---

## Phase 5：US3（P2）——場空/失敗沿用友善

- [X] T011 [P] [US3] 寫失敗友善紅測：`field_relate_factory` 拋 `SourceUnavailable` → `/field/relate` 回 200＋`rel=None`（頁不崩，教訓 3）。（沿用 spec 018 的 try/except；此測確認流的條目路徑同樣被保護。）
- [X] T012 [P] [US3] 寫場空紅測：無吸引子時對一則流的條目關聯 → `rel.kind=="empty"`（走既有引擎，不另寫）。

**檢查點**：流的條目在場空/失敗時同樣友善。

---

## Phase 6：Polish & 回歸

- [X] T013 跑 `uv run pytest tests/test_field_relate_web.py -q` 確認**種子路徑零回歸**（library 種子鈕續用同一路由）。
- [X] T014 跑 `uv run pytest -q` 全綠（現 286 + 本增量新測）；確認範圍守住（無自動標每則/批次成核/多跳/關聯搜尋結果）。

---

## 依賴與執行順序
- Phase 2（T001–T004）阻塞全部 → 先做。
- US1（T005–T009）為 MVP：路由泛化 + 模板鈕。T007 依 T004（`get_entry_material`）。
- US2（T010）、US3（T011–T012）依 US1 路由就緒。
- Polish（T013–T014）最後。

## 平行機會
- T001‖T002（不同測案，同檔可先各寫）；T005‖T006‖T008（不同測）；T011‖T012。
- 實作 T003/T004/T007/T009 觸同批檔案，順序執行。

## MVP
**US1（T001–T009）**＝首頁每則匯整條目可關聯到場、排除自己、pull 無鈕。US2/US3 為守衛與邊界，薄。
