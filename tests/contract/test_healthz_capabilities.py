"""契約：`/healthz` 要說得出「哪些能力是活的」。

⚠️ 這條測試的由來：spec 037（簡→繁）上線之後**在 prod 完全沒作用**——OpenCC 被我放進
可選 extra，Dockerfile 只裝 `.[web]`，於是 identity fallback 生效：不轉換、不報錯、
`/healthz` 照樣回 `{"ok": true}`。**一個對「功能是不是啞的」不敏感的健康檢查，
沒有在檢查健康。** 這也是 history/087 坑 2（httpx 只在 dev extra）的原樣重演。
"""
import unittest

from fastapi.testclient import TestClient

from tests.web_helpers import build_app, temp_db


class TestHealthzCapabilities(unittest.TestCase):
    def test_reports_capabilities(self):
        c = TestClient(build_app(temp_db()))
        d = c.get("/healthz").json()
        self.assertTrue(d["ok"])
        self.assertIn("capabilities", d)

    def test_s2t_capability_reflects_engine(self):
        """簡→繁引擎在不在，健康檢查要說得出來。"""
        from knowfield.text import s2t
        d = TestClient(build_app(temp_db())).get("/healthz").json()
        self.assertEqual(d["capabilities"]["s2t"], s2t.available())

    def test_capability_flips_when_engine_missing(self):
        """⚠️ 有牙齒的部分：引擎不可用時這個旗標必須變 False。

        不會變的旗標等於沒有旗標——那正是原本 `{"ok": true}` 的問題。
        """
        import knowfield.text.s2t as mod
        orig, orig_loaded = mod._load_converter, mod._LOADED
        mod._load_converter = lambda: None
        mod._LOADED = False
        try:
            d = TestClient(build_app(temp_db())).get("/healthz").json()
            self.assertFalse(d["capabilities"]["s2t"])
            self.assertTrue(d["ok"], "能力缺席不等於服務掛掉——ok 仍為真")
        finally:
            mod._load_converter, mod._LOADED = orig, False

    def test_no_secrets_leaked(self):
        """健康檢查免登入可探 → 不得洩漏設定內容。"""
        d = TestClient(build_app(temp_db())).get("/healthz").json()
        blob = str(d).lower()
        for bad in ("key", "secret", "token", "password", "dsn", "postgres://"):
            self.assertNotIn(bad, blob)
