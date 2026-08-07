# 部署 KnowField 到 K8s（Helm）

單人部署：**app ＋ in-cluster Postgres ＋ Google 登入門鎖**。映像走 **ghcr**，網域/TLS 你自己接（Caddy/ingress 指向 Service）。

## 1. 映像（ghcr）
push 到 `main`（或打 `v*` tag）→ GitHub Actions（`.github/workflows/docker-publish.yml`）自動 build 並推到
`ghcr.io/timcsy/knowfield:latest`（＋ `sha-xxxx`、tag 版本）。
- 首次推完，到 GitHub → Packages → 該 package → 設 **Public**，或給叢集一個 `imagePullSecret`（私有時）。
- 本機手動也行：`docker build -t ghcr.io/timcsy/knowfield:latest . && docker push ...`（先 `docker login ghcr.io`）。

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
