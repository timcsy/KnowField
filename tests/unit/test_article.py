"""知識的輸出（vision 階段 30）：高證實文章生成。守衛＝正文只採已證實/推論、結構化 References、
類比/猜想隔到延伸閱讀。LLM 注入 stub，測結構不測模型文字。"""
import unittest

from knowfield.output.article import _references, generate_article
from knowfield.rootcause.extract import WhyNode


def _n(claim, kind, ev=""):
    return WhyNode(id=0, claim=claim, kind=kind, evidence_urls=[ev] if ev else [])


class StubChat:
    def __init__(self):
        self.prompt = None

    def reply(self, messages):
        self.prompt = messages[-1]["content"]
        return "正文講 [1]，還有 [2]。"


class TestArticle(unittest.TestCase):
    def test_body_only_evidenced_kinds_analogy_conjecture_to_extended(self):
        nodes = [_n("已證實甲", "已證實", "https://x/a"), _n("推論乙", "推論", "https://x/b"),
                 _n("類比丙", "類比", "https://x/c"), _n("猜想丁", "猜想", "")]
        chat = StubChat()
        out = generate_article("主題", nodes, chat)
        # 正文 prompt 只餵 已證實+推論（編號 [1][2]），不餵 類比/猜想（膜：高證實）
        self.assertIn("已證實甲", chat.prompt)
        self.assertIn("推論乙", chat.prompt)
        self.assertNotIn("類比丙", chat.prompt)
        self.assertNotIn("猜想丁", chat.prompt)
        md = out["markdown"]
        self.assertIn("#### References", md)
        self.assertIn("1. https://x/a", md)                 # 結構化 References（原則 3，非模型自律）
        self.assertIn("2. https://x/b", md)
        self.assertIn("#### 延伸閱讀", md)
        self.assertIn("類比丙", md)                          # 類比/猜想→延伸閱讀、標明
        self.assertIn("💭 猜想", md)

    def test_empty_when_no_evidenced_understanding(self):
        out = generate_article("主題", [_n("只有類比", "類比")], StubChat())
        self.assertTrue(out["empty"])                       # 沒 已證實/推論→不硬寫

    def test_references_structural_and_paste_labeled(self):
        refs = _references([_n("a", "已證實", "https://x/a"), _n("b", "已證實", "paste:xxx")])
        self.assertIn("1. https://x/a", refs)
        self.assertIn("2. （你收藏的來源）", refs)            # 非 http（貼上）→標「你收藏的」

    def test_length_level_in_prompt(self):
        from knowfield.output.article import build_article_prompt
        p = build_article_prompt("主題", [_n("a", "已證實")], length="long", level="intro")
        self.assertIn("2500", p)                             # 長度指示進 prompt
        self.assertIn("入門", p)                              # 難度指示進 prompt

    def test_article_crud(self):
        from knowfield.store.repository import Repository
        from tests.rag_helpers import temp_db
        repo = Repository(temp_db())
        aid = repo.save_article("主題", "標題", "# 文章內容", "medium", "intermediate", "2026-08-07")
        rows = repo.list_articles()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "標題")
        self.assertEqual(repo.get_article(aid)["markdown"], "# 文章內容")
        self.assertTrue(repo.delete_article(aid))
        self.assertEqual(repo.list_articles(), [])
        repo.close()


if __name__ == "__main__":
    unittest.main()
