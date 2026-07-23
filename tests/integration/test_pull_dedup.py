"""T006：主題拉取＋跨源去重（quickstart 情境 A/C）。"""

import unittest

from learnnews.cli.pull_cmd import run_pull
from tests.helpers import FakeAdapter, make_item


class TestPullDedup(unittest.TestCase):
    def test_topic_pull_ranked(self):
        items = [
            make_item("agent 記憶與規劃", external_id="1", url="https://a/1"),
            make_item("編譯器最佳化", external_id="2", url="https://a/2"),
        ]
        result = run_pull([FakeAdapter("s", items)], "agent")
        titles = [e.item.title for e in result.entries]
        self.assertIn("agent 記憶與規劃", titles)
        self.assertNotIn("編譯器最佳化", titles)

    def test_same_material_two_sources_dedup(self):
        a = make_item("agent 綜述", external_id="2401.9", url="https://arxiv.org/abs/2401.9")
        b = make_item("agent 綜述", external_id="2401.9", url="https://hf.co/papers/2401.9")
        result = run_pull(
            [FakeAdapter("arxiv", [a]), FakeAdapter("hf", [b])], "agent")
        self.assertEqual(len(result.entries), 1)


if __name__ == "__main__":
    unittest.main()
