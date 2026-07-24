# 020：promote RAG MVP → 復活階段 4（個人知識庫）
> 日期：2026-07-24

## 轉移
跑 `/knowie-next` 排 RAG MVP，前置條件照 code 驗完（語料已落庫、embed_many/cosine/summarizer
現成；缺口：schema 無 embedding 欄、無「取全部 entries」查詢）。使用者確認 promote。

- **vision 階段 4**「知識沉澱」（原降級）→ **復活為「個人知識庫（可 RAG 問答）」**，切三增量：
  - 增量 1（MVP，**已 commit**）：RAG over 流——對已落庫每日匯整可溯源問答（問今天＋問累積）。
  - 增量 2（未 commit）：種子 ingest＋解說文來源類＋根因萃取。
  - 增量 3+（未 commit，concept 驅動）：吸引子拓撲／成核／衰減／反濾泡。
- **雙向連結**：vision 階段 4 ↔ `draft/2026-07-24-RAG問答.md`（draft 不刪，續作 in-flight 理由）。
- 驗收標準寫進 vision（只據語料＋掛來源、查無說無、批次嵌入落庫、離線 stub 綠燈、不回歸）。

## 為何是「復活」非新階段
「有吸引子的場」concept 把原本模糊的「知識沉澱」形狀鑿清楚了＝可 RAG 問答的個人 KB。故不
另開階段，直接讓降級的階段 4 以新形態重啟。增量 1 只鋪「流＋檢索」地板，吸引子/根因是後續。

## 下一步
`/speckit-specify` 開增量 1 規格，走 TDD。knowie-next 簡報的三視角 cautions 帶入規格：
原則 3（掛來源鐵律）、教訓 1（離線 stub）、教訓 3（攔 OpenAIError）、教訓 4（雜湊碰撞 fixture）。

## 狀態
✅ 已 promote（使用者 2026-07-24 確認）
