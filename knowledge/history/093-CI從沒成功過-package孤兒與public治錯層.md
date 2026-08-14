# 093：CI 從沒成功過——package 孤兒，且「改 public」治的是錯的那一層

> 日期：2026-08-14。承 `history/092` 的部署動作。由來：部署時照 `history/089` 的規矩查 CI，
> 才發現 `gh run list --workflow=docker-publish.yml` **只有一筆執行紀錄**（就是這次 push 觸發的），而且失敗。
> ＝ `deploy/README` 第 1 節宣稱的「push 到 main → CI 自動 build 並推 ghcr」**從來沒發生過**。

## 一、為何沒人發現：fallback 一直能用

線上 pod 的 tag 是 `988cdd2` 這種**無 `sha-` 前綴**格式＝README 第 1 節後半那條「本機手動 `$SHA`」路徑的產物
（CI 的 `type=sha,format=short` 會產出 `sha-xxxxxxx`）。**每次部署都走手動、每次都成功，所以文件的謊沒被戳破。**
這是「**主動審計才照得出累積型的漏**」的又一例——它不在任何一步的當下，在「一直沒人去看那一格」。

## 二、根因：package 是孤兒

`gh api user/packages/container/knowfield` → **`repository: （無）`**。
package 當初由本機 PAT 推出來，掛在個人帳號 namespace 下、**與 `timcsy/KnowField` 沒有關聯**；
workflow 的 `permissions: packages: write` 給的是「這個 repo 的 token 有推 package 的能力」，
但**前提是那個 package 認得這個 repo**——它不認得。

## 三、⚠ 「改 public」治錯層（實測，非推理）

使用者選擇直接把 package 改 public。**預測它治不到**（public 管 pull，錯誤發生在 push），
但**沒有爭論、直接 rerun 實測**（呼應 `history/092` 當天才學到的教訓）：

| | 錯誤 |
|---|---|
| private 時 | `denied: permission_denied: **read_package**` |
| **改 public 後** | `denied: permission_denied: **write_package**` |

→ **可見性讓它讀得到了，寫入權限完全沒動。** 預測成立，但關鍵是它是**被實測確認的**，不是被辯論贏的。
一般化：**visibility ≠ permission**；讀寫是兩套 ACL，看錯 verb 就會修錯層。

## 四、正解與自癒

GitHub → Packages → `knowfield` → **Package settings → Manage Actions access → Add repository**
→ `timcsy/KnowField`、Role **Write**（預設 Read 不夠）。→ rerun → **success**。

**授權後會自我修復**：`docker/metadata-action` 產生的 `org.opencontainers.image.source` label
（workflow 早就有 `labels: ${{ steps.meta.outputs.labels }}`，只是推不上去用不到）在推成功那一刻
把 package **自動連回 repo** —— 驗證：事後 `repository: timcsy/KnowField`。**雞生蛋只需要人破一次。**

## 五、順手對齊

- workflow `type=sha,format=short,prefix=`（拿掉 `sha-`）→ CI 與手動路徑**同一種 tag 格式**，
  `kubectl set image` 不會因為前綴半夜出錯。
- `deploy/README` 第 1 節補上「前置授權」警告，並明說**改 public 不能解決**（那是 pull 權限）。

## 六、本次部署的既成事實

線上跑的是**手動推的** `1677060`（digest `sha256:7bb53ac8…`，已核對 pod imageID 一致、`healthz` 200、
`exec` 進 pod 確認 `_MEMBRANE` 含長度紀律）。CI 後來也產出同內容的 `sha-1677060`／`main`／`latest`。
**下次部署起用 CI 的 tag。**
