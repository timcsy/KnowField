"""文件轉檔器（spec 030）：PDF → markdown。

`DocConverter` 協定＝窄介面（教訓 1，離線靠注入 stub、核心零相依）。
`MistralDocConverter`＝真實 adapter：走使用者現有 gateway `/v1/ocr`（實測 azure/mistral-document-ai-2512
吐繁體 markdown）。>30 頁時逐頁 `pdftoppm` render 成圖走 `image_url` 合併——避開單份 30 頁上限與
poppler 笨切爆脹（research R2）。真實 adapter 不進單元測試（需 gateway/pdftoppm）；金鑰不落日誌。
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from typing import Protocol

from ..sources.base import SourceUnavailable

_MAX_PAGES = 30            # Azure Mistral Document AI 單份頁數上限（實測）


class DocConverter(Protocol):
    def to_markdown(self, pdf_bytes: bytes | None = None,
                    pdf_url: str | None = None) -> str: ...


class MistralDocConverter:
    """經現有 OpenAI 相容 gateway 呼叫 `/v1/ocr`。"""

    def __init__(self, config) -> None:
        self.base = (config.api_base_url or "").rstrip("/")
        self.key = config.api_key
        self.model = getattr(config, "ocr_model", "azure/mistral-document-ai-2512")

    def _ocr(self, document: dict, pages: list[int] | None = None) -> str:
        body = {"model": self.model, "document": document, "include_image_base64": False}
        if pages is not None:
            body["pages"] = pages
        req = urllib.request.Request(
            f"{self.base}/ocr", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.key}"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read())
        except Exception as e:  # noqa: BLE001 - 轉檔失敗→邊界攔（教訓 3）
            raise SourceUnavailable(f"文件轉檔失敗：{type(e).__name__}") from e
        return "\n\n---\n\n".join(p.get("markdown", "") for p in data.get("pages", []))

    def to_markdown(self, pdf_bytes: bytes | None = None,
                    pdf_url: str | None = None) -> str:
        if not self.base or not self.key:
            raise SourceUnavailable("未設定轉檔端點或金鑰")
        if pdf_bytes is None and pdf_url:
            # 先試整份（document_url）；>30 頁被擋→退回逐頁 render
            try:
                return self._ocr({"type": "document_url", "document_url": pdf_url})
            except SourceUnavailable:
                with urllib.request.urlopen(pdf_url, timeout=120) as r:
                    pdf_bytes = r.read()
        if pdf_bytes is None:
            raise SourceUnavailable("沒有可轉檔的 PDF 內容")
        n = _page_count(pdf_bytes)
        if n is not None and n > _MAX_PAGES:
            return self._render_and_ocr(pdf_bytes)     # 逐頁 render 成圖，避開 30 頁上限
        b64 = base64.b64encode(pdf_bytes).decode()
        return self._ocr({"type": "document_url",
                          "document_url": f"data:application/pdf;base64,{b64}"})

    def _render_and_ocr(self, pdf_bytes: bytes) -> str:
        if not shutil.which("pdftoppm"):
            raise SourceUnavailable("長 PDF 需 pdftoppm 逐頁處理，但系統未安裝")
        parts: list[str] = []
        with tempfile.TemporaryDirectory() as d:
            pdf_path = os.path.join(d, "in.pdf")
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            subprocess.run(["pdftoppm", "-png", "-r", "150", pdf_path,
                            os.path.join(d, "pg")], check=True, timeout=600)
            pngs = sorted(p for p in os.listdir(d) if p.endswith(".png"))
            for name in pngs:
                with open(os.path.join(d, name), "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                try:
                    parts.append(self._ocr(
                        {"type": "image_url", "image_url": f"data:image/png;base64,{b64}"}))
                except SourceUnavailable:
                    continue                            # 單頁失敗跳過、其餘照收（best-effort）
        if not any(p.strip() for p in parts):
            raise SourceUnavailable("整份 PDF 都無法轉檔")
        return "\n\n---\n\n".join(parts)


def _page_count(pdf_bytes: bytes) -> int | None:
    """粗估頁數（數 PDF 的 /Type /Page）；估不到→None（走整份路）。"""
    try:
        import re
        return len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes)) or None
    except Exception:  # noqa: BLE001
        return None
