"""收進圖片在地化：把 markdown 裡的外連圖片下載到本地 media/、改寫成本地路徑（/media/<hash>.<ext>）。

best-effort：抓不到的圖**保留原外連 URL**（不擋收進，教訓 3）。圖片只影響顯示、不進 embedding
（存的是短路徑不是 base64）。也處理 PDF OCR 內嵌的 data: 圖（解碼存檔、改寫路徑）。
"""
from __future__ import annotations

import base64
import hashlib
import re
import urllib.request
from pathlib import Path

# 在地化 http(s) 外連圖，以及 PDF OCR 回的 data:image;base64 內嵌圖（base64 無 ) 或空白，安全）
_IMG = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+|data:image/[^)\s]+)\)")
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


def source_pdf_name(url: str) -> str:
    """來源 PDF 的本地檔名（由 url 衍生、穩定）：存原始 PDF＝防原文失效＋頁級預覽。"""
    return "pdf-" + hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:16] + ".pdf"


def save_source_pdf(media_dir: str, url: str, data: bytes) -> str:
    """把原始 PDF 存進 media_dir，回 `/media/<name>` 路徑（供來源頁預覽、由來 #page=N）。"""
    d = Path(media_dir)
    d.mkdir(parents=True, exist_ok=True)
    name = source_pdf_name(url)
    (d / name).write_bytes(data)
    return f"/media/{name}"


def paper_meta_name(url: str) -> str:
    """論文 metadata JSON 的本地檔名（由 url 衍生、穩定）：Abstract/作者/日期，供論文展示。"""
    return "paper-" + hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:16] + ".json"


def save_paper_meta(media_dir: str, url: str, meta: dict) -> str:
    """存論文 metadata JSON 進 media_dir，回本地路徑。"""
    import json
    d = Path(media_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / paper_meta_name(url)).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return f"/media/{paper_meta_name(url)}"


def load_paper_meta(media_dir: str, url: str) -> dict | None:
    """讀論文 metadata（無→None）。"""
    import json
    p = Path(media_dir) / paper_meta_name(url)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _decode_data_uri(uri: str) -> tuple[bytes, str, str]:
    """data:image/jpeg;base64,XXXX → (bytes, 副檔名, base64字串)。base64 當內容雜湊、同圖去重。"""
    header, _, b64 = uri.partition(",")
    mime = header[5:].split(";")[0].strip().lower()      # "image/jpeg"
    return base64.b64decode(b64), _CTYPE_EXT.get(mime, "img"), b64


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
            if url.startswith("data:"):               # PDF OCR 內嵌圖：解碼、不走網路
                data, ext, b64 = _decode_data_uri(url)
                key = hashlib.sha1(b64.encode("utf-8")).hexdigest()[:16]
            else:                                      # http(s) 外連圖：下載
                data, ctype = fetch(url)
                ext = _ext(url, ctype)
                key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
            if not data:
                raise ValueError("空回應")
            name = f"{key}.{ext}"
            d.mkdir(parents=True, exist_ok=True)
            (d / name).write_bytes(data)
            local = f"{url_prefix}/{name}"
            cache[url] = local
            saved += 1
            return f"![{alt}]({local})"
        except Exception:               # noqa: BLE001 - 抓不到不擋收進、保留外連
            return m.group(0)

    return _IMG.sub(repl, md), saved
