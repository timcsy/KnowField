# 085：單人 Google 登入門鎖——部署上「不被看光」（階段 32 程式側完成）

> 日期：2026-08-07。**功能完成轉移**。設計源 `draft/2026-07-23-部署與介面路線`（A 登入牆＋②節）；
> spec/plan＝`specs/035-google-login-gate/`；promote＝vision 階段 32（接 /knowie-next）。接階段 31 PG substrate。

## 做了什麼
`web/auth.py setup_auth`：SessionMiddleware（httponly）＋gate middleware＋`/auth/login|callback|logout`（Authlib
Google OIDC）。未登入 `/api`→401、頁→302 導 `/auth/login`；callback 取 email 比對 **allowlist**、非白名單拒、不建 session。
前端 `/api` 401→導登入（session 過期不卡壞畫面）。352 測綠（344＋8 新）、零回歸。

## 關鍵設計：啟用條件＝config 存在性（零回歸的鑰匙）
**auth 只在「allowlist＋Google client 憑證」都設了時啟用**（`auth_active`）。既有 344 個 build_app 測試沒設這些 env
→ gate 不掛 → 全開 → **零回歸、不用動任何既有測試**。dev bypass `KNOWFIELD_AUTH_DISABLED=1` 強制關（防設錯把自己鎖死）。
→ 這是「新增全域攔截但不驚動既有測試」的通用手法：**用設定存在性當開關，預設關**。

## 實作踩到的 bug（值得記）
- **catch-all mount 遮蔽後註冊的路由**：`/auth/*` 路由原註冊在 SPA `app.mount("/", …)` catch-all **之後** →
  被 "/" 吃掉、callback 沒跑、session 沒建（測試現象：登入後仍 401、Set-Cookie 空）。**gate middleware 擋人有效
  （middleware 在路由前），但具體 /auth 路由被遮**。修：`setup_auth` 移到 SPA mount **之前**。
  教訓：**具體路由必須註冊在 catch-all mount 之前**——已升 experience。

## 邊界：程式完成 ≠ 上線（誠實記）
- **AI 不碰憑證（安全紅線）**：Google Cloud OAuth client 建立＋回呼網址＋同意授權＝**使用者手動**；
  client id/secret、allowlist、session secret 放 env。
- **HTTPS/host＝部署層**：Caddy 自動 TLS＋Helm/host＝ops 後續，非本 spec app 碼。
- ∴ 「不被看光」在 prod 成真，還差**使用者接 Google Cloud＋部署**這一哩。真 Google 帳號登入的端到端驗證＝使用者做。

## 相依/憲章
加 `authlib`＋`itsdangerous`（web deps）；plan 說明必要性（憲章額外限制滿足）。只在 web 層；核心不受影響。

## 產物
spec/plan＝`specs/035-google-login-gate/`；commit `d11b5e0`（實作，352 測綠）。
下游解鎖：文章公開分享（階段 30，gated on 本階段）。範圍外（多租戶/聯邦/公開分享/Helm/領域分類）未引入。
