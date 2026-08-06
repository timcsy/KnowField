"""網頁正文→markdown 抽取（spec 030 增量：URL 抓正文那張嘴）。

stdlib HTMLParser、零相依、離線可測。抽 <title> ＋標題(h1-6)/段落(p)/清單(li)/引言(blockquote)
成 markdown，略過 nav/script/style/footer 等 boilerplate。品質為便宜的 readability 級——
存取難/結構要求高的走「貼上」；這條是開放網頁的**便利**嘴（best-effort）。抓下來的 markdown
再走同一條 `chunk_markdown → store_chunks`。
"""

from __future__ import annotations

import re
import urllib.parse
from html.parser import HTMLParser


_ARXIV = re.compile(r"^https?://arxiv\.org/(?:abs|pdf)/(\d+\.\d+)(?:v\d+)?/?$", re.I)


def normalize_ingest_url(url: str) -> tuple[str, str]:
    """回 (fetch_url, store_url)。arxiv abs/pdf → 抓 HTML 版（有 figure 圖＋乾淨數學；OCR 端點拿不到
    圖像素），但**存回正規 /abs**（由來/去重穩定）。其他網址原樣。"""
    u = (url or "").strip()
    m = _ARXIV.match(u)
    if m:
        aid = m.group(1)
        return f"https://arxiv.org/html/{aid}", f"https://arxiv.org/abs/{aid}"
    return u, u


def _img_tex(src: str, a: dict) -> str:
    """公式圖片→LaTeX：知乎等把數學存成 `equation?tex=...` 圖或 data-tex/alt。抽不到→""。"""
    dt = (a.get("data-tex") or "").strip()
    if dt:
        return dt
    m = re.search(r'[?&]tex=([^&"\']+)', src or "")
    if m:
        return urllib.parse.unquote(m.group(1)).strip()
    if "equation" in (src or "") and (a.get("alt") or "").strip():
        return a["alt"].strip()            # 知乎公式圖常把 tex 放 alt
    return ""

_SKIP = {"script", "style", "nav", "header", "footer", "aside",
         "form", "button", "svg", "noscript"}   # 不跳過 figure：解說圖常包在 <figure> 裡
_HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCK = _HEAD | {"p", "li", "blockquote"}


class _ArticleMarkdown(HTMLParser):
    def __init__(self, base_url: str = "") -> None:
        super().__init__()
        self.base = base_url       # 頁面網址：把相對圖片 src 接成絕對（否則相對圖被丟）
        self.title = ""            # <title> 標籤
        self.doc_h1 = ""           # 第一個 <h1>＝文章標題（全網慣例；常在 <header> 內，仍要擷取）
        self.blocks: list[str] = []
        self._in_title = False
        self._in_h1 = False
        self._skip = 0
        self._math_skip = 0        # >0＝在數學元素（span[data-tex]/aria-hidden 渲染）內，跳過
        self._in_math = 0          # <math>…</math> MathML 內：跳渲染、只留 annotation
        self._cap = None           # 正在擷取 tex 的載體："anno"（annotation）｜"script"（math/tex）
        self._tex_buf = ""
        self._mode: str | None = None
        self._cur: list[str] = []

    def _emit_tex(self, tex: str):
        tex = (tex or "").strip()
        if not tex:
            return
        if self._mode is not None:            # 段落內→行內數學（句子不斷）
            tex = " ".join(tex.split())       # 壓成單行：行內含換行會讓前端 $..$ 配對連鎖崩壞
            self._cur.append(f" ${tex}$ ")
        else:                                 # 獨立→區塊公式
            self._flush()
            self.blocks.append(f"$$\n{tex}\n$$")

    def _flush(self):
        text = " ".join("".join(self._cur).split())
        self._cur = []
        mode, self._mode = self._mode, None
        if not text:
            return
        if mode in _HEAD:
            self.blocks.append("#" * int(mode[1]) + " " + text)
        elif mode == "li":
            self.blocks.append("- " + text)
        elif len(text) >= 2:
            self.blocks.append(text)

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
            return
        if tag == "h1" and not self.doc_h1 and not self._in_h1:
            self._in_h1 = True                    # 擷取第一個 h1 當標題（即使在被略過的 header 裡）
        a = dict(attrs)
        # --- 標準數學載體（泛化：按載體抽 LaTeX，不按站）---
        if tag == "script" and "math/tex" in (a.get("type") or ""):   # MathJax v2
            self._cap = "script"
            self._tex_buf = ""
            return
        if tag == "annotation" and "x-tex" in (a.get("encoding") or ""):  # KaTeX/MathML 標準
            self._cap = "anno"
            self._tex_buf = ""
            return
        if self._math_skip:                               # 已在要跳過的數學渲染內
            self._math_skip += 1
            return
        if tag == "math":                                 # MathML：跳渲染、只留 annotation
            self._in_math += 1
            return
        if self._in_math:
            return
        cls = a.get("class") or ""                        # 數學的視覺渲染→跳過（tex 另從載體取）
        if a.get("aria-hidden") == "true" or "katex-html" in cls or "MathJax" in cls:
            self._math_skip = 1
            return
        if tag in _SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "img":                                  # 圖片→行內 markdown（spec 031 rich-paste）
            a = dict(attrs)
            src = (a.get("data-actualsrc") or a.get("data-original") or a.get("data-src")
                   or a.get("src") or "")
            tex = _img_tex(src, a)                         # 公式圖→LaTeX
            if tex:
                self._emit_tex(tex)
                return
            # 一般圖片：外連 URL 收；相對路徑靠 base_url 接成絕對；data: base64（截圖）會塞爆 embedding、擋掉
            if src and not src.startswith("data:"):
                if src.startswith("//"):
                    src = "https:" + src
                elif not src.startswith("http"):
                    src = urllib.parse.urljoin(self.base, src) if self.base else ""  # 相對→絕對（需 base）
                if src.startswith("http"):
                    self._flush()
                    if self.blocks and self.blocks[-1].endswith(f"]({src})"):
                        return                    # 連續同圖去重（知乎 預覽圖+真圖）
                    self.blocks.append(f"![{(a.get('alt') or '').strip()}]({src})")
            return
        a = dict(attrs)
        dtex = (a.get("data-tex") or a.get("data-formula") or "").strip()
        if dtex:                                           # span[data-tex] 等行內數學（知乎）
            self._emit_tex(dtex)
            self._math_skip = 1                            # 跳過它內部的渲染節點
            return
        if tag == "br":
            self._cur.append(" ")
        elif tag in _BLOCK:
            self._flush()
            self._mode = tag if tag in _HEAD else ("li" if tag == "li" else "p")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
            return
        if tag == "h1" and self._in_h1:
            self._in_h1 = False                   # h1 收尾（doc_h1 已擷取）；不 return，內文 h1 照常 flush
        if self._cap and ((self._cap == "anno" and tag == "annotation")
                          or (self._cap == "script" and tag == "script")):
            self._cap = None
            self._emit_tex(self._tex_buf.strip())        # 載體收尾→吐 LaTeX
            return
        if tag == "math" and self._in_math:
            self._in_math -= 1
            return
        if self._in_math:
            return
        if self._math_skip:                # 數學渲染關閉→退出跳過
            self._math_skip -= 1
            return
        if tag in _SKIP and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag in _BLOCK:
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if self._in_h1:                    # h1 文字→標題（即使在被略過的 header 裡）；不 return，內文 h1 照常
            self.doc_h1 += data
        if self._cap:                      # 正在擷取載體裡的 tex
            self._tex_buf += data
        elif not self._skip and not self._math_skip and not self._in_math and self._mode:
            self._cur.append(data)


