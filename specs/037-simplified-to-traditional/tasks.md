# 任務：來源簡體中文正規化為繁體（顯示層）

**輸入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/api-source.md](./contracts/api-source.md)

**測試為必要**：憲章 I「測試優先開發（TDD，不可妥協）」——先紅後綠，禁止在沒有失敗測試的情況下寫功能碼。

**基準**：現有 369 個 test 函式，完工後 MUST 零回歸。

---

## Phase 1：Setup

- [X] T001 在 `pyproject.toml` 加入可選相依 `opencc-python-reimplemented`（純 Python、無 C 相依），置於 optional extras，並更新 `uv.lock`
- [X] T002 建立模組骨架 `src/knowfield/text/__init__.py`（空模組，僅宣告 package）

---

## Phase 2：Foundational（阻塞所有 user story）

⚠️ 本階段是**承重保護**的地基。[research.md](./research.md) 實測顯示六個危險案例在無保護下**全部被破壞**，
因此 US1 不得在 Phase 2 完成前出貨。

- [X] T003 [P] 撰寫 `tests/unit/test_text_protect.py`：往返不變式 `restore(*mask(t)) == t`，涵蓋空字串、純文字、巢狀結構（fenced 內含 `$` 與反引號）——**先確認測試失敗**
- [X] T004 [P] 撰寫 `tests/unit/test_text_protect.py` 的類別覆蓋測試：圍欄程式碼、數學區塊、圖片、連結 URL、行內程式碼、行內數學、裸 URL 各一例——**先確認測試失敗**
- [X] T005 實作 `src/knowfield/text/protect.py` 的 `mask(text) -> (masked, segments)` 與 `restore(masked, segments) -> str`，抽取順序依 [data-model.md](./data-model.md)：塊級（fenced、`$$`）先於行內（圖片、連結 URL、`` ` ``、`$`、裸 URL）
- [X] T006 在 `src/knowfield/text/protect.py` 實作佔位符格式：純 ASCII + 數字（`s2twp` 不會轉換），並加測試「佔位符本身經轉換後不變」

---

## Phase 3：User Story 3 — 承重內容不被轉換破壞（P1）

**目標**：轉換不得改壞程式碼、URL、圖片、數學。

**獨立測試**：把 [research.md](./research.md) 的六個危險案例逐一送進轉換，比對承重片段與輸入逐字相同。

⚠️ **本故事優先於 US1 實作**，因為沒有它 US1 的淨值為負（見 plan.md 的 Summary）。

- [X] T007 [P] [US3] 在 `tests/unit/test_text_s2t.py` 寫入 research.md 六個危險案例的迴歸測試：`def 处理(内存):`、`http://a.cn/发展/index.html`、`pic1.zhimg.com/发展_v2.jpg`、`$$…\text{发展}$$`、`$x_{发}$`、`` `发送` ``——每例斷言承重片段逐字不變，**先確認失敗**
- [X] T008 [US3] 在 `src/knowfield/text/s2t.py` 的 `convert()` 內串接 `protect.mask` → 引擎 → `protect.restore`
- [X] T009 [P] [US3] 加邊界測試於 `tests/unit/test_text_s2t.py`：連結的 `[顯示文字]` **要轉**、`(url)` **不轉**；圖片整段（含 alt）**不轉**——依 data-model.md 第 3/4 條

---

## Phase 4：User Story 1 — 讀一篇簡體來源不必費力（P1）

**目標**：詳情頁預設顯示繁體，含詞彙在地化。

**獨立測試**：開啟知乎〈深入解析Flow Matching技术〉的詳情頁，正文為繁體且「技术」顯示為「技術」。

- [X] T010 [P] [US1] 在 `tests/unit/test_text_s2t.py` 加轉換行為測試：簡體詞彙（软件→軟體、内存→記憶體、程序员→程式設計師）、繁體輸入逐字不變、英文逐字不變、一對多（头发/发展）、全形標點不變——**先確認失敗**
- [X] T011 [US1] 實作 `src/knowfield/text/s2t.py` 的 OpenCC 後端（`s2twp`）與 `convert(text) -> str` 介面
- [X] T012 [P] [US1] 撰寫 `tests/contract/test_web_source_s2t.py`：`GET /api/source` 預設回繁體、回應含 `s2t_applied` 欄位（契約 C-002、C-005）——**先確認失敗**
- [X] T013 [US1] 在 `src/knowfield/web/app.py` 的 `/api/source`（約 `:621`）於 `stitch_chunks` 拼回**之後**套用 `text.s2t.convert`，並回傳 `s2t_applied`
- [X] T014 [US1] 確認未觸碰任何寫入路徑：加測試斷言呼叫 `/api/source` 前後 `digest_entries.article_body` 逐字未變（FR-004）

---

## Phase 5：User Story 2 — 原文仍是真相，隨時取得回（P1）

**目標**：使用者能取回未經轉換的原文。⚠️ **這條同時是憲章 VI（可覆寫）的兌現**，缺了它本功能違憲。

**獨立測試**：對同一來源以 `raw=1` 取得內容，與 `get_source_chunks` 拼回結果逐字比對。

