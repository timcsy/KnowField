"""單人 Google 登入門鎖（spec 035，vision 階段 32）。離線注入身分、不打真實 Google。
守衛：未登入真被擋（負向測試，別信自報的綠）；非 allowlist 拒；session httponly；dev bypass；未設＝全開。"""

import os
import unittest

from fastapi.testclient import TestClient

from tests.web_helpers import build_app, temp_db

_AUTH_ENV = {
    "KNOWFIELD_AUTH_ALLOWLIST": "me@example.com",
    "KNOWFIELD_GOOGLE_CLIENT_ID": "test-client",
    "KNOWFIELD_GOOGLE_CLIENT_SECRET": "test-secret",
    "KNOWFIELD_SESSION_SECRET": "test-session-secret",
}


def _restore(saved):
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


class TestLoginGate(unittest.TestCase):
    """auth 啟用（設了 allowlist＋憑證）。"""

    def setUp(self):
        keys = list(_AUTH_ENV) + ["KNOWFIELD_AUTH_DISABLED"]
        self._saved = {k: os.environ.get(k) for k in keys}
        os.environ.update(_AUTH_ENV)
        os.environ.pop("KNOWFIELD_AUTH_DISABLED", None)

    def tearDown(self):
        _restore(self._saved)

    def _app(self, identity=None):
        app = build_app(temp_db())
        if identity is not None:
            app.state.oauth_userinfo_for_test = (lambda req, e=identity: {"email": e})
        return app

    def _login(self, client):
        client.get("/auth/login", follow_redirects=True)   # 注入身分→callback→建 session

    def test_unauthed_page_redirects_to_login(self):       # 未登入訪頁→導登入
        c = TestClient(self._app("me@example.com"), follow_redirects=False)
        r = c.get("/")
        self.assertIn(r.status_code, (302, 307))
        self.assertIn("/auth/login", r.headers["location"])

    def test_unauthed_api_blocked_401(self):               # 負向測試（FR-010）：未登入 /api 真的被擋
        c = TestClient(self._app("me@example.com"), follow_redirects=False)
        self.assertEqual(c.get("/api/roots").status_code, 401)

    def test_non_allowlist_rejected(self):                 # 非白名單→拒、不建 session（FR-002）
        c = TestClient(self._app("stranger@evil.com"), follow_redirects=False)
        r = c.get("/auth/login", follow_redirects=True)
        self.assertEqual(r.status_code, 403)               # callback 拒
        self.assertEqual(c.get("/api/roots").status_code, 401)   # 仍未授權

    def test_allowlist_login_grants_access(self):          # 本人→建 session→全站可用（FR-003）
        c = TestClient(self._app("me@example.com"))
        self._login(c)
        self.assertEqual(c.get("/api/roots").status_code, 200)

    def test_logout_clears_session(self):                  # 登出→清 session→再訪被擋（FR-006）
        c = TestClient(self._app("me@example.com"))
        self._login(c)
        self.assertEqual(c.get("/api/roots").status_code, 200)
        c.get("/auth/logout", follow_redirects=False)
        self.assertEqual(
            TestClient(self._app("me@example.com"), cookies=None).get(
                "/api/roots", follow_redirects=False).status_code, 401)

    def test_session_cookie_httponly(self):                # session cookie httponly（FR-004，防前端竊取）
        c = TestClient(self._app("me@example.com"))
        r = c.get("/auth/callback", follow_redirects=False)   # 注入身分→建 session→Set-Cookie
        set_cookie = r.headers.get("set-cookie", "")
        self.assertIn("session=", set_cookie)
        self.assertIn("httponly", set_cookie.lower())


class TestAuthGatingConfig(unittest.TestCase):
    """啟用條件：未設＝全開（既有測試零回歸）；dev bypass＝強制關。"""

    def test_inactive_when_unconfigured(self):             # 沒設 allowlist/憑證→gate 不啟用→全開
        saved = {k: os.environ.get(k) for k in _AUTH_ENV}
        for k in _AUTH_ENV:
            os.environ.pop(k, None)
        try:
            c = TestClient(build_app(temp_db()), follow_redirects=False)
            self.assertEqual(c.get("/api/roots").status_code, 200)   # 無門鎖
        finally:
            _restore(saved)

    def test_dev_bypass_forces_open(self):                 # KNOWFIELD_AUTH_DISABLED=1→即使設了憑證也全開（防鎖死）
        keys = list(_AUTH_ENV) + ["KNOWFIELD_AUTH_DISABLED"]
        saved = {k: os.environ.get(k) for k in keys}
        os.environ.update(_AUTH_ENV)
        os.environ["KNOWFIELD_AUTH_DISABLED"] = "1"
        try:
            c = TestClient(build_app(temp_db()), follow_redirects=False)
            self.assertEqual(c.get("/api/roots").status_code, 200)   # bypass
        finally:
            _restore(saved)


if __name__ == "__main__":
    unittest.main()
