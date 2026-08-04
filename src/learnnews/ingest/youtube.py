"""YouTube 逐字稿抓取（spec 030 增量：YouTube 那張嘴）。

洞見：YouTube 的價值多半是**逐字稿（文字）**，不是影片——抓字幕就好，跳過整條 ffmpeg/whisper 重工。
stdlib、`http_get` 可注入（離線可測）。**過膜的老實話**：程式化抓字幕本身脆（YouTube 會擋/改版、需同意
cookie），故 best-effort——抓不到就丟友善錯誤，使用者可改用「貼上」（開逐字稿面板全選複製貼上，那張嘴涵蓋）。
抓下來的逐字稿再走同一條 `chunk_markdown → store_chunks`。
"""

from __future__ import annotations

import html as _html
import re

from ..sources.base import SourceUnavailable


def parse_video_id(url: str) -> str:
    """從各種 YouTube 連結抽出 11 碼 video id；抽不到→""。"""
    url = (url or "").strip()
    m = re.search(r"(?:v=|/shorts/|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    return url if re.fullmatch(r"[A-Za-z0-9_-]{11}", url) else ""


def extract_caption_url(watch_html: str) -> str:
    """從 watch 頁的 `captionTracks` 抽第一條字幕 baseUrl；無→""。"""
    m = re.search(r'"captionTracks":\[(.*?)\]', watch_html or "", re.S)
    if not m:
        return ""
    b = re.search(r'"baseUrl":"(.*?)"', m.group(1))
    if not b:
        return ""
    return b.group(1).replace("\\u0026", "&").replace("\\/", "/")


def parse_transcript(caption_xml: str) -> str:
    """把 timedtext XML 的 <text> 逐句解成純文字（去標籤、反 HTML 實體）。"""
    lines = []
    for t in re.findall(r"<text[^>]*>(.*?)</text>", caption_xml or "", re.S):
        line = _html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _title(watch_html: str, fallback: str) -> str:
    m = re.search(r'"title":"(.*?)"', watch_html or "")
    return (m.group(1).replace("\\u0026", "&") if m else fallback)


def fetch_transcript(url: str, http_get) -> tuple[str, str]:
    """回 (title, transcript)。無 id/無字幕/空字幕→SourceUnavailable（邊界攔，教訓 3）。"""
    vid = parse_video_id(url)
    if not vid:
        raise SourceUnavailable("這不是有效的 YouTube 連結")
    watch = http_get(f"https://www.youtube.com/watch?v={vid}")
    cap_url = extract_caption_url(watch)
    if not cap_url:
        raise SourceUnavailable("這支影片沒有可取用的字幕（可開逐字稿面板全選複製，改用「貼上」）")
    text = parse_transcript(http_get(cap_url))
    if not text.strip():
        raise SourceUnavailable("字幕內容是空的")
    return _title(watch, vid), text
