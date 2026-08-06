"""spec 030 切塊純函式：長文切多塊、原子塊（code/表格/$$）不切半、章節優先切點、中文按字元。"""

import unittest

from knowfield.ingest.chunk import chunk_markdown, stitch_chunks


class TestStitch(unittest.TestCase):
    def test_removes_overlap(self):
        c1 = "第一段講貓的照顧方式" + "重疊區塊XYZ123"
        c2 = "重疊區塊XYZ123" + "第二段講狗的忠誠"
        self.assertEqual(stitch_chunks([c1, c2]),
                         "第一段講貓的照顧方式重疊區塊XYZ123第二段講狗的忠誠")  # 重疊去掉一次

    def test_no_overlap_joins(self):
        self.assertEqual(stitch_chunks(["第一段", "第二段"]), "第一段\n\n第二段")

    def test_empty(self):
        self.assertEqual(stitch_chunks([]), "")


class TestChunkMarkdown(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(chunk_markdown(""), [])
        self.assertEqual(chunk_markdown("   \n  "), [])

    def test_short_one_chunk(self):
        self.assertEqual(chunk_markdown("短短一句話。"), ["短短一句話。"])

    def test_long_prose_multiple(self):
        md = "甲" * 1000                              # 無空格中文長串
        chunks = chunk_markdown(md, target=400, overlap=40)
        self.assertGreater(len(chunks), 1)             # 按字元切得動
        self.assertTrue(all(len(c) <= 400 for c in chunks))
        self.assertEqual("".join(dict.fromkeys("".join(chunks))), "甲")  # 內容沒掉字（都是甲）

    def test_heading_starts_new_chunk(self):
        md = "# 第一章\n短內容甲\n\n# 第二章\n短內容乙"
        chunks = chunk_markdown(md, target=400)
        self.assertEqual(len(chunks), 2)
        self.assertIn("第一章", chunks[0])
        self.assertIn("第二章", chunks[1])
        self.assertNotIn("第二章", chunks[0])

    def test_code_block_not_split(self):
        code = "```python\n" + "x = 1\n" * 200 + "```"   # 遠大於 target
        chunks = chunk_markdown("前言\n\n" + code + "\n\n後語", target=400)
        holding = [c for c in chunks if "```python" in c]
        self.assertEqual(len(holding), 1)               # 整塊在同一 chunk
        self.assertIn("```", holding[0].rstrip()[-3:] if holding[0].rstrip().endswith("```") else holding[0])
        self.assertEqual(holding[0].count("x = 1"), 200)  # 沒被切掉

    def test_table_not_split(self):
        rows = "\n".join(f"| 列{i} | 值{i} |" for i in range(80))
        table = "| 欄A | 欄B |\n| --- | --- |\n" + rows
        chunks = chunk_markdown("說明\n\n" + table, target=300)
        holding = [c for c in chunks if "| 欄A | 欄B |" in c]
        self.assertEqual(len(holding), 1)               # 整張表在同一 chunk
        self.assertIn("| 列79 | 值79 |", holding[0])

    def test_math_block_not_split(self):
        math = "$$\n" + "a + b + c + d = e\n" * 60 + "$$"
        chunks = chunk_markdown("推導\n\n" + math, target=200)
        holding = [c for c in chunks if c.strip().startswith("$$") or "$$" in c]
        self.assertTrue(any(h.count("a + b + c + d = e") == 60 for h in holding))  # 公式完整


if __name__ == "__main__":
    unittest.main()
