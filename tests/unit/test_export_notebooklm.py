"""spec 024：NotebookLM 匯出 formatter 純函式——離線、缺項不崩、去重保序。"""

import unittest

from learnnews.export.notebooklm import (
    conversation_evidence_urls,
    conversation_to_markdown,
    dedup_urls,
    why_node_to_markdown,
)

_MSGS = [
    {"role": "user", "content": "attention 為何加權？"},
    {"role": "assistant", "content": "因內容決定權重 [1]，殘差再累加 [2]。",
     "sources": [{"n": 1, "url": "https://a/1", "title": "Attention 論文"},
                 {"n": 2, "url": "https://a/2", "title": "殘差"}]},
    {"role": "user", "content": "那 FFN 呢？"},
    {"role": "assistant", "content": "FFN 是 key-value 記憶 [1]。",
     "sources": [{"n": 1, "url": "https://a/1", "title": "重複來源"}]},
]


class TestConversationMarkdown(unittest.TestCase):
    def test_structure_and_roles(self):                     # T003 正常
        md = conversation_to_markdown("attention 加權", _MSGS)
        self.assertIn("# attention 加權", md)
        self.assertIn("**你：**", md)
        self.assertIn("**副手：**", md)
        # 內文保留行內引用
        self.assertIn("[1]", md)
        self.assertIn("[2]", md)

    def test_sources_block_per_message(self):               # T003 逐訊息來源塊
        md = conversation_to_markdown("t", _MSGS)
        # 每則來源接在該則後，含標題與 URL
        self.assertIn("Attention 論文", md)
        self.assertIn("https://a/1", md)
        self.assertIn("https://a/2", md)
        # 第二則 assistant 的 [1] 與第一則的 [1] 各自成塊（不撞號）——「重複來源」也在
        self.assertIn("重複來源", md)

    def test_empty_messages_only_title(self):               # T003 空 messages
        md = conversation_to_markdown("空的", [])
        self.assertIn("# 空的", md)
        # 不崩、無來源塊
        self.assertNotIn("**副手：**", md)

    def test_missing_title(self):                           # T003 缺標題
        md = conversation_to_markdown("", _MSGS)
        self.assertIn("（未命名對話）", md)

    def test_missing_content_and_sources_ok(self):          # T003 缺欄位不崩
        md = conversation_to_markdown("t", [{"role": "assistant"}])  # 無 content/sources
        self.assertIn("**副手：**", md)                     # 不拋例外

    def test_source_missing_title_uses_url(self):           # T003 缺 source 標題
        md = conversation_to_markdown("t", [
            {"role": "assistant", "content": "見 [1]",
             "sources": [{"n": 1, "url": "https://x/y"}]}])
        self.assertIn("https://x/y", md)


class TestConversationEvidenceUrls(unittest.TestCase):
    def test_dedup_preserve_order(self):                    # T008 去重保序
        urls = conversation_evidence_urls(_MSGS)
        self.assertEqual(urls, ["https://a/1", "https://a/2"])  # a/1 重複只一次、保序

    def test_no_sources_empty(self):                        # T008 無來源
        self.assertEqual(conversation_evidence_urls(
            [{"role": "user", "content": "hi"}]), [])

    def test_skip_source_without_url(self):                 # T008 缺 url 略過
        urls = conversation_evidence_urls(
            [{"role": "assistant", "content": "x",
              "sources": [{"n": 1, "title": "無網址"}, {"n": 2, "url": "https://ok"}]}])
        self.assertEqual(urls, ["https://ok"])


class TestDedupUrls(unittest.TestCase):
    def test_dedup(self):                                   # T008
        self.assertEqual(dedup_urls(["a", "b", "a", "c", "b"]), ["a", "b", "c"])

    def test_empty(self):
        self.assertEqual(dedup_urls([]), [])


class TestWhyNodeMarkdown(unittest.TestCase):
    def test_full(self):                                    # T013 主張＋階梯＋佐證
        md = why_node_to_markdown(
            "attention＝內容加權聚合",
            ["表面：怎麼加權", "更深：置換對稱", "bedrock：內容決定"],
            ["https://a/1", "https://a/2"])
        self.assertIn("# attention＝內容加權聚合", md)
        self.assertIn("階梯", md)
        self.assertIn("1. 表面：怎麼加權", md)
        self.assertIn("bedrock：內容決定", md)
        self.assertIn("佐證", md)
        self.assertIn("https://a/1", md)

    def test_empty_ladder_and_evidence_skipped(self):       # T013 空段略過
        md = why_node_to_markdown("只有主張", [], [])
        self.assertIn("# 只有主張", md)
        self.assertNotIn("階梯", md)
        self.assertNotIn("佐證", md)

    def test_missing_claim(self):                           # T013 空 claim
        md = why_node_to_markdown("", ["a"], [])
        self.assertIn("（未命名根因）", md)

    def test_evidence_deduped(self):                        # T013 佐證去重
        md = why_node_to_markdown("c", [], ["https://a/1", "https://a/1"])
        self.assertEqual(md.count("https://a/1"), 1)


if __name__ == "__main__":
    unittest.main()