- [X] T015 [P] [US2] 在 `tests/contract/test_web_source_s2t.py` 加契約測試 C-001（`raw=1` 回原文逐字相同）與 C-004（`raw` 非法值視為 0，不回錯誤）——**先確認失敗**
- [X] T016 [US2] 在 `src/knowfield/web/app.py` 的 `/api/source` 加入 `raw` 查詢參數，依 [contracts/api-source.md](./contracts/api-source.md) 實作
- [X] T017 [US2] 在 `frontend/src/SourcePage.tsx` 加「繁體 ⇄ 原文」切換（**擇一顯示，非並置對照**），僅在 `s2t_applied=true` 時顯示

---

## Phase 6：User Story 4 — 轉換能力缺席時仍可用（P2）

**目標**：引擎不可用時顯示原文、不中斷。

**獨立測試**：在引擎不可用的環境下開啟詳情頁，回 200、內容為原文、`s2t_applied=false`。

- [X] T018 [P] [US4] 在 `tests/unit/test_text_s2t.py` 加 fallback 測試：引擎不可用時 `convert()` 回傳輸入本身（identity）——**先確認失敗**
- [X] T019 [US4] 在 `src/knowfield/text/s2t.py` 實作可插拔載入與 identity fallback，並依憲章 V 記一次結構化日誌（不靜默吞例外）
- [X] T020 [P] [US4] 加契約測試 C-003 於 `tests/contract/test_web_source_s2t.py`：引擎不可用時 `/api/source` 回 200、`s2t_applied=false`

---

## Phase 7：Polish & 跨切面

- [X] T021 執行 `uv run pytest -q` 全量，確認零回歸且總數 > 369（SC-006）
- [X] T022 [P] 量測 SC-003：比較 `raw=1` 與 `raw=0` 的回應時間，差值須 < 200ms；未達標則記錄並提出對策
- [X] T023 [P] 依 [quickstart.md](./quickstart.md) 第 3 節對真實來源（知乎 Flow Matching）做端到端驗證
- [ ] T024 人工確認憲章 VI：前端切換確實能看回原文

---

## 相依關係

```
Phase 1 (T001-T002)
    ↓
Phase 2 承重保護 (T003-T006)  ← 阻塞一切
    ↓
Phase 3 US3 (T007-T009)       ← 必須先於 US1 完成
    ↓
Phase 4 US1 (T010-T014)       ← MVP 的另一半
    ↓
Phase 5 US2 (T015-T017)       ← 憲章 VI，出貨前必備
    ↓
Phase 6 US4 (T018-T020)       ← 可延後，不阻塞出貨
    ↓
Phase 7 (T021-T024)
```

## 可平行的任務

- Phase 2：T003 與 T004（不同測試案例，同檔不同函式，可分開寫）
- Phase 3：T007 與 T009
- Phase 4：T010 與 T012（不同檔）
- Phase 6：T018 與 T020（不同檔）
- Phase 7：T022 與 T023

## 實作策略

⚠️ **MVP 不是「只做 US1」**。範本的預設是 MVP = 最高優先故事，但**這個功能的 US1 單獨出貨會造成傷害**
——實測顯示無保護的轉換會改壞程式碼識別字、URL 與圖片路徑（[research.md](./research.md)）。

因此：

- **真正的 MVP = Phase 2 + US3 + US1**（保護 → 轉換 → 接上詳情頁）
- **出貨門檻 = 再加 US2**（憲章 VI：沒有看原文的出口就違憲）
- **US4 可延後**：它不創造價值，只防止閱讀輔助變成閱讀障礙；沒它功能仍可用（只是缺套件時會壞）

三個 P1 並列不是排序失誤：US1 是價值、US3 是它的**前提**、US2 是它的**約束**。缺任一，這個功能都不該出貨。

---

## 執行結果（2026-08-18）

**T001–T023 完成，T024 待人工確認**（前端切換要你自己開瀏覽器看，AI 做不到）。

- 測試：**369 → 419 個 test 函式，全綠、零回歸**（SC-006 ✅）
- 對真實來源（知乎〈深入解析Flow Matching技术〉，`stitch_chunks` 後 13,111 字元）實測：
  - SC-003 轉換耗時 **33.9 ms**（門檻 200ms）✅
  - SC-002 承重片段：URL 6/6、圖片 6/6、**行內數學 161/161** 逐字保留 ✅
  - FR-002 正文詞彙在地化：`这` 35/35、`变换` 23/23、`转换` 5/5 全轉 ✅
  - FR-004 儲存層逐字未變 ✅

⚠️ **一個查證過程值得記**：初次驗證我用 `"\n\n".join(chunks)` 而非 `stitch_chunks`，
造成塊重疊未去除、`$` 數量變成奇數、配對錯位，於是「有正文沒轉到」。
**那是驗證方法的錯，不是實作的錯**——換成與 `/api/source` 完全相同的 `stitch_chunks`
路徑後 `$` 為偶數（322），殘留歸零。教訓：驗證要走與正式路徑**完全相同**的管線，
否則照出來的是驗證腳本的 bug。

### 已知限制（設計如此，非缺陷）

- 圖片 alt 內的文字不轉（`![深入解析Flow Matching技术](…)` 維持簡體）。
  依 data-model.md 第 3 條，圖片整段保護——alt 常與檔名對應，且極少需要閱讀。
- 採顯示層（岔路 ①）⇒ **檢索索引仍是簡體**，以繁體詞查詢可能撈不到簡體來源。
  已在 spec Assumptions 明列，不在本刀解決。