_REL_START = re.compile(
    r"^\s*(?:\\displaystyle\s*)?(?:=|\\le|\\ge|\\leq|\\geq|\\approx|\\equiv|\\sim|\\propto|<|>|\\to|\\Rightarrow|\\subseteq|\\in|\\cdot|\\times|\\pm|\+|-)")


def _merge_math_blocks(blocks: list[str]) -> list[str]:
    """連續的區塊公式（arxiv LaTeXML 把對齊式拆成多個 <math>）合併成單一 \\begin{aligned}：
    修對齊跑版，也消掉連續 $$（否則被切塊/stitch 誤判、砍掉分隔符連鎖崩壞）。關係符號開頭的塊→接上一列。"""
    out: list[str] = []
    i = 0
    while i < len(blocks):
        if blocks[i].startswith("$$") and blocks[i].rstrip().endswith("$$"):
            run: list[str] = []
            while i < len(blocks) and blocks[i].startswith("$$") and blocks[i].rstrip().endswith("$$"):
                inner = re.sub(r"^\\displaystyle\s*", "", blocks[i].strip()[2:-2].strip())
                if inner:
                    run.append(inner)
                i += 1
            if len(run) <= 1:
                out.append(f"$$\n{run[0]}\n$$" if run else "")
            else:
                rows: list[str] = []
                for part in run:
                    if rows and _REL_START.match(part):     # 關係符號開頭→接上一列（對齊點在 &）
                        rows[-1] = rows[-1] + " &" + part
                    else:
                        rows.append(part)
                body = " \\\\\n".join(rows)
                out.append(f"$$\n\\begin{{aligned}}\n{body}\n\\end{{aligned}}\n$$")
        else:
            out.append(blocks[i])
            i += 1
    return [b for b in out if b]


def extract_article_markdown(html: str, base_url: str = "") -> tuple[str, str]:
    """回 (title, markdown)。抽不到→("", "")；不崩（best-effort）。base_url＝把相對圖片接成絕對。"""
    p = _ArticleMarkdown(base_url)
    try:
        p.feed(html or "")
    except Exception:  # noqa: BLE001 - 壞 HTML 不該炸收進
        pass
    p._flush()
    p.blocks = _merge_math_blocks(p.blocks)
    # 標題優先文章 h1（乾淨、無站名後綴），退回 <title> 標籤
    title = " ".join((p.doc_h1 or p.title).split()).strip()
    md = "\n\n".join(p.blocks).strip()
    return title, md
