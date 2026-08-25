# 任務：整理與糾纏（階段 44）

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## 階段 0：加欄

- [x] T001 `schema.py`：`article_roots` 表 ＋ `_ADD_COLUMNS` 三筆新欄
- [x] T002 `_ensure_columns` 冪等驗證（重跑 `init_db` 不重複加欄）

## 階段 1：文章的來源連結（US1）

- [x] T003 [測試先行] `tests/unit/test_article_links.py`（5 條）
- [x] T004 `generate_article` 回傳 `used_body_ids` / `used_ext_ids`（⚠️ 不動 kind-split）
- [x] T005 `save_article(..., root_ids, ext_ids, conversation_id)` ＋ `article_roots(aid)`
- [x] T006 `/api/article` 帶上 `conversation_id`

## 階段 2：搬動與糾纏（US2、US3）

- [x] T007 [測試先行] `tests/unit/test_tangle.py`（7 條）
- [x] T008 `knowledge_domain` / `set_knowledge_domain` / `_KIND_TABLE`
- [x] T009 `_neighbours`（一跳）＋ `tangles_for`（不同且非空）
- [x] T010 `move_knowledge(bring_along)`（連帶只走一層）
- [x] T011 **對抗測試**：把 `_neighbours` 改成傳遞閉包 → 測試轉紅 ✅
- [x] T012 **對抗測試**：把連帶改成遞迴 → 測試轉紅 ✅

## 階段 3：路由

- [x] T013 [測試先行] `tests/contract/test_tangle_api.py`（5 條）
- [x] T014 `POST /api/knowledge/{kind}/{kid}/tangles`（零副作用）
- [x] T015 `POST /api/knowledge/{kind}/{kid}/move`
- [x] T016 `_knowledge_label` 讓提示塊看得懂是哪一條

## 階段 4：介面

- [x] T017 `api.ts`：`pages.tangles` / `pages.moveKnowledge`
- [x] T018 `DomainsPage`「搬到…」下拉（排除當前領域）
- [x] T019 糾纏提示塊：三按鈕 ＋ 一行但書

## 驗收

- [x] T020 612 後端測試綠、20 前端測試綠、`npm run build` 綠
- [x] T021 實跑：預覽無副作用 ✅／留一條糾纏 ✅／連帶一起搬 ✅（API ＋ 瀏覽器各一次）
