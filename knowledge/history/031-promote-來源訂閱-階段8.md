# 031：promote 來源訂閱 → vision 階段 8
> 日期：2026-07-25

## 轉移
`/knowie-next` 規劃後使用者確認 promote。延續使用者的「管理/策展」線（收進→KB 管理→來源）。

- **vision 階段 8（已 commit）**：web `/sources` 自助加來源（貼 RSS/站台 URL→RSS 探測→加前驗證
  有料）＋列出/停用/刪除。＝第三種追蹤粒度（站台/作者＝持續水源，原則 5 人冊封）。
- 合流兩 draft：`來源訂閱`（主）＋`知識庫管理` 的來源管理面。
- 部署段（容器化/K8s/Helm）改為**後續、不綁階段號**（孵化中），停止編號被擠的 churn。

## 現成關鍵（照 code 驗）
- **`build_adapters(sources)` 已吃 DB sources**（fetchers.py）→ 加來源進 `sources` 表即被 digest
  抓取，**抓取管線零改**。RssAdapter 可注入 fetch（離線測）。upsert_source/set_source_enabled/
  list_sources 現成；`/library`/`/interests` CRUD 樣式現成。
- 新增：RSS 自動探測、加前驗證有料、`delete_source`、`/sources` 頁。

## 範圍
先做 **RSS**（有 feed 的站，最現成）；**無 RSS 站的 email-ingestion／作者跨平台／每來源品質
加權 → 後續**。`evaluate-and-add-source` skill 續為 AI 版後備。

## 下一步
`/speckit-specify`。cautions：教訓 1（探測/驗證離線可注入）、教訓 3（死 feed 友善不加壞）、
教訓 7 第四面（加前驗證做進程式，不靠使用者保證 URL 對）、教訓 8（復用 sources 表）。

## 狀態
✅ 已 promote（使用者 2026-07-25 確認）
