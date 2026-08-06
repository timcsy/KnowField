"""spec 030 增量：YouTube 逐字稿抓取的純解析（video id、captionTracks、transcript XML）。"""

import unittest

from knowfield.ingest.youtube import (
    extract_caption_url,
    fetch_transcript,
    parse_transcript,
    parse_video_id,
)


class TestParse(unittest.TestCase):
    def test_video_id_forms(self):
        self.assertEqual(parse_video_id("https://www.youtube.com/watch?v=abcdefghij1"), "abcdefghij1")
        self.assertEqual(parse_video_id("https://youtu.be/abcdefghij1"), "abcdefghij1")
        self.assertEqual(parse_video_id("https://www.youtube.com/shorts/abcdefghij1"), "abcdefghij1")
        self.assertEqual(parse_video_id("不是連結"), "")

    def test_extract_caption_url(self):
        html = ('xxx"captionTracks":[{"baseUrl":"https://www.youtube.com/api/'
                'timedtext?v=X\\u0026lang=zh","name":{}}]yyy')
        self.assertEqual(extract_caption_url(html),
                         "https://www.youtube.com/api/timedtext?v=X&lang=zh")

    def test_extract_caption_url_none(self):
        self.assertEqual(extract_caption_url("沒有字幕的頁面"), "")

    def test_parse_transcript(self):
        xml = ('<transcript><text start="0" dur="2">貓要吃貓糧</text>'
               '<text start="2" dur="2">也要用貓砂 &amp; 定期看醫生</text></transcript>')
        self.assertEqual(parse_transcript(xml), "貓要吃貓糧\n也要用貓砂 & 定期看醫生")


class TestFetchTranscript(unittest.TestCase):
    _WATCH = ('..."title":"養貓完全指南"...'
              '"captionTracks":[{"baseUrl":"https://yt/api/timedtext?v=abc","name":{}}]...')
    _CAP = '<transcript><text start="0" dur="2">貓要吃貓糧與用貓砂</text></transcript>'

    def _http(self, u):
        return self._CAP if "timedtext" in u else self._WATCH

    def test_fetch(self):
        title, text = fetch_transcript("https://youtu.be/abcdefghij1", self._http)
        self.assertEqual(title, "養貓完全指南")
        self.assertIn("貓要吃貓糧", text)

    def test_no_captions_raises(self):
        from knowfield.sources.base import SourceUnavailable
        with self.assertRaises(SourceUnavailable):
            fetch_transcript("https://youtu.be/abcdefghij1", lambda u: "沒字幕頁")


if __name__ == "__main__":
    unittest.main()
