"""單人 Google 登入門鎖（spec 035，vision 階段 32）。只在 web 層；核心不受影響。

啟用條件：allowlist ＋ Google client 憑證都設了才啟用（`auth_active`）——既有測試/dev 沒設＝全開、零回歸。
dev bypass：KNOWFIELD_AUTH_DISABLED=1 強制關（防設錯鎖死自己）。
隱私＝結構保證（原則 3）：授權判斷在伺服器端 gate、session httponly、密鑰進 env。
測試注入（不打真實 Google）：app.state.oauth_userinfo_for_test → 回 {"email": …}。
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from ..config import Config

_GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"


def allowlist(cfg: Config) -> set[str]:
    return {e.strip() for e in (cfg.auth_allowlist or "").split(",") if e.strip()}


def auth_active(cfg: Config) -> bool:
    """gate 是否啟用：allowlist＋client 憑證都在、且未 dev-bypass。"""
    return bool(
        allowlist(cfg) and cfg.google_client_id and cfg.google_client_secret
        and not cfg.auth_disabled
    )


def setup_auth(app) -> None:
    """掛 SessionMiddleware（永遠）＋ gate（僅啟用時）＋ /auth 路由。在 create_app 尾呼叫。"""
    cfg: Config = app.state.config

    # gate 只在啟用時掛（避免包住既有路由/SSE；未啟用＝既有 344 測零回歸）。
    # 順序：先掛 gate（inner），後掛 Session（outer）→ Session 先跑、gate 讀得到 request.session。
    if auth_active(cfg):
        app.add_middleware(BaseHTTPMiddleware, dispatch=_make_gate(app))
    app.add_middleware(
        SessionMiddleware,
        secret_key=cfg.session_secret or "kf-insecure-dev-key",
        https_only=False,           # HTTPS 由佈署層（Caddy）負責；此旗標不強制 cookie 僅 https（本機可測）
        same_site="lax",
    )

    # Authlib OAuth（有憑證才註冊；測試走注入、不會真的呼叫）
    oauth = None
    if cfg.google_client_id and cfg.google_client_secret:
        from authlib.integrations.starlette_client import OAuth
        oauth = OAuth()
        oauth.register(
            name="google",
            client_id=cfg.google_client_id,
            client_secret=cfg.google_client_secret,
            server_metadata_url=_GOOGLE_METADATA,
            client_kwargs={"scope": "openid email profile"},
        )

    @app.get("/auth/login")
    async def auth_login(request: Request):
        if getattr(app.state, "oauth_userinfo_for_test", None) is not None:
            return RedirectResponse("/auth/callback")   # 測試/離線：跳過真 Google
        redirect_uri = request.url_for("auth_callback")
        return await oauth.google.authorize_redirect(request, str(redirect_uri))

    @app.get("/auth/callback", name="auth_callback")
    async def auth_callback(request: Request):
        inj = getattr(app.state, "oauth_userinfo_for_test", None)
        if inj is not None:
            userinfo = inj(request) if callable(inj) else inj
        else:
            token = await oauth.google.authorize_access_token(request)
            userinfo = token.get("userinfo") or {}
        email = ((userinfo or {}).get("email") or "").strip()
        if email and email in allowlist(app.state.config):
            request.session["user"] = email          # 只存授權 email；不落庫（單人、無使用者表）
            return RedirectResponse("/")
        # Google 認得你 ≠ 本站授權你：非白名單→拒、不建 session、不洩白名單內容
        return JSONResponse({"error": "此帳號未獲授權"}, status_code=403)

    @app.get("/auth/logout")
    async def auth_logout(request: Request):
        request.session.pop("user", None)
        return RedirectResponse("/auth/login")


def _make_gate(app):
    async def gate(request: Request, call_next):
        path = request.url.path
        # 豁免：登入流程本身＋健康檢查（否則無法呈現登入入口）
        if path.startswith("/auth/") or path == "/healthz":
            return await call_next(request)
        user = request.session.get("user")
        if user and user in allowlist(app.state.config):
            return await call_next(request)
        # 未登入/未授權：/api → 401（給 fetch）；其餘 → 302 導登入（結構上擋在伺服器端，非前端藏）
        if path.startswith("/api/"):
            return JSONResponse({"error": "未登入"}, status_code=401)
        return RedirectResponse("/auth/login")

    return gate
