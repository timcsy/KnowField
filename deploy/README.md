# 部署 KnowField 到 K8s（Helm）

單人部署：**app ＋ in-cluster Postgres ＋ Google 登入門鎖**。映像走 **ghcr**，網域/TLS 你自己接（Caddy/ingress 指向 Service）。

## 1. 映像（ghcr）
push 到 `main`（或打 `v*` tag）→ GitHub Actions（`.github/workflows/docker-publish.yml`）自動 build 並推到
`ghcr.io/timcsy/knowfield:latest`（＋ short sha、tag 版本；sha tag 無前綴，與下方手動路徑一致）。

> **⚠ 前置（做過一次就好，2026-08-14 才補上）**：package 若是**本機手動推出來的**，它掛在個人帳號底下、
> **沒有連到 repo** → CI 推不上去（`denied: permission_denied: read_package`／改 public 後變 `write_package`）。
> **改 public 不能解決——那是 pull 權限，這裡缺的是 push 權限。** 正解：
> GitHub → Packages → `knowfield` → **Package settings → Manage Actions access → Add repository**
> → 選 `timcsy/KnowField`、Role 設 **Write**。
> 授權後 CI 推成功一次，`docker/metadata-action` 帶的 `org.opencontainers.image.source` label 會把 package
> **自動連回 repo**，之後就自給自足。
> （這條 README 原本宣稱 CI 會自動 build，實際上**從沒成功過一次**——手動 fallback 一直能用，所以沒人發現。
> 見 `knowledge/history/093`。）

- 叢集拉私有映像用 `imagePullSecret`（本專案為 `ghcr-pull`）；package 設 public 則不需要。
- 本機手動（Mac→amd64 節點）：
  ```bash
  gh auth token | docker login ghcr.io -u <你> --password-stdin   # ⚠ token 會過期，push 前先重登
  SHA=$(git rev-parse --short HEAD)
  docker buildx build --platform linux/amd64 -t ghcr.io/timcsy/knowfield:$SHA -t ghcr.io/timcsy/knowfield:latest --push .
  ```
  > **⚠ 血淚教訓（history/089）**：token 過期時 `buildx --push` 會 **build 成功、push 靜默失敗**，rollout 照樣「成功」但拉到舊映像。
  > 用 **git sha 當 tag**（別只靠 latest），部署後**一定核對 digest**（見第 4 步末）。

## 2. 準備 secrets（別提交真值）
複製一份覆蓋檔，只放密鑰：
```yaml
# my-values.yaml（勿進 git）
postgres:
  password: <長隨機字串>
auth:
  allowlist: "you@example.com"          # 你的 Google email
  googleClientId: "<...>.apps.googleusercontent.com"
  googleClientSecret: "<...>"
  sessionSecret: "<python -c \"import secrets;print(secrets.token_urlsafe(48))\">"
backend:                                 # 你的 OpenAI 相容 gateway（留空=離線 stub）
  apiBase: "https://<你的 gateway>/v1"
  apiKey: "<...>"
image:
  tag: latest                            # 或 sha-xxxx 釘版本
```

## 3. Google Cloud OAuth（手動一次）
OAuth 2.0 用戶端 → 已授權的重新導向 URI 加：`https://<你的網域>/auth/callback`
（本機測試才用 `http://127.0.0.1:8000/auth/callback`）。同意畫面為「測試」時把自己加進測試使用者。

## 4. 安裝
```bash
helm upgrade --install knowfield deploy/helm/knowfield \
  -n knowfield --create-namespace \
  -f my-values.yaml
```
出來的東西：
- `Deployment`（app，1 副本、Recreate）＋ `Service`（ClusterIP，port 80 → 8000）
- `StatefulSet` Postgres ＋ headless Service ＋ PVC（5Gi）
- app media 的 PVC（2Gi）
- 一個 `Secret`（DB DSN＋auth＋gateway）

