"""T025 後記：相關度門檻依 embedder 尺度校準（experience 教訓 4）。

真跑實測：text-embedding-3-small 命中≈0.6、無關問題≤0.22；離線雜湊尺度低得多。
故單一固定門檻不可行——真實後端要高門檻（濾噪音＋擋無關），離線要低門檻。
"""

import os
import unittest

from knowfield.config import Config


class TestThresholdCalibration(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in
                       ("KNOWFIELD_BACKEND", "KNOWFIELD_RAG_MINSCORE")}
        os.environ.pop("KNOWFIELD_RAG_MINSCORE", None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_openai_backend_uses_high_threshold(self):
        os.environ["KNOWFIELD_BACKEND"] = "openai"
        c = Config.from_env(dotenv="/nonexistent")
        self.assertGreaterEqual(c.rag_min_score, 0.30)   # 濾鬆散相關、擋無關問題

    def test_offline_backend_uses_low_threshold(self):
        os.environ["KNOWFIELD_BACKEND"] = "offline"
        c = Config.from_env(dotenv="/nonexistent")
        self.assertLessEqual(c.rag_min_score, 0.10)      # 離線雜湊尺度低

    def test_env_override_wins(self):
        os.environ["KNOWFIELD_BACKEND"] = "openai"
        os.environ["KNOWFIELD_RAG_MINSCORE"] = "0.5"
        c = Config.from_env(dotenv="/nonexistent")
        self.assertEqual(c.rag_min_score, 0.5)


if __name__ == "__main__":
    unittest.main()
