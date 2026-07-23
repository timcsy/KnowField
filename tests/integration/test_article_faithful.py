"""T007：忠實不捏造（情境 C）＋不下工具結論（情境 D）。

註：真正的忠實度需接真實後端後抽查（experience 教訓 2）。此處以確定性 stub 驗證
「不捏造數據、不加結論」的行為契約。
"""

import unittest

from learnnews.cli.pull_cmd import run_pull
from tests.helpers import FakeAdapter, make_item

_CONCLUSION_MARKERS = ["我認為", "顯然", "必然", "將會顛覆", "註定", "毫無疑問"]


class TestArticleFaithful(unittest.TestCase):
    def test_no_fabricated_numbers_when_source_has_none(self):
        item = make_item("agent 快訊", external_id="1", url="https://a/1", abstract="")
        result = run_pull([FakeAdapter("s", [item])], "agent")
        body = result.entries[0].article.body
        self.assertNotIn("%", body)          # 原文無數據 → 不憑空生成
        self.assertNotIn("倍", body)

    def test_no_tool_conclusions(self):
        item = make_item("agent 研究", external_id="2", url="https://a/2",
                         abstract="研究前文。")
        result = run_pull([FakeAdapter("s", [item])], "agent")
        body = result.entries[0].article.body
        for marker in _CONCLUSION_MARKERS:
            self.assertNotIn(marker, body)   # 不下工具自己的結論/外推


if __name__ == "__main__":
    unittest.main()
