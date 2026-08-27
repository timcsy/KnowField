"""GitHub App 認證與抓取——**只拿 `knowledge/**` 的內容，其餘只拿路徑**。

⚠️ 這一支的結構性承諾：**場從來沒有拿過你的程式碼。**
   所以這裡**沒有** tarball／zipball／clone——那些快 8 倍，但它們會把整包下載下來
   再丟掉大部分，於是「只拿 markdown」就從一個**可掃描驗證的結構**退化成一句紀律。
   （`history/131`：禁令做在結構上，不是紀律上。實測代價：17s vs 2s。）
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

API = "https://api.github.com"
KNOWLEDGE = "knowledge/"

#: `knowledge/` 底下的層。由**路徑**導出，不猜。
_DIRS = ("concepts", "history", "episodes", "draft", "skills")
_FILES = ("experience", "vision", "principles")   # 三個入口；其餘頂層 md（README…）＝ other


class GitHubError(RuntimeError):
    """呼叫 GitHub 失敗。訊息要能讓人知道下一步做什麼，而**不含 token**。"""


def layer_of(path: str) -> str:
    """`knowledge/history/137-x.md` → `history`；`knowledge/experience.md` → `experience`。"""
    rest = path[len(KNOWLEDGE):] if path.startswith(KNOWLEDGE) else path
    head, _, tail = rest.partition("/")
    if tail:
        return head if head in _DIRS else "other"
    stem = head.rsplit(".", 1)[0] if head.endswith(".md") else ""
    return stem if stem in _FILES else "other"


def _jwt(app_id: str, pem: bytes) -> str:
    """App 的身分憑證（RS256，10 分鐘）。用 `cryptography` 簽，不引入 JWT 套件。"""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    key = serialization.load_pem_private_key(pem, password=None)
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")   # noqa: E731
    now = int(time.time())
    head = b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    # iat 往前 60 秒：GitHub 對時鐘漂移很敏感，這是它自己文件建議的
    body = b64(json.dumps({"iat": now - 60, "exp": now + 540, "iss": str(app_id)},
                          separators=(",", ":")).encode())
    sig = b64(key.sign(head + b"." + body, padding.PKCS1v15(), hashes.SHA256()))
    return (head + b"." + body + b"." + sig).decode()


@dataclass
class GitHubApp:
    app_id: str
    private_key: bytes
    _tok: str = field(default="", repr=False)     # ⚠️ repr=False：別讓 token 進 log
    _tok_exp: float = 0.0
    _inst: str = ""

    # ── 低層 ──
    def _req(self, url: str, token: str, kind: str, method: str = "GET"):
        r = urllib.request.Request(url, method=method, headers={
            "Authorization": f"{kind} {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "KnowField"})
        try:
            with urllib.request.urlopen(r, timeout=30) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            msg = {401: "憑證不對——檢查 App ID 與 private key",
                   403: "被拒絕（權限或速率額度）",
                   404: "找不到——這個 repo 可能沒有授權給 App"}.get(e.code, f"HTTP {e.code}")
            raise GitHubError(f"{msg}（{url.replace(API, '')}）") from None

    def token(self) -> str:
        """installation token（1 小時）。⚠️ **現鑄、只留在記憶體、不落庫**。"""
        if self._tok and time.time() < self._tok_exp - 60:
            return self._tok
        jwt = _jwt(self.app_id, self.private_key)
        insts = self._req(f"{API}/app/installations", jwt, "Bearer")
        if not insts:
            raise GitHubError("App 還沒安裝到任何帳號——到 App 設定頁按 Install App")
        self._inst = str(insts[0]["id"])
        r = self._req(f"{API}/app/installations/{self._inst}/access_tokens", jwt, "Bearer", "POST")
        self._tok, self._tok_exp = r["token"], time.time() + 3600
        return self._tok

    def _get(self, path: str):
        return self._req(f"{API}{path}", self.token(), "token")

    # ── 高層 ──
    def repos(self) -> list[dict]:
        """App 看得到哪些 repo（分頁走完——**取樣不是列舉**）。"""
        out, page = [], 1
        while True:
            r = self._get(f"/installation/repositories?per_page=100&page={page}")
            out += [{"repo": x["full_name"], "private": bool(x["private"]),
                     "branch": x["default_branch"]} for x in r["repositories"]]
            if len(out) >= r["total_count"] or not r["repositories"]:
                return out
            page += 1

    def fetch(self, repo: str, workers: int = 8) -> dict:
        """一個 repo → `{branch, private, paths, truncated, items}`。

        `items` 只有 `knowledge/**` 的 `.md`；`paths` 是**整棵樹的路徑**（不含內容）。
        """
        meta = self._get(f"/repos/{repo}")
        branch = meta["default_branch"]        # ⚠️ 不寫死 main（VizGPT 是 knowledge-python）
        tree = self._get(f"/repos/{repo}/git/trees/{branch}?recursive=1")
        blobs = [x for x in tree["tree"] if x["type"] == "blob"]
        want = [x for x in blobs
                if x["path"].startswith(KNOWLEDGE) and x["path"].endswith(".md")]

        def one(x):
            b = self._get(f"/repos/{repo}/git/blobs/{x['sha']}")
            return {"path": x["path"], "layer": layer_of(x["path"]),
                    "body": base64.b64decode(b["content"]).decode("utf-8", "replace")}

        with ThreadPoolExecutor(max(1, workers)) as ex:
            items = list(ex.map(one, want))
        return {"branch": branch, "private": bool(meta["private"]),
                "paths": [x["path"] for x in blobs],
                # ⚠️ 截斷了要**說**——一份不完整的樹會讓死指標報告變成看起來很權威的漏報
                "truncated": bool(tree.get("truncated")),
                "items": items}


def app_from_config(cfg) -> GitHubApp | None:
    """`None` ＝ 沒設定 ⇒ 這個功能不啟用，其餘一切照常。"""
    import os
    import pathlib
    app_id = getattr(cfg, "github_app_id", "")
    pem = getattr(cfg, "github_private_key", "")
    path = getattr(cfg, "github_private_key_path", "")
    if not app_id:
        return None
    if not pem and path:
        p = pathlib.Path(os.path.expanduser(path))
        if not p.is_file():
            raise GitHubError(f"讀不到 private key：{path}")
        pem = p.read_text(encoding="utf-8")
    if not pem:
        return None
    return GitHubApp(app_id=str(app_id), private_key=pem.encode())
