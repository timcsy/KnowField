# Tasks：翻譯落庫快取（spec 039 · 階段 36）

**輸入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[data-model.md](./data-model.md)、[quickstart.md](./quickstart.md)

**TDD（憲章 I，不可妥協）**：每個測試任務都要**先看到紅燈**再寫實作。
⚠️ D3（降級不快取）與 D5（命中早於建後端）兩條是「沉默失效」型——正確與根本沒接上，
在綠燈下長得一模一樣，所以紅燈是唯一的區分方式（`experience.md:705`）。

---

## Phase 1：Setup

- [X] T001 在 `src/knowfield/store/schema.py` 的 `SCHEMA` 末尾加入 `source_translations` 表（DDL 見 data-model.md）；確認 `CREATE TABLE IF NOT EXISTS` 讓兩種後端都免遷移腳本

## Phase 2：Foundational（阻擋所有 user story）

- [X] T002 [P] 在 `tests/unit/test_translate.py` 加 `TestContentKey`：同字串同鍵、差一字不同鍵、回傳為 64 位十六進位 —— **先跑，要紅**
- [X] T003 在 `src/knowfield/text/translate.py` 加 `content_key(md: str) -> str`（SHA-256 十六進位），讓 T002 轉綠
- [X] T004 [P] 在 `tests/unit/test_translation_cache.py` 加 `TestTranslationCache`：存了取得回、`content_key` 不符回 `None`、不存在回 `None` —— **先跑，要紅**
- [X] T005 在 `src/knowfield/store/repository.py` 加 `get_translation` / `save_translation`（`ON CONFLICT(url) DO UPDATE`），讓 T004 轉綠

---

## Phase 3：User Story 1 — 第二次開不用再等（P1）

**目標**：同一份來源第二次要譯文時秒回。
**獨立測試**：對同一份來源翻兩次，第二次明顯更快且內容相同。

- [X] T006 [US1] 在 `tests/contract/test_web_translate.py`寫「快取命中」測試：預先塞一列快取，
      呼叫 `/api/source/translate`，斷言 ① 只收到一則 `done`、② `markdown` ＝ 快取內容、
      ③ **完全沒有 `stage` 事件**（進度條不該閃） —— **先跑，要紅**
- [X] T007 [US1] ⚠️ 在同檔寫「命中時不建翻譯後端」測試（D5）：把 `make_translate_backend` 換成
      會 raise 的假物件，命中路徑仍須成功回譯文 —— **先跑，要紅**。
      這條釘的是**程式碼順序**，不是行為：查快取必須排在建後端之前
- [X] T008 [US1] 在 `src/knowfield/web/app.py` 的 `api_source_translate` 開頭加入查快取分岔，讓 T006／T007 轉綠
- [X] T009 [US1] 在同檔寫「未命中則翻譯並落庫」測試：假後端回可預測譯文，呼叫一次後直接查 DB 斷言已寫入 —— **先跑，要紅**
- [X] T010 [US1] 在 `api_source_translate` 的 `done` 之前加入寫快取，讓 T009 轉綠

---

## Phase 4：User Story 3 — 原文仍是真相（P1）

**目標**：落庫的是衍生物，原文一個字都沒動。
**獨立測試**：翻譯並快取後，比對儲存的原文與快取前逐字相同。

- [X] T011 [P] [US3] 在 `tests/contract/test_web_translate.py` 寫「原文逐字不變」測試：
      翻譯前後各取一次 `repo.get_source_chunks(url)`，斷言完全相等 —— **先跑，要紅**（無實作時本來就綠 ⇒ 這條要靠 T012 的反向攻擊才有牙齒）
- [X] T012 [US3] ⚠️ 對 T011 做一次**反向攻擊**：暫時讓 `save_translation` 也寫回 chunks，確認 T011 由綠轉紅，再還原。
      沒撞過的測試不知道自己在測什麼——本任務的產出是「撞過了」這個事實，記在 commit message

---

## Phase 5：Edge Cases（FR-004 / FR-006）

- [X] T013 [P] 在 `tests/contract/test_web_translate.py` 寫「內容變了不給舊譯文」測試（FR-004／SC-004）：
      塞快取後改動 chunk，斷言走重新翻譯（有 `stage`）而非秒回 —— **先跑，要紅**
