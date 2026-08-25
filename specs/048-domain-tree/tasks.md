# Tasks：知識庫的樹（spec 048 · 階段 43）— 全部完成

- [X] T001 `tests/unit/test_domain_tree.py` 先紅（13 條）
- [X] T002 `domains` 表 ＋ `conversations.domain_id`（走 spec 044 的 `_ADD_COLUMNS`）
- [X] T003 repository：`create_domain`／`list_domains`／`rename_domain`／`domain_path`／
      `domain_descendants`／`move_domain`（擋成環）／`set_conversation_domain`
- [X] T004 ⚠️ 反向攻擊：拿掉成環檢查 → 撞紅 2 條
- [X] T005 ⚠️ 反向攻擊：把 `domain_path` 改成讀快取（模擬「存路徑字串」）→ **第一次撞不紅**
- [X] T006 修測試（先讀→改名／搬家→再讀）→ 重跑攻擊，撞紅 2 條
- [X] T007 `tests/contract/test_domain_api.py` 先紅（含 `TestGroundingUnchanged`）
- [X] T008 路由：`/api/domains` CRUD ＋ `/api/conversations/{cid}/domain`；autosave 帶 `domain_id`
- [X] T009 ⚠️ 反向攻擊 grounding：**第一次攻到非串流路徑**（測試走串流）→ 沒撞紅；
      攻對串流路徑後撞紅 2 條
- [X] T010 前端：`DomainsPage`、路由、側欄導覽、`?new=1&domain=N`
- [X] T011 `uv run pytest -q`（595）＋ `npm run build` ＋ `npm run test -- --run`（20）綠
- [X] T012 真跑

## 真跑（2026-08-25，本機，經真實 proxy）

⚠️ **先讀 vite 印出來的 port（5174）**，沒有假設 5173。

- 樹：`AI` / `AI/生成模型` / `AI/生成模型/Flow Matching` / `數學` / `數學/生成模型`
- ⚠️ **SC-002 同名不同父**：兩個「生成模型」的路徑分別是 `AI / 生成模型` 與 `數學 / 生成模型`
- ⚠️ **SC-003 成環被擋**：把 `AI` 搬到 `Flow Matching` 底下 →
  `{"ok":false,"err":"不能把領域搬到它自己或它的子孫底下（會成環）"}`，**樹維持原狀**
- **SC-004**：在「生成模型」底下開新對話 → `#32 → 領域 2（生成模型）` 落庫
- **SC-005**：未歸屬 15 段，`why_nodes` **根本沒有 domain 欄**（這一刀不碰）
- **SC-006**：`git diff` 中那 8+4 處 grounding 呼叫點改動行數 **＝ 0**
- 順手修掉一個：領域頁那行說明的 `**粗體**` 在 JSX 裡不會渲染，改成 `<b>`

## ⚠️ 三次反向攻擊的教訓（同一件事的三種形態）

1. T005：攻擊**是真的**，但測試在改名前從沒讀過路徑 ⇒ 快取沒被填 ⇒ 撞不到。**測試的時序不對。**
2. T009：攻擊**打錯路徑**（非串流 vs 串流）⇒ 改的程式碼測試根本不會執行。
3. （spec 043 那次）攻擊本身是 **no-op**。

⇒ 撞不紅有**三種**原因：測試沒牙齒／攻擊沒實作／**攻擊打錯地方**。
前兩種既有教訓有講，第三種是新的。
