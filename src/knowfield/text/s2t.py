"""簡體 → 繁體（台灣用語）顯示層正規化（spec 037）。

**只在顯示路徑用，絕不寫回儲存層**（FR-004：原文逐字保留，原文才是真相）。

三件事，缺一不可：
  1. 承重片段先抽佔位（`protect`）——沒有它，轉換會改壞程式碼／URL／圖片／數學，淨值為負。
  2. 確定性引擎 `s2twp`（含詞彙層：軟件→軟體、內存→記憶體），零 LLM。
  3. 引擎不可用時退回 identity——這是**預期路徑不是例外**（experience：
     「把重量級相依藏在可插拔介面後，預設離線 stub」）。
"""
from __future__ import annotations

import logging

from . import protect

_log = logging.getLogger(__name__)

_CONVERTER: object | None = None
_LOADED = False
_WARNED = False


def _load_converter():
    """載入 OpenCC 轉換器；不可用回 None。純副作用隔離點，測試可 monkeypatch。"""
    try:
        import opencc
    except ImportError:
        return None
    try:
        return opencc.OpenCC("s2twp")
    except Exception as exc:                      # 設定檔缺失等
        _log.warning("s2t：OpenCC 載入失敗，顯示層將顯示原文（%s）", exc)
        return None


def _converter(force_reload: bool = False):
    global _CONVERTER, _LOADED, _WARNED
    if force_reload or not _LOADED:
        _CONVERTER = _load_converter()
        _LOADED = True
        if _CONVERTER is None and not _WARNED:
            # 憲章 V：不靜默吞掉——記一次就好，別每則來源都刷一行
            _log.info("s2t：轉換引擎不可用（未安裝 opencc），來源詳情頁將顯示原文")
            _WARNED = True
    return _CONVERTER


def available() -> bool:
    """轉換能力目前是否可用。前端據此決定要不要顯示「繁體 ⇄ 原文」切換。"""
    return _converter() is not None


def convert(text: str, _force_reload: bool = False) -> str:
    """簡→繁（台灣用語）。承重片段逐字不變；引擎不可用時回傳輸入本身。

    確定性：同輸入永遠同輸出，不涉及生成式模型。
    """
    if not text:
        return text
    conv = _converter(force_reload=_force_reload)
    if conv is None:
        return text
    masked, segments = protect.mask(text)
    return protect.restore(conv.convert(masked), segments)