- [X] T014 ⚠️ 寫「含降級單位不快取」測試（FR-006／D3）：假後端讓部分單位失敗（`failed > 0`），
      呼叫後斷言 DB 中**沒有**該 url 的列 —— **先跑，要紅**。
      ⚠️ 紅燈必須真的出現：若一開始就綠，代表寫快取那段根本沒被觸及，測試是假的
- [X] T015 讓 T013／T014 轉綠（命中條件含 `content_key`；`failed > 0` 時跳過寫入）

---

## Phase 6：FR-005 自動清理

- [X] T016 [P] 在 `tests/unit/test_translation_cache.py` 加 `purge_stale_translations` 測試：
      過期的刪、未過期的留、回傳刪除數 —— **先跑，要紅**
- [X] T017 在 `repository.py` 實作 `purge_stale_translations(before)`，讓 T016 轉綠
- [X] T018 在 `api_source_translate` 進入時呼叫清理（門檻 180 天），並記一行 `_log`；
      ⚠️ **不得**新增任何設定項或介面元素（FR-003／FR-005）

---

## Phase 7：Polish & 驗收

- [X] T019 `uv run pytest -q` 全綠（SC-005 零回歸）
- [X] T020 `git diff --stat` 確認 **`frontend/` 零檔案改動**——這是 FR-003／SC-002 最強的結構性證據
- [X] T021 ⚠️ 依 [quickstart.md](./quickstart.md) §2 用**瀏覽器真跑**：首次翻譯計時 → 重整 → 再翻，
      確認秒回且進度條不閃。真跑是唯一照得出前端整合缺陷的方式（`experience.md:602`）
- [X] T022 依 quickstart §4 真跑 FR-004（改內容 → 應重新翻譯）

---

## 依賴

```
T001 ─┬─ T004,T005 ─┬─ T006..T010 (US1) ─┬─ T013..T015
      └─ T002,T003 ─┘                    ├─ T016..T018
                                          └─ T011,T012 (US3)
                                                 └─ T019..T022
```

## 平行機會

`[P]` 標記者可同時進行：T002／T004（不同測試檔）、T011／T013／T016（同檔不同類別，但需注意同檔衝突 → 實際上依序寫較安全）。

## MVP 範圍

**T001–T010**（Phase 1–3）＝ 使用者要的東西本身：第二次不用等。
T011–T018 是紅線與自動清理，**同刀必做**（FR-002／004／005／006 都是 MUST）。


---

## ⚠️ Phase 8：真跑推翻了 D3，加做的（2026-08-21）

T021 的真跑照出：45 個單位失敗 1 個 ⇒ 逐文件快取一個字都不存 ⇒
使用者要的「自動保存」根本不會發生。這不是運氣，是 (1-p)^N 的結構問題。

- [X] T023 把快取由**逐文件**改為**逐翻譯單位**：`source_translations` → `translation_units`
      （鍵＝單位原文雜湊，無 url 欄）；repository 三個方法改為複數版
- [X] T024 `translate_stream` 的 `done` 事件加上逐塊 `ok` 陣列 ——
      ⚠️ 不能用「譯文 == 原文」去猜成敗（純程式碼／URL 的單位翻完本來就可能一樣）
- [X] T025 路由：逐單位查 → 只翻沒命中的 → 只存成功的；`stage` 的分母＝真正還要做的量
- [X] T026 加 `test_partial_failure_keeps_the_good_units`（US1 的真正驗收），
      並反向攻擊（改回「全成功才存」）確認它會紅
- [X] T027 ⚠️ 修 `logging_setup`：handler 改掛套件根 `knowfield`。
      原本只掛在 `knowfield.web`／`knowfield.cli` ⇒ `knowfield.text.translate` 的 INFO
      **從來沒印出來過**，而那是診斷翻譯降級唯一的線索（憲章 V）。加 `test_logging_reach.py`
- [X] T028 真跑複驗：113 秒/存 44 → 5.6 秒（只重翻 1 個）→ **0.03 秒**（全命中、0 個 stage）；
      瀏覽器點「🌐 翻成繁中」瞬間出譯文，畫面上無任何快取痕跡
