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

# FR-010：s2twp 的詞彙層會把某些詞轉到**錯的領域義**。這 8 個是在實際語料（626 塊）上
# 比對 s2tw 與 s2twp 的輸出差異、逐一判斷後確認的**錯義或不成詞**——不含台灣用語偏好差異
# （優化→最佳化、數據→資料、概率→機率、函數→函式、網絡→網路 這些是對的，留著）。
# 掃描方法與完整判斷記在 specs/037-simplified-to-traditional/spec.md〈修訂記錄〉。
_OVERRIDES: tuple[tuple[str, str], ...] = (
    ("引數", "參數"),          # 模型參數 ≠ 函式引數（程式設計術語）
    ("推匯出", "推導出"),      # 不成詞：「導出」被當 export 轉成「匯出」
    ("檢索正規化", "檢索範式"),  # paradigm 被轉成 normalization，意思完全變了
    ("擴充套件", "擴展"),      # 軟體擴充套件 ≠ 數學上的擴展
    ("影象", "圖像"),          # 不成詞
    ("全域性", "全局"),        # 全局最佳化的「全局」台灣也這樣講
    ("多工", "多任務"),        # 多任務學習（multi-task）
    ("許可權", "權限"),        # 權限在台灣是通用詞
)

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
    converted = conv.convert(masked)
    # FR-010：只在**原文沒出現過該詞**時才修——若作者本來就寫「引數」，那是他的用字（守 FR-008）。
    # 同一份文件兩種寫法都有時整份跳過：少修比改壞安全，與 FR-006 承重保護同方向。
    for bad, good in _OVERRIDES:
        if bad not in masked:
            converted = converted.replace(bad, good)
    return protect.restore(converted, segments)
