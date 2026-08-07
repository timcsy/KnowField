# 087：首次部署上線——k3s ＋ ghcr ＋ in-cluster PG ＋ Google 登入（https://know.tew.tw）

> 日期：2026-08-08。**里程碑：從本地工具變成上線服務**。承階段 27（PWA/上線基座）、31（PG substrate）、
> 32（登入門鎖）、33（可攜資料層）。設計源 `draft/2026-07-23-部署與介面路線`（Helm/host 那段，原標「ops 後續」）。
> 這是那條路線的**終局**：使用者的場真的上網、只有他進得來。

## 做了什麼
使用者要「把服務起起來、`.env` 直接帶入、DB 自己想辦法、本地資料也帶入」。交付（ops，非 spec-kit）：
- **映像**：`Dockerfile`（多階段：node build 前端 → python editable，保 src 佈局讓 `_DIST` 解析）→ push `ghcr.io/timcsy/knowfield`
  （docker 已認證，私有映像＋k8s pull secret；GH Actions 也備好但這次直接 buildx 推）。
- **叢集**：k3s（節點 tew，amd64，containerd）。namespace `knowfield`。
- **設定**：`kubectl create secret --from-env-file=.env`（使用者 .env 直接帶入，AI 不讀內容）；DB DSN 由 deployment
  顯式 env 覆蓋（.env 的空值→指向 in-cluster PG）。**安全前檢**：bool 檢查 .env 無 `AUTH_DISABLED=1`（否則 prod 門鎖全關）。
- **Helm chart** `deploy/helm/knowfield`：app Deployment（1 副本 Recreate）＋Service（ClusterIP 80→8000）＋
  StatefulSet Postgres（PVC）＋media PVC＋existingSecret/imagePullSecrets 支援。
- **資料遷移**：本地 `knowfield.db`（SQLite，備份後）→ in-cluster PG。腳本：先 `init_db` 建 schema、再逐表 copy（保 id）、
  修 SERIAL 序列。搬入 why34/來源15/digest_entries626/embeddings799/對話11/文章1。部署 app 讀得到。
- **網域/TLS**：使用者自接 Caddy → `https://know.tew.tw`。

## 踩到的四個坑（都上 prod 才炸、本地/測試照不到）→ 升 experience
1. **映像平台**：Mac build 出 arm64、節點 amd64 → `no match for platform`。修：`buildx --platform linux/amd64`。
2. **執行期 vs 測試相依**：`httpx` 只在 `dev` extra，但 Authlib OAuth client 執行期 import 它 → 本地測綠（測環境有 httpx）、
   prod crash。修：httpx 進 `web` runtime deps。
3. **反向代理 proxy-headers**：Caddy 後面沒開 `--proxy-headers` → `request.url_for` 用內部 http → OAuth redirect_uri 錯
   → `redirect_uri_mismatch`。修：uvicorn `--proxy-headers --forwarded-allow-ips '*'`；實測 redirect_uri=https://know.tew.tw/auth/callback。
4. **init_db 惰性**：schema 首次碰 DB 的請求才建（`/healthz` 不碰）→ 遷移時 PG 空、撲空。修：遷移腳本先 init_db。
5. **latest tag 快取**：`IfNotPresent` 不重拉同 tag → 改版看不到。改 `pullPolicy=Always`。

## 運維注記（留給未來）
- **PG 密碼固定在 PVC**：`helm upgrade` 必須帶同一個 `--set postgres.password`（存 `/tmp/kf_pgpw.txt`／my-values.yaml），
  否則 app 連不上既有 PG。→ chart 可改成「密碼從自動生成的 secret 讀」免每次帶（未做，記著）。
- **使用者手動一哩**：Google Cloud OAuth 重新導向 URI 加 `https://know.tew.tw/auth/callback`（AI 不碰憑證）。
- 改版：buildx --push → `kubectl rollout restart deployment/knowfield-knowfield`。

## mirrord 唯讀開發實測（2026-08-08）
驗證 `draft/2026-08-07-本地SQLite與prod-PG雙後端`＋`history/084/086` 設計的「mirrord 讀遠端、唯讀」那條路：
- PG 建唯讀 role `mirrord_ro`（GRANT SELECT only ＋ default privileges）；`mirrord exec -t deployment/... -- python`
  讓本地程式進 pod 網路連 in-cluster PG。**讀到線上場（why34/digest626/對話12）、寫入被 DB 拒**
  （`permission denied`）＝**結構保證，不靠自律**。mirrord exit 自動清 agent、無殘留。
- 記進 `deploy/README`「本地開發：mirrord 讀線上」。鐵律：dev 只讀線上、要改資料走本地 SQLite。

## 產物
commits `8198de1`（部署基座）、`232bc23`（httpx＋chart existingSecret/pull secret）、`2d2581b`（proxy-headers）。
`deploy/helm/knowfield`、`Dockerfile`、`.github/workflows/docker-publish.yml`、`deploy/README.md`。
下游解鎖：文章公開分享（階段 30，gated on 上線＋auth，現已具備地基）。
