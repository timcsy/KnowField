# 任務：整理台（階段 45）

**Spec**: [spec.md](spec.md)

## 後端

- [x] T001 `digest_entries.domain_id`（`_ADD_COLUMNS`，沿用 spec 044 的加欄路徑）
- [x] T002 [測試先行] `tests/unit/test_batch_move.py`（9 條）
- [x] T003 `_KIND_TABLE` 改成 `kind → (表, 鍵欄位)`；來源的鍵是 **url**
- [x] T004 `_neighbours` 加來源兩向（冊封自它的理解、帶著它開的對話）
      ⚠️ `source_entry_id` 預設 0 不是 NULL → 用 `> 0` 過濾
- [x] T005 `batch_tangles`（同批排除 ＋ 去重）／`batch_move`（連帶只一層）
- [x] T006 `GET /api/knowledge/inventory`（四種扁平清冊）
- [x] T007 `POST /api/knowledge/tangles` ／ `/move`；**刪掉單件那兩支**（FR-009）
- [x] T008 遷移 `test_tangle.py`／`test_tangle_api.py` 到批次路徑（不是刪掉）
- [x] T009 [測試先行] `tests/contract/test_organizer_api.py`（6 條）

## 對抗測試（先看它變紅才算數）

- [x] T010 同批不排除 → 2 條紅 ✅
- [x] T011 拿掉去重 → 紅 ✅（⚠️ 第一版 fixture 沒造出重複，攻擊是 no-op，修過 fixture 才打得到）
- [x] T012 連帶改遞迴 → 2 條紅 ✅
- [x] T013 來源改用 `id` 當鍵 → 2 條紅 ✅

## 前端

- [x] T014 `api.ts`：`inventory`／批次 `tangles`／`moveKnowledge`；`KnowledgeItem` 型別
- [x] T015 `lib/knowledge.ts` ＋ 測試（6 條）——⚠️ 選取鍵必須含 kind，否則文章#5 與理解#5 會撞
- [x] T016 整理台版面：左樹（放置目標）／右清冊（四種分段 ＋ 篩選）／多選操作列
- [x] T017 拖放用 **Pointer Events**，不是 HTML5 DnD
      ⚠️ HTML5 DnD 在觸控裝置完全不觸發，而這是 PWA——手機上會安靜地不能拖
- [x] T018 `renderRow`／`renderNode` 從元件內部搬出來
      ⚠️ 定義在 render 裡的 JSX 元件每次 render 都是新型別 → 整棵子樹重掛，拖曳時卡死

## 驗收

- [x] T019 627 後端測試綠、26 前端測試綠、`npm run build` 綠
- [x] T020 實跑：清冊 105 件四種齊全；批次搬 3 個來源 → **224 塊全部**帶上領域（FR-008）；
      拖放真的生效（數學 0→1）；同批不算糾纏 vs 單搬報 1 條，兩邊都對
