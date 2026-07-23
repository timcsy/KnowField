"""OpenAI 格式後端：解析回應、正規化、後端選擇（mock，不打真實 API）。"""

import math
import unittest

from learnnews.backends import openai_api
from learnnews.backends.factory import make_embedder, make_summarizer
from learnnews.config import Config
from learnnews.ranking.embeddings import HashingEmbedder
from learnnews.summarize.llm import StubSummarizer


class TestOpenAIBackend(unittest.TestCase):
    def setUp(self):
        self._orig = openai_api._post

    def tearDown(self):
        openai_api._post = self._orig

    def test_embedder_normalizes(self):
        openai_api._post = lambda *a, **k: {"data": [{"embedding": [3.0, 4.0]}]}
        emb = openai_api.OpenAIEmbedder("http://x/v1", "k", "text-embedding-3-small")
        vec = emb.embed("hello")
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in vec)), 1.0, places=6)
        self.assertEqual(emb.dim, 2)

    def test_summarizer_parses_two_lines(self):
        openai_api._post = lambda *a, **k: {
            "choices": [{"message": {"content": "定位一句\n為何值得看一句"}}]}
        s = openai_api.OpenAISummarizer("http://x/v1", "k", "gpt-4o-mini")
        positioning, why = s.summarize("標題", "摘要", "agent")
        self.assertEqual(positioning, "定位一句")
        self.assertEqual(why, "為何值得看一句")

    def test_summarizer_strips_scaffold_labels(self):
        # 模型把「第一行＝」「為何值得看：第二行：」等鷹架吐出來 → 應剝除
        openai_api._post = lambda *a, **k: {"choices": [{"message": {"content":
            "第一行＝這篇在談 RL 潛在推理\n第二行：值得看它的效率延展性"}}]}
        s = openai_api.OpenAISummarizer("http://x/v1", "k", "m")
        positioning, why = s.summarize("t", "a", "LLM 推理")
        self.assertEqual(positioning, "這篇在談 RL 潛在推理")
        self.assertEqual(why, "值得看它的效率延展性")

    def test_clean_line_variants(self):
        self.assertEqual(openai_api._clean_line("第一行：內容"), "內容")
        self.assertEqual(openai_api._clean_line("定位＝內容"), "內容")
        self.assertEqual(openai_api._clean_line("1. 內容"), "內容")
        self.assertEqual(openai_api._clean_line("正常一句話"), "正常一句話")

    def test_factory_offline_without_key(self):
        cfg = Config(backend="offline")
        self.assertIsInstance(make_embedder(cfg), HashingEmbedder)
        self.assertIsInstance(make_summarizer(cfg), StubSummarizer)

    def test_factory_openai_with_key(self):
        cfg = Config(backend="openai", api_key="sk-x")
        self.assertIsInstance(make_embedder(cfg), openai_api.OpenAIEmbedder)
        self.assertIsInstance(make_summarizer(cfg), openai_api.OpenAISummarizer)

    def test_article_writer_uses_configured_language(self):
        captured = {}

        def fake_post(base, path, key, payload, timeout=60):
            captured["payload"] = payload
            return {"choices": [{"message": {"content": "文章"}}]}

        openai_api._post = fake_post
        w = openai_api.OpenAIArticleWriter("http://x/v1", "k", "m", lang="日本語")
        w.write_article("t", "a", "agent")
        system_msg = captured["payload"]["messages"][0]["content"]
        self.assertIn("日本語", system_msg)   # 指定語言進入提示

    def test_article_backend_default_language_is_zh(self):
        from learnnews.backends.factory import make_article_backend
        w = make_article_backend(Config(backend="openai", api_key="sk-x"))
        self.assertEqual(w.lang, "繁體中文")  # 預設繁中（FR-010）


if __name__ == "__main__":
    unittest.main()
