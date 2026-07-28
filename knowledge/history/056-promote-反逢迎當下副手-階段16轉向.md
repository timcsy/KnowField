# 056：promote 反逢迎的當下副手（時刻 A）→ vision 階段 16（產品轉向）

> 日期：2026-07-28　｜　承接 history（capture `反逢迎的當下副手` draft）＋賭注 A 手動探針

## 轉移
北極星從「**你要去照顧的知識庫／目的地**」轉向「**當下能問、不順著你走的副手**」。
promote `draft/2026-07-28-反逢迎的當下副手.md` 的第一塊（時刻 A：值不值得 follow）→
**vision 階段 16（產品轉向點）**。使用者拍板「promote 並跑 speckit」。

## 為何現在 promote（不是又拿批准當訊號）
先用**手動探針**驗**賭注 A**（一份誠實的「值不值得＋真實心得＋怎麼用」到底有沒有幫到你）——
對 Claude Opus 5 那則跑完，使用者答「**有用**」。這才過 experience 教訓「提案-批准 ≠ 打到需求」
要的**真實訊號**，才 promote。探針同時**撞出兩個真風險**（見下），是光靠點頭永遠不會浮現的。

## 探針暴露的兩個真實風險（使用者親點，納入階段 16 驗收）
1. **取得網站內容**：WebFetch 抓 iThome 吃 **403**，退回 curl＋UA 才成；牆內（FB/Threads）伺服器
   更抓不到 → **收內容口**（客戶端送標題＋內文），伺服器抓＝best-effort。＝設計 B「收網址 vs 收內容」。
2. **Web Search 關鍵字**：綜合有料是因為 query 專打「心得/批評/怎麼用」（review Reddit、vs 對手
   complaints、worth it hacker news limitations），非查通用名 → 後端要會**生成獵心得多角度 query**。

## 範圍（階段 16 驗收見 vision）
- MVP：手機丟新東西 → 獵心得 → 反逢迎綜合（官方/獨立/用戶分開、明說炒作、有引用）。
- 手機可達＝**最便宜 tunnel**（cloudflared），**out：容器化/K8s/Helm**（`部署與介面路線` 已擱置）。
- 手動探針＝參考實作／可執行規格：fetch(or 收內容)→ 獵心得 query → 反逢迎綜合。
- **真驗收超越測試綠**：一週內使用者自己伸手用幾次。
- out：場驅動關聯（fast-follow）、收進捕捉 extension（設計 B 後續）、moment B/C。

## 出口
- `反逢迎的當下副手` draft 標此塊為 in-flight（雙向連結），待做完反流退場。
- 下一步：`/speckit-specify` 開 spec 021。複用 make_web_search／make_answerer／expand.py。
- 相關：experience「提案-批准 ≠ 打到需求」、principle 6（過度擬合檢查）、`轉向場的護城河` 設計 B
  （收內容口）、`部署與介面路線`（tunnel vs K8s）、spec 009/011/016（web 搜尋/擴展/news）。
