# 任務：出生就歸位（階段 46）

**Spec**: [spec.md](spec.md)

- [x] T001 [測試先行] `tests/unit/test_inherit_domain.py`（18 條）
- [x] T002 `lca_domain`（最近共同祖先，環安全）／`inherited_domain`（出處勝過站的地方）
- [x] T003 `place_new(kind, ref, current)`——出處＝`_neighbours`，一個方法服務三條出生路徑
- [x] T004 [測試先行] `tests/contract/test_inherit_api.py`（7 條）
- [x] T005 `_do_anoint` 接線 ⚠️ **在連結建好之後**（早一步 `_neighbours` 是空的）
- [x] T006 ⚠️ 冊封時**新建**的對話自己也要歸位（`save_conversation` 不帶領域）
- [x] T007 `/api/whynode/anoint`（來源側）也接——只接一支會有一半知識繼續漏掉
- [x] T008 `/api/article/save` 收 `root_ids`／`ext_ids`／`conversation_id` 並歸位
- [x] T009 四支 `/api/ingest/*` 帶當前領域；`ContentIngestResult` 補 `url`
- [x] T010 前端接上 `used_body_ids`／`used_ext_ids`
      ⚠️ 後端一直算得出來，前端從沒接——文章的溯源在傳輸層斷了

## 對抗測試（先看它變紅）

- [x] T011 根領域的出處算一票 → 2 條紅 ✅
- [x] T012 LCA 改成「取第一個」 → 4 條紅 ✅
- [x] T013 `place_new` 移到連結建好之前 → 紅 ✅
      ⚠️ 第一版**沒打到**：測試被 `current` 的退路餵飽，是套套邏輯。改成不送 `domain_id` 才打得到
- [x] T014 只接對話那支、不接 `/api/whynode/anoint` → 紅 ✅
- [x] T015 新建的對話不歸位 → 紅 ✅

## 驗收

- [x] T016 664 後端測試綠
- [x] T017 實跑：站在 Flow Matching 冊封 → 落在 Flow Matching；
      帶著「生成模型」的對話冊封但**故意送 domain_id=3** → 落在 **2**（出處勝過站的地方）✅
