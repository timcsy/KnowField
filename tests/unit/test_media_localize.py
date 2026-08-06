"""收進圖片在地化：外連圖→下載到 media/、改寫本地路徑；抓不到保留外連（best-effort）。"""
import tempfile
import unittest
from pathlib import Path

from knowfield.ingest.media import localize_images


class TestLocalizeImages(unittest.TestCase):
    def test_downloads_and_rewrites(self):
        calls = {}

        def fake_fetch(url):
            calls[url] = calls.get(url, 0) + 1
            return b"bytes", "image/jpeg" if "b.jpg" in url else "image/png"

        with tempfile.TemporaryDirectory() as d:
            md = "看圖 ![示意](https://blog.x/img/a.png) 和 ![](https://cdn.x/b.jpg?v=2)"
            out, n = localize_images(md, d, fetch=fake_fetch)
            self.assertEqual(n, 2)
            self.assertIn("![示意](/media/", out)
            self.assertNotIn("https://blog.x", out)          # 外連已換成本地
            self.assertRegex(out, r"/media/[0-9a-f]{16}\.png")
            self.assertRegex(out, r"/media/[0-9a-f]{16}\.jpg")   # content-type 定副檔名
            self.assertEqual(len(list(Path(d).iterdir())), 2)    # 兩檔真的落地

    def test_failed_fetch_keeps_external_url(self):
        def boom(url):
            raise OSError("hotlink 擋")

        with tempfile.TemporaryDirectory() as d:
            md = "![x](https://walled.example/secret.png)"
            out, n = localize_images(md, d, fetch=boom)
            self.assertEqual(n, 0)
            self.assertEqual(out, md)                         # 原封不動（不擋收進）

    def test_dedup_same_url_fetched_once(self):
        calls = {}

        def fake_fetch(url):
            calls[url] = calls.get(url, 0) + 1
            return b"data", "image/gif"

        with tempfile.TemporaryDirectory() as d:
            md = "![a](https://x/same.gif) ... ![b](https://x/same.gif)"
            out, n = localize_images(md, d, fetch=fake_fetch)
            self.assertEqual(calls["https://x/same.gif"], 1)  # 同 url 只抓一次
            self.assertEqual(n, 1)

    def test_data_uri_image_decoded_and_saved(self):
        # PDF OCR 內嵌圖：data:image;base64 → 解碼存檔、改寫 /media（不走網路）
        import base64
        b64 = base64.b64encode(b"PNGBYTES").decode()
        with tempfile.TemporaryDirectory() as d:
            md = f"見圖 ![圖1](data:image/png;base64,{b64}) 說明"
            out, n = localize_images(md, d)          # data: 不需注入 fetch
            self.assertEqual(n, 1)
            self.assertRegex(out, r"!\[圖1\]\(/media/[0-9a-f]{16}\.png\)")
            files = list(Path(d).iterdir())
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].read_bytes(), b"PNGBYTES")   # 真的解碼落地

    def test_no_images_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            md = "純文字沒有圖片。data:image 也不碰。"
            out, n = localize_images(md, d, fetch=lambda u: (b"", ""))
            self.assertEqual((out, n), (md, 0))


if __name__ == "__main__":
    unittest.main()
