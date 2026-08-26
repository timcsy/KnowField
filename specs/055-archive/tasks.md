# 任務：封存（階段 50）

**Spec**: [spec.md](spec.md)

## 後端

- [x] T001 `archived_at`／`archived_root` 加到 domains ＋ 四種知識表（沿用 spec 044 加欄路徑）
- [x] T002 [測試先行] `tests/unit/test_archive.py`（12 條，含 **sweep**）
- [x] T003 `archive_knowledge` / `restore_knowledge` / `archived_items`
- [x] T004 `archive_domain`（**整棵子樹一起**，不上移）／`restore_domain`（只復原同一批）
- [x] T005 ⚠️ **每一份活的清單都要過濾**——少一處就是沉默失敗：
      `list_domains`／`list_why_nodes`／`list_articles`／`list_conversations`／
      `list_source_groups`／`_inventory_rows`／`list_seeds`／`_anointed_corpus_entries`／
      `why_node_provenance`／`conversation_yield_counts`／`conversation_referrers`
- [x] T006 三處硬 DELETE 改成封存：`delete_why_node`／`delete_article`／`delete_conversation`
      ＋ `delete_source`（來源）。⚠️ embedding **照樣清掉**，否則檢索仍命中
- [x] T007 路由：`/api/knowledge/{archive,restore}`、`/api/domains/{did}/{archive,restore}`、
      `/api/domains/{did}/archive-preview`、`/api/archived`
- [x] T008 [測試先行] `tests/contract/test_domain_archive_api.py`（5 條）

## 對抗測試（先看它變紅）

- [x] T009 只擋畫面、不擋檢索（吸引子語料不濾）→ 2 條紅 ✅
- [x] T010 種子語料不濾 → 2 條紅 ✅
- [x] T011 封存領域時知識上移（回到被推翻的語意）→ 3 條紅 ✅
- [x] T012 復原時把所有遺骸都帶回來（不分批）→ 紅 ✅

## 前端

- [x] T013 `刪除 → 封存`（📦）：領域管理頁、對話選單、理解、應用、來源
- [x] T014 ⚠️ 掃掉「不可復原」那類文案——**現在那句話是假的**，
      文案跟行為不一致比舊行為更糟
- [x] T015 遺骸區塊「📦 已封存」：列出封存過的領域與知識、可**復原**
      ——⚠️ 沒有這一格，「封存」在使用者眼裡就等於「刪除」

## 驗收

- [x] T016 685 後端測試綠、36 前端測試綠、`npm run build` 綠
- [x] T017 實跑封存「生成模型」：子樹一起成為遺骸（8 件知識 ＋ 1 個子領域）
- [x] T018 ⚠️ 實跑**檢索**：活的吸引子語料 **549 → 496 → 549**（封存真的擋住檢索，
      不只擋住畫面；復原後完整回來）✅
