# 實作計畫：單人 Google 登入門鎖

**Spec**: [spec.md](./spec.md) · **憲章 III（spec-driven）＋ I（TDD）**

## 相依必要性（憲章額外限制：新增第三方相依 MUST 說明必要性）
- **新增 `authlib`（Google OIDC 流程）＋ `itsdangerous`（Starlette SessionMiddleware 簽章 cookie 需要）**。
- **必要性**：vision 階段 32＝讓部署「不被看光」的登入牆。Google OIDC 把憑證安全外包 Google（勝過自刻密碼，
  draft 已否決密碼式）；SessionMiddleware 提供簽章、httponly 的登入狀態（結構保證，非假隱私）。無此二者無法安全實作
  OIDC 流程。**只在 web 層**；核心演算法（chunk/ingest/distill/rag/repository）不受影響、不引入。

## 啟用條件（關鍵：既有 344 測零回歸）
- **auth 只在「allowlist ＋ Google client 憑證」都設了時啟用**（`auth_enabled`）。既有測試/dev 沒設 → gate 不啟用 → 全開、零回歸。
- **dev bypass**（FR-007）：`KNOWFIELD_AUTH_DISABLED=1` 強制關（即使已設憑證）——防設錯把自己鎖死；預設不設＝尊重 auth_enabled。
- 這樣不需動既有 344 個 build_app 測試。

## 設計（只在 web 層）
- **新 `web/auth.py`**：
  - `setup_auth(app)`：掛 `SessionMiddleware`（httponly、session secret 由 env）＋ gate middleware ＋ `/auth/login|callback|logout` 路由。
  - **gate middleware**：`auth_enabled` 時，未登入（session 無授權 email 或不在 allowlist）→ `/api/*` 回 401、其餘 302 導 `/auth/login`；
    豁免 `/auth/*`、`/healthz`。授權判斷純伺服器端（原則 3、FR-005）。
  - **login**：Authlib `authorize_redirect` 導 Google。**callback**：取 userinfo email→比對 allowlist→符合才 `session["user"]=email`、
    否則拒（FR-002）。**logout**：清 session。
  - **測試注入點**（FR-009）：`app.state.oauth_userinfo_for_test`（回 `{"email": …}`）→ callback 用它取身分，繞過真 Google。
- **config.py**：加 `google_client_id/secret`、`auth_allowlist`（逗號分隔 email）、`session_secret`、`auth_disabled`（皆 env、不進 git）。
- **app.py**：`create_app` 尾呼 `setup_auth(app)`。
- **pyproject**：web deps 加 `authlib`、`itsdangerous`。

## 測試（TDD、離線注入、不打真實 Google）
- 新 `tests/test_auth.py`：
  - 未登入訪頁 → 302 導登入；未登入訪 /api → 401（**負向測試，FR-010**）。
  - callback 注入非 allowlist email → 拒、無 session（FR-002）。
  - callback 注入 allowlist email → 建 session → 後續請求可用（FR-003）。
  - 登出清 session → 再訪被擋。
  - session cookie httponly（FR-004）。
  - dev bypass 開 → 全放行；auth 未設 → 不啟用（既有測試行為）。
- 既有 344 測不設 auth env → 不啟用 → 零回歸。

## 使用者手動步驟（AI 不碰憑證，安全紅線）
在 Google Cloud 建 OAuth client、設回呼網址、完成同意授權＝**使用者自己做**；client id/secret、allowlist、session secret 放 env。
HTTPS 由佈署層（Caddy）負責，非本 spec app 碼。

## 驗收
未登入被擋（頁 302／api 401）、非 allowlist 拒、本人可用、session httponly、密鑰不進 git、含未登入被擋負向測試、
既有 344＋新測全綠（不打真實 Google）。範圍外（多租戶/聯邦/公開分享/Helm/領域分類）未引入。
