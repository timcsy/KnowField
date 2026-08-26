# 任務：滑動不是點選（階段 54）

- [x] T001 `lib/tap.ts` ＋ 測試（6 條）：`isTap(start, end, slop=10)`
      ⚠️ 沒有起點時回 `true`（fail-open）——吃掉合法點擊比放行誤觸更糟
- [x] T002 所有列在 `pointerdown` 記下位置，`onClick` 先過 `isTap`
- [x] T003 ⚠️ `beginDrag` 觸控直接 return——捲動會誤觸拖放，而代價是**悄悄搬走知識**
- [x] T004 長按選單補「搬到…」，否則手機上搬不動東西

## 驗收（390px iframe 模擬手機視埠）

- [x] T005 703 後端測試綠、47 前端測試綠、`npm run build` 綠
- [x] T006 實跑三條：
      滑動 60px → **不開啟** ✅ ／ 原地按放 → **開啟**（`/domains` → `/`）✅ ／
      從項目捲到資料夾列放開 → **不搬、不跳糾纏詢問** ✅
- [x] T007 ⚠️ 過程中我的**檢查**錯過一次：量 `location.search` 找 `resume=`，
      但 ChatPage 開啟後就把它清掉了 ⇒ 誤判成「點選也壞了」。改量 `pathname` 才對。
