# 029：promote 知識庫管理 → vision 階段 7
> 日期：2026-07-25

## 轉移
`/knowie-next` 規劃後使用者確認 promote。使用者問「前端能不能有管理功能」，點破缺口：
**工具全是進水（digest/pull/ingest/訂閱），沒有修剪**——能加不能瀏覽/刪/改已收的。

- **vision 階段 7（已 commit）**：web `/library` 管理**種子**——瀏覽／刪除／重分類（解說文↔一般）。
- 部署（原 draft 的 7-9 容器化/K8s/Helm）順延為 8-10（仍孵化）。

## 核心洞見（為何值得做）
**管理＝原則 5 的「另一半」**：人冊封不只**加**吸引子，也含**退**吸引子、**改**權重。
concept 上＝**人工修剪場**（退信錯的吸引子＝手動衰減）。沒有修剪，KB 遲早變雜物抽屜。
它也補上「場的生命週期」缺的一角：進水→冊封→讀→**修剪**。

## 前置（照 code 驗，spec 要處理）
- 現成：`list_corpus_entries`（帶 source_class）、`/interests` web CRUD 樣式、interests service。
- 新增：`list_seeds`、`delete_corpus_entry`（連 entry_embeddings 清，教訓 8）、`set_source_class`；
  `/library` 頁＋POST 路由。

## 範圍
只碰**種子**（每日流條目唯讀）；**來源管理**耦合 `來源訂閱` draft，緊接其後、共用 `/library` 模式。

## 下一步
`/speckit-specify` 開規格。cautions：教訓 8（刪除連清嵌入免孤兒）、教訓 1（離線可測）、
原則 5＋憲章 VI（主權含刪除）。

## 狀態
✅ 已 promote（使用者 2026-07-25 確認）
