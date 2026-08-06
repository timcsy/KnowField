"""收進圖片在地化：把 markdown 裡的外連圖片下載到本地 media/、改寫成本地路徑（/media/<hash>.<ext>）。

best-effort：抓不到的圖**保留原外連 URL**（不擋收進，教訓 3）。圖片只影響顯示、不進 embedding
（存的是短路徑不是 base64）。data: 內嵌圖在抽取階段已擋（web.py）。
"""
from __future__ import annotations

import hashlib
import re
import urllib.request
from pathlib import Path

# 只在地化 http(s) 外連圖；OCR 產的本地參照（img-0.jpeg）等非 http 的略過
_IMG = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)")
_CTYPE_EXT = {
    "image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
    "image/svg+xml": "svg", "image/webp": "webp", "image/avif": "avif",
}
_EXT_OK = {"png", "jpg", "jpeg", "gif", "svg", "webp", "avif"}


def fetch_image_bytes(url: str, timeout: int = 30) -> tuple[bytes, str]:
    """抓圖 bytes＋content-type（帶 UA，牆內/hotlink 擋→拋，由 localize 攔成保留外連）。"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (KnowField)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        return r.read(), ctype


def _ext(url: str, ctype: str) -> str:
    if ctype in _CTYPE_EXT:
        return _CTYPE_EXT[ctype]
    tail = url.split("?")[0].rsplit(".", 1)[-1].lower()
    return tail if tail in _EXT_OK else "img"


def localize_images(md: str, media_dir: str, fetch=fetch_image_bytes,
                    url_prefix: str = "/media") -> tuple[str, int]:
    """下載 md 內每張外連圖到 media_dir、改寫成 <url_prefix>/<hash>.<ext>。回 (新md, 成功數)。
    抓不到的圖保留原樣。fetch 可注入（離線測試）。"""
    if not md or "![" not in md:
        return md, 0
    d = Path(media_dir)
    saved = 0
    cache: dict[str, str] = {}

    def repl(m: re.Match) -> str:
        nonlocal saved
        alt, url = m.group(1), m.group(2)
        if url in cache:
            return f"![{alt}]({cache[url]})"
        try:
            data, ctype = fetch(url)
            if not data:
                raise ValueError("空回應")
            name = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16] + "." + _ext(url, ctype)
            d.mkdir(parents=True, exist_ok=True)
            (d / name).write_bytes(data)
            local = f"{url_prefix}/{name}"
            cache[url] = local
            saved += 1
            return f"![{alt}]({local})"
        except Exception:               # noqa: BLE001 - 抓不到不擋收進、保留外連
            return m.group(0)

    return _IMG.sub(repl, md), saved
