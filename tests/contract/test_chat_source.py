"""契約：帶著一份來源聊（spec 042）。離線注入、零外呼。

⚠️ 本檔的核心是 `test_injected_even_when_no_retrieval`：**撒網停用**時仍要進得去。
來源本來就會被撒網撈到（`_chat_corpus`），拿有撒網的環境驗這一刀，驗的是既有功能。
"""
import json
import unittest

from fastapi.testclient import TestClient

from knowfield.ingest.service import ContentIngestService
from knowfield.store.repository import Repository
from tests.web_helpers import build_app, temp_db


class StubEmbedder:
    def embed(self, text): return [1.0, 0.0]
    def embed_many(self, texts): return [[1.0, 0.0] for _ in texts]


_BODY = ("# Manifolds\n\n"
         + "The zorblatt constant governs how layers untangle data. " * 30
         + "\n\nSee $x_0$ for details.\n")


def _seed(db):
    repo = Repository(db)
    ContentIngestService(repo, StubEmbedder()).ingest_text(_BODY, title="Manifolds")
    url = repo.list_source_groups()[0]["url"]
    repo.close()
    return url


class _Capture:
    """假 chat backend：把收到的 messages 留下來給測試檢查。"""
    def __init__(self): self.messages = None
    def reply(self, messages):
        self.messages = messages
        return "好"
    def stream(self, messages):
        self.messages = messages
        yield "好"


def _app(db):
    app = build_app(db)
    app.state.corpus_search_for_test = lambda q: []      # ⚠️ 撒網停用
    return app


def _sse(resp):
    return [json.loads(l[5:]) for l in resp.text.splitlines() if l.startswith("data:")]


def _ctx(cap):
    return "\n".join(m["content"] for m in (cap.messages or []))


_LONG_TAIL = "The frobnicator threshold is exactly seventeen point four."


def _seed_long(db):
    """長到會觸發份內檢索的來源；⚠️ 關鍵句放在**很後面**，開頭那段拿不到它。"""
    repo = Repository(db)
    # ⚠️ 帶頁碼標記（PDF 來源才有）——比對用的那把尺若不一致就會靜默對不上，
    # 沒有標記的 fixture 測不到那條路徑。
    body = ("# Long\n\n"
            + "\n\n".join(f"<!--kf-page:{i}-->Paragraph {i} about untangling manifolds. " * 40
                           for i in range(40))
            + f"\n\n<!--kf-page:99-->{_LONG_TAIL}\n")
    ContentIngestService(repo, StubEmbedder()).ingest_text(body, title="Long")
    url = repo.list_source_groups()[0]["url"]
    repo.close()
    return url


class TestLongSourceRetrieval(unittest.TestCase):
    """⚠️ 這一類本來沒有，所以份內檢索**靜默退化成只給開頭**時測試全綠——
    真跑才被日誌照出來（import 路徑錯 ＋ 頁碼標記讓比對對不上）。
    短來源永遠走不到這條路徑：要測它就得種一份真的超過上限的。"""

    class _RankBySubstring:
        """假 embedder：含關鍵字的塊拿高分。讓「有沒有把命中的塊帶進來」變成確定性的斷言。"""
        def __init__(self, needle): self.needle = needle
        def embed(self, text):
            return [1.0, 0.0] if self.needle in text else [0.0, 1.0]
        def embed_many(self, texts): return [self.embed(t) for t in texts]

    def test_ranked_tail_chunk_reaches_context(self):
        db = temp_db(); url = _seed_long(db)
        app = build_app(db)
        app.state.corpus_search_for_test = lambda q: []
        app.state.embedder_for_test = self._RankBySubstring("frobnicator")
        cap = _Capture(); app.state.chat_backend_for_test = cap
        TestClient(app).post("/api/chat/stream", json={
            "history": [], "message": "frobnicator threshold 是多少", "source_url": url})
        # ⚠️ 只看**來源那一則**。第一版串了全部訊息，於是被**使用者自己的提問**滿足
        # （問句裡就有 frobnicator），兩次反向攻擊都撞不動——與 041 的同義反覆同一族：
        # **斷言被你以為之外的東西滿足了**。
        blocks = [m["content"] for m in cap.messages if "收進的來源" in m["content"]]
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertIn("此處是開頭", block, "前提：這份必須真的觸發節錄")
        self.assertIn("frobnicator", block, "份內檢索沒把命中的塊帶進來（可能靜默退化成只給開頭）")


class TestSourceInChat(unittest.TestCase):
    def _run(self, db, url, **body):
        app = _app(db)
        cap = _Capture()
        app.state.chat_backend_for_test = cap
        c = TestClient(app)
        payload = {"history": [], "message": "這份在講什麼", **body}
        r = c.post("/api/chat/stream", json=payload)
        return cap, _sse(r)

    def test_injected_even_when_no_retrieval(self):
        """⚠️ FR-003／SC-002：撒網停用時仍要進得去——這是本刀存在的理由。"""
        db = temp_db(); url = _seed(db)
        cap, _ = self._run(db, url, source_url=url)
        self.assertIn("zorblatt", _ctx(cap))

    def test_no_source_url_means_no_injection(self):
        """FR-011：沒帶就跟現況一樣（撒網已停用 ⇒ 脈絡裡不該有這份）。"""
        db = temp_db(); url = _seed(db)
        cap, _ = self._run(db, url)
        self.assertNotIn("zorblatt", _ctx(cap))

    def test_deduped_against_retrieval(self):
        """⚠️ FR-007／SC-005：同一份既被帶入又被撒網命中時，只算一份證言。
        不去重的話模型會把同一段當成兩個獨立佐證，而畫面上看不出來。"""
        db = temp_db(); url = _seed(db)
        app = build_app(db)

        class _Hit:                                   # 假撒網結果，正好是同一份
            kind = "corpus"; title = "Manifolds"; url = None
            snippet = "The zorblatt constant governs how layers untangle data."
        _Hit.url = url
        app.state.corpus_search_for_test = lambda q: [_Hit()]
        cap = _Capture(); app.state.chat_backend_for_test = cap
        TestClient(app).post("/api/chat/stream",
                             json={"history": [], "message": "這份在講什麼", "source_url": url})
        blocks = [m for m in cap.messages if "收進的來源" in m["content"]]
        self.assertEqual(len(blocks), 1)
        joined = _ctx(cap)
        self.assertNotIn("（你收藏的）Manifolds", joined, "撒網那份沒被去掉")

    def test_missing_source_is_quiet(self):
        """來源不存在 → 安靜當作沒帶，不 5xx（與 041 不同：那邊是明講找不到那篇文章，
        但來源的 url 是使用者可能手改的網址參數，噪音成本比較高）。"""
        db = temp_db(); _seed(db)
        cap, evs = self._run(db, "x", source_url="nope://gone")
        self.assertEqual(evs[-1].get("type"), "done")

    def test_bare_does_not_inject(self):
        db = temp_db(); url = _seed(db)
        cap, _ = self._run(db, url, source_url=url, bare=True)
        self.assertNotIn("zorblatt", _ctx(cap))

    def test_storage_unchanged(self):
        """FR-009。"""
        db = temp_db(); url = _seed(db)
        repo = Repository(db); before = repo.get_source_chunks(url); repo.close()
        self._run(db, url, source_url=url)
        repo = Repository(db); after = repo.get_source_chunks(url); repo.close()
        self.assertEqual(before, after)