> **⚠ PG 密碼固定在 PVC**：`postgres.password` 建庫時寫死進 PVC，之後 `helm upgrade` **必須帶同一個值**，
> 否則 app 連不上（history/089 曾因密碼放 /tmp 被清、upgrade 用了預設值把站弄掛）。**寫進你的 `my-values.yaml`，別放 /tmp。**
> 忘了可從舊 ReplicaSet 撈：`kubectl -n knowfield get rs -o jsonpath` 看 `KNOWFIELD_DATABASE_URL`。

**部署後核對真的上新版（別信「rollout 成功」，history/089）**：
```bash
kubectl -n knowfield get pod -l app.kubernetes.io/component=app \
  -o jsonpath='{.items[0].status.containerStatuses[0].imageID}'   # digest 要 ＝ 這次 build 的
```

## 5. 網域/TLS（你自己接）
Service 名稱＝`knowfield-knowfield`（release 名 + chart 名），port 80。把你的 Caddy/ingress 指向它即可。
或啟用內建 ingress：
```yaml
ingress:
  enabled: true
  className: "nginx"        # 或你的 ingress class
  host: "knowfield.example.com"
  tls: true                # 需搭配 cert-manager 之類
```
> HTTPS 必備——沒有的話登入狀態在傳輸中會被看光（見 experience「隱私要在結構上保證」）。

## 6. 驗證
```bash
kubectl -n knowfield get pods            # app 與 postgres 都 Running
kubectl -n knowfield port-forward svc/knowfield-knowfield 8000:80
# 開 http://127.0.0.1:8000 → 應看到登入畫面
```

## 用外部 Postgres（可選）
不想用 chart 內建 PG：
```yaml
postgres:
  enabled: false
externalDatabaseUrl: "postgresql://user:pass@your-pg-host:5432/knowfield"
```

## 本地開發：mirrord 讀「線上」場（唯讀，寫入被 DB 拒）
用 mirrord 讓本地程式進到 pod 的網路、讀線上 PG，但用**唯讀 role** → 寫入被資料庫拒絕（結構保證，不靠自律）。

一次性：在 PG 建唯讀 role（已建 `mirrord_ro`；重建時）：
```sql
CREATE ROLE mirrord_ro LOGIN PASSWORD '<pw>';
GRANT CONNECT ON DATABASE knowfield TO mirrord_ro;
GRANT USAGE ON SCHEMA public TO mirrord_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mirrord_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mirrord_ro;
```
本地跑（`-t` 指部署，程式經 pod 網路連 in-cluster PG service）：
```bash
export MIRRORD_DEMO_DSN="postgresql://mirrord_ro:<pw>@knowfield-knowfield-postgres:5432/knowfield"
mirrord exec -t deployment/knowfield-knowfield -n knowfield -- .venv/bin/python your_script.py
```
> 鐵律：**dev 只讀線上、絕不寫**——唯讀 role 讓它結構上成立（見 experience「隱私/唯讀要做進結構」）。
> 要重度改資料的開發，走本地 SQLite（`KNOWFIELD_DATABASE_URL=` 留空），別碰線上。

## 備份（你的全部家當）
內建 PG 的資料在它的 PVC。定期 `pg_dump` 出來（可另開一支 CronJob）。media PVC 同理。


## 部署後核對（兩件，缺一不可）

1. **pod 實際 digest ＝ 這次 build**——別信 `rollout successfully`（`history/089`，燒過一小時）。
2. **`/healthz` 的 `capabilities` 全為預期值**——digest 對了功能仍可能是啞的：
   可選相依沒進執行期時，可插拔介面會靜默降級（`history/099`，spec 037 上線後在 prod 完全沒作用）。

```bash
POD=$(kubectl -n knowfield get pod -l app.kubernetes.io/component=app -o jsonpath='{.items[0].metadata.name}')
kubectl -n knowfield get pod $POD -o jsonpath='{.status.containerStatuses[0].imageID}{"\n"}'
kubectl -n knowfield exec $POD -- python -c \
  "import urllib.request,json;print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/healthz')))"
```
