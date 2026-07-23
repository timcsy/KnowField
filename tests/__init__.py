"""測試套件啟動：把 src/ 加入匯入路徑（離線、零安裝可測）。"""

import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
