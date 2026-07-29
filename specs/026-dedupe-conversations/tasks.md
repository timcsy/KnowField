# 任務清單：既有重複對話清理（一次性、非破壞、人確認）

**規格**：[spec.md](./spec.md) ｜ **計畫**：[plan.md](./plan.md) ｜ **分支**：`026-dedupe-conversations`

TDD 強制：先紅後綠。**核心零新相依、無新表/新欄**（只刪多餘列＋UPDATE 連結）。純函式 `plan_dedupe` 為可測基石；計畫與執行分離。三重護欄：預覽＋人確認＋只併同指紋。

---

## Phase 1：Foundational（純計畫核心，阻塞執行與 web）

- [ ] T001 [P] `tests/unit/test_capture_core.py` 擴 `plan_dedupe` 紅測：3 組各數份（同指紋）＋若干不重複＋一組異指紋 → `delete_ids`＝各組非最大 id、`n_extra` 正確、每組 survivor＝max id；`repoint` 只含「provenance 指向 loser」的 wid→survivor；**異指紋不入計畫**；空/無重複→全空、三數 0；一組中**未連根因的多餘份**仍列入 `delete_ids`（但不產生 repoint）。
- [ ] T002 `src/learnnews/chat/capture.py`：實作 `plan_dedupe(convos, provenance)`＋`DedupePlan`（dataclass：`delete_ids/repoint/n_groups/n_extra/n_roots`），複用 `conversation_fingerprint`。跑 T001 轉綠。

**檢查點**：計畫純函式正確、離線可測、非破壞（異指紋不入計畫）、缺項不崩。

---

## Phase 2：US1（P1）——預覽（唯讀、人閘門）

- [ ] T003 [P] [US1] `tests/unit/test_dedupe_web.py` 寫預覽紅測：種同內容多份＋不同內容數份 → `GET /conversations/dedupe` 回應含「N 組／M 份多餘／K 條根因」；且呼叫後 `list_conversations` 份數、`why_node_provenance` **完全未變**（人閘門守衛，GET 不動資料）；無重複→顯示「沒有重複可清」。
- [ ] T004 [US1] `src/learnnews/store/repository.py` 加 `dedupe_plan()`（讀 `list_conversations`＋`why_node_provenance`→`plan_dedupe`，**不寫庫**）；`src/learnnews/web/app.py` 加 `GET /conversations/dedupe`（算計畫、渲染 `dedupe.html`）；建 `templates/dedupe.html`（顯示 N/M/K＋「確認清理」POST 表單＋「取消」連回；無重複→友善訊息無確認鈕）；`conversations.html` 頁首加「🧹 清理重複對話」鈕。跑 T003 轉綠。

**檢查點**：預覽顯示計畫、資料零變動、無重複友善。

---

## Phase 3：US2（P1）——確認執行（重指＋刪、非破壞）

- [ ] T005 [P] [US2] `test_dedupe_web.py` 寫執行紅測：種一組 N 份同內容（各連一根因）＋一組異指紋 2 份 → `POST /conversations/dedupe` → 該組只剩 1 份（max id）、N 條根因 `why_node_provenance` 皆改指 survivor、**異指紋兩份都在**、任一根因 `claim`／`ladder`**未變**；空庫 POST → 友善不崩、無變動。
- [ ] T006 [US2] `repository.py` 加 `apply_dedupe()`（重算 `dedupe_plan`→`UPDATE why_nodes SET conversation_id=survivor` for repoint＋`DELETE FROM conversations WHERE id IN delete_ids`＋commit；回摘要 `{groups,removed,repointed}`；**不碰 claim/ladder/evidence**）；`app.py` 加 `POST /conversations/dedupe`（`apply_dedupe`→`RedirectResponse('/conversations?cleaned=1&removed=M',303)`）；`conversations.html` 讀 `cleaned/removed` 顯示成功 flash。跑 T005 轉綠。

**檢查點**：同組留 1、根因全重指、異指紋不動、根因主張不變、清理後由來不斷。

---

## Phase 4：Polish＋守衛＋回歸

- [ ] T007 [P] 寫**非破壞守衛**紅測：執行後（a）`why_node_provenance` 每條原有由來的根因仍連得到（指向仍存在的 survivor、不孤兒）；（b）異指紋對話（不同 messages）份數與內容不變；（c）根因總數不變（只重指、不刪根因）。
- [ ] T008 全繁中檢查（鈕/預覽/flash 文案）＋範圍守住（**無**併相關非相同、**無**自動/背景清理、**無** #3 章節切分/重命名、**無**全文搜尋/跨對話關聯、**無** CLI）。
- [ ] T009 跑 `uv run pytest tests/unit/test_capture_core.py tests/unit/test_dedupe_web.py -q` 全綠；再 `uv run pytest -q` 全綠（現 414 ＋ 本增量）；既有 spec 023/025 行為零回歸。

---

## 依賴與平行

- **純核心（T001-T002）→ US1 預覽（T003-T004）→ US2 執行（T005-T006）→ Polish**。US1／US2 皆依賴純核心；預覽（唯讀）先於執行（寫）。
- **MVP＝US1+US2**（預覽＋執行是一個完整動作的兩段，皆 P1）；單獨 US1（預覽）也已有價值（掌握囤積現況、零風險）。
- 紅測多可 `[P]`（不同測試檔/案例）。
