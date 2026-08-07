"""單人 Google 登入門鎖（spec 035，vision 階段 32）。只在 web 層；核心不受影響。

啟用條件：allowlist ＋ Google client 憑證都設了才啟用（`auth_active`）——既有測試/dev 沒設＝全開、零回歸。
dev bypass：KNOWFIELD_AUTH_DISABLED=1 強制關（防設錯鎖死自己）。
隱私＝結構保證（原則 3）：授權判斷在伺服器端 gate、session httponly、密鑰進 env。
測試注入（不打真實 Google）：app.state.oauth_userinfo_for_test → 回 {"email": …}。
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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
        # 登入畫面（未登入被 gate 導來、或被拒導回）：一顆「用 Google 登入」鈕。
        denied = request.query_params.get("error") == "denied"
        return HTMLResponse(_login_page(denied))

    @app.get("/auth/google")
    async def auth_google(request: Request):
        # 實際發起 Google OIDC；測試/離線走注入、跳過真 Google
        if getattr(app.state, "oauth_userinfo_for_test", None) is not None:
            return RedirectResponse("/auth/callback")
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
        # Google 認得你 ≠ 本站授權你：非白名單→拒、不建 session、導回登入頁顯示訊息（不洩白名單內容）
        return RedirectResponse("/auth/login?error=denied")

    @app.get("/auth/logout")
    async def auth_logout(request: Request):
        request.session.pop("user", None)
        return RedirectResponse("/auth/login")

    @app.get("/api/me")
    async def api_me(request: Request):
        # 給前端知道：目前登入者是誰、門鎖有沒有啟用（決定要不要顯示登出）
        return {"user": request.session.get("user"),
                "auth_enabled": auth_active(app.state.config)}


def _login_page(denied: bool = False) -> str:
    """自足登入畫面（pre-auth，後端直接吐；不依賴前端 SPA）。深淺色自適應。"""
    err = ('<p class="err">此帳號未獲授權——請用被允許的 Google 帳號登入。</p>'
           if denied else "")
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>登入 · KnowField</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; min-height:100svh; display:flex; align-items:center; justify-content:center; padding:1.5rem;
    font-family: system-ui, -apple-system, "PingFang TC", "Noto Sans TC", sans-serif;
    background:#fafaf9; color:#1c1917; }}
  .card {{ width:min(94vw,400px); padding:2.6rem 2.2rem; border-radius:1rem; text-align:center;
    background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.08), 0 8px 30px rgba(0,0,0,.06); }}
  h1 {{ margin:.3rem 0 .15rem; font-size:1.6rem; }}
  .tag {{ margin:0 0 1.5rem; font-size:.9rem; color:#78716c; }}
  .feats {{ margin:0 0 1.7rem; padding:1rem 1.1rem; border-radius:.7rem; background:#f5f5f4; text-align:left; }}
  .feat {{ display:flex; gap:.6rem; align-items:flex-start; font-size:.85rem; line-height:1.5; }}
  .feat + .feat {{ margin-top:.6rem; }}
  .feat b {{ font-weight:600; }}
  .btn {{ display:inline-flex; align-items:center; gap:.6rem; width:100%; justify-content:center;
    padding:.7rem 1rem; border-radius:.6rem; border:1px solid #e7e5e4; background:#fff; color:#1c1917;
    font-size:.95rem; font-weight:500; text-decoration:none; cursor:pointer; transition:background .15s; }}
  .btn:hover {{ background:#f5f5f4; }}
  .g {{ width:18px; height:18px; }}
  .foot {{ margin:1rem 0 0; font-size:.72rem; color:#a8a29e; }}
  .err {{ margin:0 0 1rem; padding:.5rem .7rem; border-radius:.5rem; font-size:.8rem;
    background:#fef2f2; color:#b91c1c; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background:#0c0a09; color:#f5f5f4; }}
    .card {{ background:#1c1917; box-shadow:0 1px 3px rgba(0,0,0,.4), 0 8px 30px rgba(0,0,0,.5); }}
    .tag, .foot {{ color:#a8a29e; }}
    .feats {{ background:#292524; }}
    .btn {{ background:#292524; border-color:#44403c; color:#f5f5f4; }}
    .btn:hover {{ background:#44403c; }}
    .err {{ background:#450a0a; color:#fca5a5; }}
  }}
</style></head>
<body><div class="card">
  <div style="font-size:2.6rem">🧠</div>
  <h1>KnowField</h1>
  <p class="tag">反逢迎的當下副手</p>
  <div class="feats">
    <div class="feat"><span>📥</span><span><b>收進你信的來源</b>——文章、論文、對話，沉澱成你的「核心理解」。</span></div>
    <div class="feat"><span>💬</span><span><b>跟你的知識場聊</b>——有話直說、有據可溯，不順著你講好聽話。</span></div>
    <div class="feat"><span>✍️</span><span><b>生成高證實文章</b>——只用已證實/推論、每個引用連回來源。</span></div>
  </div>
  {err}
  <a class="btn" href="/auth/google">
    <svg class="g" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.6 2.4 30.1 0 24 0 14.6 0 6.4 5.4 2.5 13.3l7.8 6c1.9-5.5 7-9.8 13.7-9.8z"/><path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.5 3-2.2 5.5-4.7 7.2l7.3 5.7c4.3-3.9 6.8-9.7 6.8-17.4z"/><path fill="#FBBC05" d="M10.3 28.3c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.8-6C.9 16.3 0 20 0 24s.9 7.7 2.5 10.9l7.8-6z"/><path fill="#34A853" d="M24 48c6.1 0 11.3-2 15-5.5l-7.3-5.7c-2 1.4-4.6 2.2-7.7 2.2-6.7 0-12.4-4.3-14.4-10.1l-7.8 6C6.4 42.6 14.6 48 24 48z"/></svg>
    用 Google 登入
  </a>
  <p class="foot">私人知識場，僅限授權帳號進入</p>
</div></body></html>"""


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
