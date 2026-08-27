"""把一段思考變成可貼進**那個 repo 的 `knowledge/draft/`** 的一塊。

⚠️ **這一支只組得出 `knowledge/draft/*.md` 的路徑。** 那是能力邊界，不是政策：
   使用者定的界線是「我們只會動 draft，代表短期記憶。至於如何處理 draft 就是專案的事了」。
   往上每一層（`experience.md`／`concepts/`）都需要判斷，而那個判斷**是那個專案的**
   ——用它自己的 `knowie-consolidate`。而 `experience.md` 也**不是 append-only**
   （它會被反流、合併、拆分），讀-改-寫是另一回事。
"""
from __future__ import annotations

import re
import urllib.parse

DRAFT_DIR = "knowledge/draft/"

#: ⚠️ 實測（2026-08-27）：GitHub 預填新檔頁面的網址上限 ≈ 8,100 字元
#: （8,200 → 414，而 7,000–8,100 之間已經開始回 500／斷線）。
#: 中文 percent-encode 是 **5.3 倍** ⇒ 按鈕只塞得下約 1,000 字。
#: 超過要**退回複製並說明原因**，不是靜默降級。
URL_BUDGET = 6000


def slug(title: str) -> str:
    """檔名用的一段。⚠️ **不留空白**——空白會讓 `%20` 編碼與字面連結對不起來。"""
    s = re.sub(r"[^\w一-鿿-]+", "-", (title or "").strip())
    return re.sub(r"-{2,}", "-", s).strip("-")[:48] or "note"


def draft_path(date: str, title: str) -> str:
    """⚠️ **唯一**組得出路徑的地方，而它只組得出 `knowledge/draft/`。"""
    return f"{DRAFT_DIR}{date[:10]}-{slug(title)}.md"


def render(title: str, body: str, cites: list[dict], base_repo: str, date: str) -> str:
    """一塊 draft。⚠️ 出處逐條列出——合成最容易磨掉的就是它。"""
    lines = [f"# {title}", "",
             "> 由 KnowField 從一段對話整理。**推論的**，未經冊封——"
             "留不留、怎麼沉澱是這個專案的事。", "",
             body.strip(), ""]
    if cites:
        lines += ["## 出處", ""]
        lines += [f"- `{c['path'].replace('knowledge/', '')}` #{c.get('seq', 0)}" for c in cites]
        lines.append("")
    lines.append(f"ⓘ {date[:10]} · 來自 {base_repo} 自己的 `knowledge/`")
    return "\n".join(lines)


def prefill_url(repo: str, branch: str, path: str, content: str) -> str | None:
    """GitHub 的「新檔案」頁面，檔名與內容都填好 → **你**按 commit。

    ⚠️ 回 `None` ＝ 太長，塞不進網址。**呼叫端要說明原因**，不要靜默改成別的行為。
    ⚠️ 而選這條最強的理由不是安全，是**作者是誰**：讓 bot commit，`git log` 就不再
       分得出哪些是你寫的、哪些是工具生的——而那條線正是這個專案的認識論。
    """
    if not path.startswith(DRAFT_DIR):          # 結構性禁令的最後一道
        raise ValueError(f"只寫得了 {DRAFT_DIR}：{path}")
    q = urllib.parse.urlencode({"filename": path, "value": content})
    url = f"https://github.com/{repo}/new/{branch or 'main'}?{q}"
    return url if len(url) <= URL_BUDGET else None
