# Tasks：帶入物的由來落庫（spec 044 · 階段 40）

**TDD**：先紅再實作。⚠️ FR-004／FR-007 是沉默失效型，要反向攻擊。

## Phase 1：可攜補欄（地基）

- [X] T001 `tests/unit/test_schema_add_columns.py` —— **先紅**
      ① 缺欄且**有資料**的舊庫 → 跑 `init_db` → 欄出現、資料列數與內容逐字不變
      ② 連跑三次不報錯、欄不重複（冪等）
      ③ ⚠️ 表不存在時要**丟出來**，不是靜默略過（否則型別寫錯也會沉默）
- [X] T002 `src/knowfield/store/schema.py`：`_ADD_COLUMNS` 清單 ＋ `_ensure_columns(conn)`
      （SQLite 走 `PRAGMA table_info`、PG 走 `information_schema.columns`），`init_db` 收尾呼叫；補欄記一行 log
- [X] T003 ⚠️ 反向攻擊：把 `_ensure_columns` 改成 try/except 吞例外，確認 ③ 轉紅

## Phase 2：由來落庫

- [X] T004 `tests/unit/test_carried_provenance.py` —— **先紅**
      ① 新建時帶 article → 由來 = ('article', id)
      ② 帶 source → ('source', url)
      ③ 沒帶 → 空
      ④ ⚠️ 同一筆再 autosave 兩次（且第二次故意送**不同**的由來）→ 由來**不變**
- [X] T005 `repository.autosave_temporary(..., carried_kind='', carried_ref='')`
      —— 只改 INSERT 分支，UPDATE 分支一個字不動
- [X] T006 ⚠️ 反向攻擊：讓 UPDATE 分支也寫由來，確認 ④ 轉紅

## Phase 3：路由與前端

- [X] T007 `tests/contract/test_autosave_carried.py` —— **先紅**
      ① 路由把 carried 傳下去 ② 沒帶時**請求與回應與現況逐字相同**
- [X] T008 `src/knowfield/web/app.py`：`/api/chat/autosave` 接兩個欄位
- [X] T009 `frontend/src/lib/api.ts` ＋ `ChatPage.tsx`：autosave 帶上 `carried`；
      ⚠️ **零可見元素**（FR-008／SC-006）
- [X] T010 ⚠️ 驗 FR-007：帶入物由來落庫**不改變送給模型的訊息**——
      沿用 spec 042 的 capture backend，比對逐字相同

## Phase 4：audit 讀得到

- [X] T011 `knowledge/skills/audit-field-usage/audit.py`：加一段「帶入物由來」統計
      （article／source 各幾段、空的幾段）
- [X] T012 `uv run pytest -q` 全綠（SC-007）；`npm run build` 綠

## Phase 5：真跑

- [X] T013 ⚠️ 對**既有的本機 knowfield.db**（有 13 段對話）起一次服務，確認欄補上、資料沒動
- [X] T014 瀏覽器：帶著文章開一段新對話 → 查 DB 由來正確；不帶的那段由來為空
- [X] T015 反流 → 出貨（`ship-knowfield`）；⚠️ 部署後確認**正式庫**的欄也補上了


---

## 真跑結果（2026-08-22）

- **T013**：對**真實本機庫**（13 段對話）補欄——欄出現、列數仍 13、
  訊息長度逐字不變（#18 的 181,415 字原封不動）、既有對話由來全空（本來就該空）。
- **T014**：帶著文章開新對話 → `#30 kind=article ref=1`；
  不帶的那段 → `#31 由來=''`；畫面上「由來／carried」字樣 **0 處**。
- **T011**：audit 的階段 37 從 🔴（永遠空白）變成 🟡 1/15。
  ⚠️ 並在報告尾端註明「在 spec 044 之前建立的對話一律為空，那是**沒資料**不是**沒人用**」
  ——不然這個數字自己就會變成下一個誤導。
