"""FastAPI web app。唯一 import 框架之處；核心全複用、零改動。

頁面（產品轉向後，新聞分診子系統已退役，見 knowledge/history/068）：
/（導向 /chat）、/chat*、/roots、/conversations*、/ingest、/library、/ask。
後端失敗經例外處理器攔成友善繁中頁（FR-009、experience 教訓 3）。
可覆寫點（app.state）供測試注入：repo_factory、chat_factory、rag_answer_factory 等。
"""

from __future__ import annotations

import contextvars
import json
import re
from pathlib import Path

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import (
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)

from ..backends.openai_api import OpenAIError
from ..config import Config
from ..sources.base import SourceUnavailable
from ..logging_setup import get_logger
from ..store.repository import Repository
from .cache import TTLCache

_log = get_logger("knowfield.web")


def _knowledge_label(repo, kind: str, ref) -> str:
    """一個知識在畫面上的名字（spec 049；spec 050 起 `ref` 對來源是 url）。"""
    if kind == "conversation":
        c = repo.get_conversation(ref)
        return f"💬 {c.title}" if c else f"💬 #{ref}"
    if kind == "article":
        a = repo.get_article(ref)
        return f"📝 {a.get('title') or a.get('topic')}" if a else f"📝 #{ref}"
    if kind == "source":
        r = repo.conn.execute(
            f"SELECT MIN(title) AS t FROM digest_entries WHERE {repo._OWN} AND url=%s", (ref,)).fetchone()
        return f"📚 {(r['t'] if r and r['t'] else ref)[:40]}"
    r = repo.conn.execute(
        f"SELECT claim FROM why_nodes WHERE {repo._OWN} AND id=%s", (ref,)).fetchone()
    return f"💡 {(r['claim'] or '')[:40]}" if r else f"💡 #{ref}"


_KINDS = ("conversation", "why_node", "article", "source")


def _parse_items(raw) -> list[tuple[str, object]]:
    """把 body 的 `items` 轉成 [(kind, ref)]。⚠️ 來源的 ref 是 url（字串），其餘是 int。"""
    out = []
    for it in (raw or []):
        k = (it.get("kind") or "").strip()
        if k not in _KINDS:
            raise ValueError(f"不認得的知識種類：{k}")
        ref = it.get("ref")
        out.append((k, str(ref) if k == "source" else int(ref)))
    return out


def _domain_of(body) -> int | None:
    """請求裡的「當前領域」（spec 051）。0／缺 ＝ 根領域＝沒有訊號。"""
    try:
        return int(body.get("domain_id") or 0) or None
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# spec 042：帶入來源的脈絡預算。比文章的 6000 寬——來源是這一輪明講的談話對象，
# 而且實測一份 20k–38k 字；但仍要留空間給理解與對話本身。
_SOURCE_CAP = 12000
_SOURCE_HEAD = 2500        # 開頭保底：沒有它就答不出「這篇整體在講什麼」


# spec 039：譯文快取的存活門檻。遠比 spec 028 的 7 天寬鬆——譯文能重生，
# 清掉的代價只是下次要再等一次翻譯，不是資料遺失。
_TRANSLATION_TTL_DAYS = 180


def _days_ago_iso(days: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _pump(gen):
    """把 token 逐段轉成 SSE 吐出，回 `(全文, 截斷原因)`。

    截斷有兩種、在畫面上長得一模一樣，所以**都要標出來**（憲章 V）——分不出來就會像上次一樣
    只治到其中一種（調大 max_tokens 治的是 length，連線斷的完全沒被看見）：
    - `"length"`：模型撞 max_tokens 被切（來自 `finish_reason`，走 generator 回傳值上來）。
    - `"connection"`：上游中途斷線——**已收到的字保留**、標明不完整，不整段丟掉。
    一個 token 都還沒吐就失敗 → 往上拋，由呼叫端攔成 error 事件（沒有半截可留，報錯才對）。
    """
    full = ""
    try:
        while True:
            try:
                delta = next(gen)
            except StopIteration as stop:
                return full, ("length" if (stop.value or "") == "length" else "")
            full += delta
            yield _sse({"type": "token", "text": delta})
    except Exception as e:  # noqa: BLE001 - 邊界要攔所有失敗，不只預期的那種
        if not full:
            raise
        _log.error("對話串流中途斷", extra={"extra": {"reason": str(e), "chars": len(full)}})
        return full, "connection"


#: spec 067：這個請求是在哪個身分底下。⚠️ 用 contextvar 而不是改 `repo_factory` 的簽章
#: ——後者要動幾十個呼叫點，而**漏掉一個就是跨身分外洩，且不會報錯**。
_CURRENT_PERSONA: "contextvars.ContextVar[int | None]" = contextvars.ContextVar(
    "kf_persona", default=None)


def _default_repo_factory(config: Config) -> Repository:
    from ..cli.fetchers import DEFAULT_SOURCES
    repo = Repository(config.database_url or None,   # spec 034：PG DSN（env）
                      persona=_CURRENT_PERSONA.get())
    if not repo.list_sources():
        for s in DEFAULT_SOURCES:
            repo.upsert_source(s)
    return repo


def _default_rag_answer(config: Config, repo_factory, question: str, today: bool,
                        lang: str):
    """web 問答：組 embedder/answerer＋RagService→answer。可被 rag_answer_factory 覆寫（測試）。"""
    from ..backends.factory import make_answerer, make_embedder
    from ..rag.service import RagService
    from ..rag.types import Scope
    repo = repo_factory(config)
    try:
        service = RagService(repo, make_embedder(config), make_answerer(config),
                             top_k=config.rag_top_k, min_score=config.rag_min_score,
                             explainer_weight=config.rag_explainer_weight,
                             root_weight=config.rag_root_weight)
        return service.answer(question, Scope(today=today), lang=lang)
    finally:
        repo.close()


def _default_seed_ingest(config: Config, repo_factory, ref: str, explainer: bool):
    """web 種子 ingest：組後端＋SeedService→ingest。可被 seed_ingest_factory 覆寫（測試）。"""
    from ..backends.factory import make_article_backend, make_embedder
    from ..seed.service import SeedService
    from ..summarize.article import ArticleBuilder
    repo = repo_factory(config)
    try:
        builder = ArticleBuilder(backend=make_article_backend(config))
        return SeedService(repo, builder, make_embedder(config)).ingest(ref, explainer)
    finally:
        repo.close()


def create_app() -> FastAPI:
    app = FastAPI(title="KnowField")
    app.state.config = Config.from_env()
    app.state.cache = TTLCache()
    app.state.repo_factory = _default_repo_factory
    app.state.rag_answer_factory = lambda question, today, lang: _default_rag_answer(
        app.state.config, app.state.repo_factory, question, today, lang)
    app.state.seed_ingest_factory = lambda ref, explainer: _default_seed_ingest(
        app.state.config, app.state.repo_factory, ref, explainer)

    from ..ingest.convert import MistralDocConverter
    app.state.doc_converter = MistralDocConverter(app.state.config)  # spec 030；測試可注入
    app.state.web_fetch = None                                       # 網頁抓取（測試可注入；None=預設）

    @app.get("/healthz")   # k8s liveness/readiness 探針；門鎖豁免（見 auth gate），免登入可探
    async def healthz():
        """健康 ＋ **可選能力是否活著**。

        ⚠️ 為什麼要有 capabilities：spec 037 上線後在 prod 完全沒作用——OpenCC 被放進可選
        extra、Dockerfile 只裝 `.[web]`，identity fallback 生效：不轉換、不報錯，
        而 `/healthz` 照樣回 `{"ok": true}`。**一個對「功能是不是啞的」不敏感的健康檢查，
        沒有在檢查健康。** 這裡只回布林，不回任何設定內容（免登入可探）。

        `ok` 與能力分開：能力缺席是降級不是掛掉，探針不該因此重啟 pod。
        """
        from ..backends.factory import make_translate_backend
        from ..text import s2t
        return {"ok": True,
                "capabilities": {
                    "s2t": s2t.available(),                                   # 簡→繁（spec 037）
                    "translate": make_translate_backend(app.state.config) is not None,  # 英→繁（spec 038）
                }}

    def _content_ingest(kind, **kw):
        """貼上/PDF/URL 收進：切塊→存成 corpus（spec 030）。轉檔器/抓取器可注入。"""
        from ..backends.factory import make_embedder
        from ..ingest.service import ContentIngestService
        cfg = app.state.config
        repo = app.state.repo_factory(cfg)
        try:
            svc = ContentIngestService(repo, make_embedder(cfg), app.state.doc_converter,
                                       chat_backend=_chat_backend(), media_dir=cfg.media_dir)
            note, at = kw.get("note", ""), kw.get("ingested_at", "")
            if kind == "text":
                return svc.ingest_text(kw["text"], kw.get("title", ""),
                                       html=kw.get("html", ""), clean=kw.get("clean", False),
                                       source_url=kw.get("source_url", ""), note=note, ingested_at=at)
            if kind == "url":
                return svc.ingest_url(kw["url"], kw.get("title", ""), http_get=app.state.web_fetch,
                                      note=note, ingested_at=at)
            if kind == "youtube":
                return svc.ingest_youtube(kw["url"], kw.get("title", ""), http_get=app.state.web_fetch)
            return svc.ingest_pdf(pdf_bytes=kw.get("pdf_bytes"), pdf_url=kw.get("pdf_url", ""),
                                  title=kw.get("title", ""), note=note, ingested_at=at)
        finally:
            repo.close()
    app.state.content_ingest = _content_ingest

    # 跟你的場聊天（spec 022）：可注入的多輪對話／蒸餾／佐證（測試覆寫）
    def _chat_backend():
        from ..backends.factory import make_chat_backend
        return getattr(app.state, "chat_backend_for_test", None) or make_chat_backend(app.state.config)

    def _extractor():
        """根因萃取後端（spec 032 整理成理解，復用階段 10）；可注入離線 stub（教訓 1）。"""
        from ..backends.factory import make_root_cause_extractor
        return getattr(app.state, "extractor_for_test", None) or make_root_cause_extractor(app.state.config)

    def _chat_search(message):
        """每輪撒網找佐證（一邊聊一邊找）；失敗→空、不拖垮對話（教訓 3）。"""
        search = getattr(app.state, "chat_search_for_test", None)
        try:
            if search is not None:
                results = search(message)
            else:
                from ..backends.factory import make_web_search
                results = make_web_search(app.state.config).search(message, news=False)
        except (SourceUnavailable, OpenAIError):
            return []
        return list(results)[:6]

    def _chat_corpus(query):
        """檢索使用者收進的相關資料，當「你收藏的」證言（spec 029）。失敗/無語料→空、不擋聊天（教訓 3）。"""
        inj = getattr(app.state, "corpus_search_for_test", None)
        if inj is not None:
            try:
                return list(inj(query))
            except Exception:  # noqa: BLE001
                return []
        try:
            import types as _t

            from ..backends.factory import make_embedder
            from ..rag.service import retrieve_corpus
            cfg = app.state.config
            repo = app.state.repo_factory(cfg)
            try:
                hits = retrieve_corpus(repo, make_embedder(cfg), query,
                                       top_k=cfg.rag_top_k, min_score=cfg.rag_min_score)
            finally:
                repo.close()
            return [_t.SimpleNamespace(
                title=(getattr(h, "headline", "") or getattr(h, "title", "")),
                snippet=getattr(h, "body", "") or "", url=getattr(h, "url", ""),
                kind="corpus") for h in hits]
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("聊天檢索收進失敗", extra={"extra": {"reason": str(e)}})
            return []

    def _fetch_message_urls(message):
        """偵測訊息裡的網址→伺服器端抓內容（best-effort，抓不到也回一筆 note，教訓 3）。"""
        urls = re.findall(r"https?://[^\s，。）)】\]]+", message or "")[:3]
        if not urls:
            return []
        fetch = getattr(app.state, "chat_fetch_for_test", None)
        out = []
        for u in dict.fromkeys(urls):        # 去重、保序
            try:
                if fetch is not None:
                    out.append(fetch(u))
                else:
                    from ..seed.fetch import fetch_url
                    it = fetch_url(u)
                    out.append({"url": u, "title": it.title, "body": it.abstract})
            except Exception as e:  # noqa: BLE001 - 抓不到不崩，回 note（教訓 3）
                _log.error("對話抓網址失敗", extra={"extra": {"reason": str(e), "url": u}})
                out.append({"url": u, "title": "", "body": ""})
        return out

    def _default_chat(history, message, bare=False):
        from ..chat.field_chat import FieldChat
        # bare＝這輪屏蔽知識庫：不查理解、不撒網、不查收藏
        if bare:
            roots = []
        else:
            repo = app.state.repo_factory(app.state.config)
            try:
                roots = repo.list_why_nodes("anointed")
            finally:
                repo.close()
        fc = FieldChat(_chat_backend())
        url_contents = _fetch_message_urls(message)   # 貼的網址→讀進來（best-effort）
        if bare:
            sources = []
        else:
            q = fc.search_query(history, message)        # LLM 先把問題轉成好 query（消歧義）
            # web 撒網＋收進的文章併成一個連號來源清單（web 在前、收進在後，帶 kind）
            sources = list(_chat_search(q)) + _chat_corpus(message)
        text = fc.reply(history, message, roots, sources, bare=bare,
                        max_history=app.state.config.chat_context_messages,
                        url_contents=url_contents)
        # 只顯示回答真的引用到的來源（[n]）——沒被引用的（多半不相關）一律不列，濾掉垃圾
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
        numbered = [{"n": i, "url": s.url, "title": s.title or s.url,
                     "kind": getattr(s, "kind", "web")}
                    for i, s in enumerate(sources, 1) if i in cited]
        return text, numbered
    app.state.chat_factory = _default_chat

    def _default_distill(history):
        from ..chat.field_chat import FieldChat
        repo = app.state.repo_factory(app.state.config)
        try:
            roots = repo.list_why_nodes("anointed")   # 傳既有理解→標「已收過」（去重）
        finally:
            repo.close()
        return FieldChat(_chat_backend()).distill(history, roots)
    app.state.distill_factory = _default_distill

    def _default_title(messages):
        from ..chat.field_chat import FieldChat
        return FieldChat(_chat_backend()).title(messages)
    app.state.title_factory = _default_title

    def _default_suggest_backend():
        """spec 065：建議整理用的 LLM。⚠️ 只做**命名與合併**，成員來自結構。"""
        return _chat_backend()
    app.state.suggest_backend_factory = _default_suggest_backend

    def _default_district_embedder():
        """spec 069：劃界用的 embedder。⚠️ 一定要跟語料**同一個模型**——
        混維度的話會算出一個看起來正常的垃圾距離。"""
        from ..backends.factory import make_embedder
        return make_embedder(app.state.config)
    app.state.district_embedder_factory = _default_district_embedder

    def _default_segment(messages):
        from ..chat.field_chat import FieldChat
        return FieldChat(_chat_backend()).segment(messages)
    app.state.segment_factory = _default_segment

    def _convo_title(messages):
        """自動由來標題；失敗/空 → 退回首個 user 訊息截斷（教訓 3，不讓存對話崩）。"""
        try:
            t = (app.state.title_factory(messages) or "").strip()
        except Exception as e:  # noqa: BLE001
            _log.error("生對話標題失敗", extra={"extra": {"reason": str(e)}})
            t = ""
        if not t:
            first = next((m.get("content", "") for m in messages
                          if m.get("role") == "user"), "")
            t = first.strip()[:20] or "（未命名對話）"
        return t
    app.state._convo_title = _convo_title


    @app.exception_handler(OpenAIError)
    async def _backend_error(request: Request, exc: OpenAIError):
        _log.error("web 後端失敗", extra={"extra": {"reason": str(exc)}})
        return PlainTextResponse(f"後端暫時無法回應：{exc}", status_code=503)

    @app.get("/ask")
    async def ask():
        # 舊入口導向 SPA（問答併進聊天，帶膜、能引用「你收藏的」）。
        return RedirectResponse("/", status_code=302)


    def _root_count():
        repo = app.state.repo_factory(app.state.config)
        try:
            return len(repo.list_why_nodes("anointed"))
        finally:
            repo.close()

    def _parse_history(history: str) -> list:
        try:
            h = json.loads(history or "[]")
            return h if isinstance(h, list) else []
        except Exception:  # noqa: BLE001
            return []

    # 收尾缺口提醒（spec 025）：對話夠長且自上次收以來又長出一大段未蒸餾 → 提醒（只提醒、不自動冊封）
    _NUDGE_MIN_TOTAL = 20     # 訊息數（約 10 輪）以下不吵
    _NUDGE_GAP = 16           # 自上次收又長出 ≥ 約 8 輪才提醒

    def _temp_id(v) -> int:
        try:
            return int(v) if v else 0
        except (TypeError, ValueError):
            return 0

    def _distill_nudge(hist: list, last_captured: str):
        from ..chat.capture import distill_gap
        try:
            lc = int(last_captured or 0)
        except (TypeError, ValueError):
            lc = 0
        gap = distill_gap(len(hist), lc, _NUDGE_MIN_TOTAL, _NUDGE_GAP)
        return {"from": gap[0], "to": gap[1]} if gap else None


    def _load_source_context(u: str, query: str):
        """spec 042：把一份收進的來源整理成可注入的脈絡。找不到回 None。

        ⚠️ 注入的是**儲存層原文**——不是 `/api/source` 那條顯示路徑的繁體化／翻譯結果。
        譯文是 AI 產物，餵回去是回灌線的縮小版；餵原文反而讓模型替使用者抓翻譯的失真（FR-004）。
        ⚠️ 長來源**不硬切**——切點一律落在原始塊邊界，並在脈絡裡明講節錄了多少（FR-005）。
        """
        from ..chat.source_context import select_source_context
        repo = app.state.repo_factory(app.state.config)
        try:
            chunks = [re.sub(r"<!--kf-page:\d+-->", "", c) for c in repo.get_source_chunks(u)]
            if not chunks:
                return None
            title = repo.source_title(u)
            ranked: list[int] = []
            if len("\n\n".join(chunks)) > _SOURCE_CAP:
                ranked = _rank_chunks_in_source(repo, u, chunks, query)
        finally:
            repo.close()
        ctx = select_source_context(chunks, ranked, _SOURCE_CAP, _SOURCE_HEAD)
        _log.info("帶入來源", extra={"extra": {"url": u, "units": ctx.total_units,
                                              "shown": ctx.shown_units,
                                              "excerpted": ctx.excerpted}})
        return {"url": u, "title": title, "body": ctx.body,
                "total_units": ctx.total_units, "shown_units": ctx.shown_units,
                "excerpted": ctx.excerpted}

    def _rank_chunks_in_source(repo, u: str, chunks: list[str], query: str) -> list[int]:
        """份內檢索：把既有的語料檢索**範圍縮到這一份**。失敗→空（退化成只給開頭，不擋聊天）。

        不新增檢索機制——來源的每個塊本來就是一列 `digest_entries`（YAGNI）。
        """
        try:
            from ..backends.factory import make_embedder
            from ..ranking.embeddings import cosine
            from ..rag.service import embedder_tag
            emb = getattr(app.state, "embedder_for_test", None) or make_embedder(app.state.config)
            entries = [e for e in repo.list_corpus_entries() if e.url == u]
            if not entries:
                return []
            vecs = repo.ensure_embeddings(entries, emb, embedder_tag(emb))
            qv = emb.embed(query)
            order = sorted(entries, key=lambda e: cosine(qv, vecs[e.entry_id]), reverse=True)
            # ⚠️ 塊已去過頁碼標記，語料條目的 body 沒有——比對前要用同一把尺，
            # 否則對不上、靜默退化成「只給開頭」（真跑時就是這樣被日誌照出來的）。
            by_body = {re.sub(r"<!--kf-page:\d+-->", "", c): i for i, c in enumerate(chunks)}
            hits = [by_body[k] for e in order
                    if (k := re.sub(r"<!--kf-page:\d+-->", "", e.body or "")) in by_body]
            if not hits:
                _log.info("份內檢索沒對上任何塊，退回只給開頭",
                          extra={"extra": {"url": u, "entries": len(entries)}})
            return hits
        except Exception as exc:  # noqa: BLE001 - 檢索失敗不該擋住聊天（教訓 3）
            # ⚠️ 原因一定要寫出來。第一版只寫「失敗」，真跑時我看得到它退化、
            # 卻看不出是 import 路徑錯——那是憲章 V 要擋的靜默（同 history/102）。
            _log.info("份內檢索失敗，退回只給開頭",
                      extra={"extra": {"url": u, "reason": f"{type(exc).__name__}: {exc}"}})
            return []

    def _stream_gen(hist, message, bare, article_id=0, source_url=""):
        """SSE 生成器：/chat/stream 與 /api/chat/stream 共用（協定：stage/token/done/error）。
        bare＝這輪暫時屏蔽知識庫：不注入理解、不撒網、不查收藏。
        article_id＝使用者**明確**帶進來的一篇生成文章（spec 041），0＝沒帶。
        source_url＝使用者**明確**帶進來的一份收進來源（spec 042），空＝沒帶。"""
        from ..chat.field_chat import FieldChat
        cfg = app.state.config
        if not message:
            yield _sse({"type": "done", "text": ""})
            return
        # spec 041：使用者明確帶的一篇生成文章。找不到就明講，不靜默略過（憲章 V）。
        _article = None
        if article_id and not bare:
            _r = app.state.repo_factory(cfg)
            try:
                _a = _r.get_article(article_id)      # 回 dict | None（非物件）
            finally:
                _r.close()
            if not _a:
                yield _sse({"type": "error", "message": "找不到那份應用（可能已封存）。"})
                return
            _article = {"id": _a.get("id", article_id),
                        "title": _a.get("title") or "",
                        "markdown": _a.get("markdown") or ""}
        # spec 042：使用者明確帶的一份來源。⚠️ 這一步**與撒網無關**——帶了就進得去，
        # 那正是本刀與現況的全部差別（撒網的失敗是沉默的：沒撈到你不會知道）。
        _source = None
        if source_url and not bare:
            _source = _load_source_context(source_url, message)
        if bare:
            roots = []
        else:
            repo = app.state.repo_factory(cfg)
            try:
                roots = repo.list_why_nodes("anointed")
            finally:
                repo.close()
        fc = FieldChat(_chat_backend())
        try:
            url_contents = _fetch_message_urls(message)
            if url_contents:
                yield _sse({"type": "stage", "text": "讀取你貼的網址…"})
            if bare:
                sources = []
            else:
                yield _sse({"type": "stage", "text": "找關鍵字…"})
                q = fc.search_query(hist, message)
                yield _sse({"type": "stage", "text": "撒網找佐證…"})
                web = _chat_search(q)
                yield _sse({"type": "stage", "text": "翻你收進的資料…"})
                sources = list(web) + _chat_corpus(message)   # web＋收進併成連號清單
                if _source:
                    # ⚠️ FR-007：同一份既被帶入又被撒網命中 → 只算一份證言。
                    # 不去重的話模型會把同一段當成**兩個獨立佐證**，而畫面上完全看不出來。
                    sources = [s for s in sources
                               if (getattr(s, "url", "") or "") != _source["url"]]
            yield _sse({"type": "stage", "text": "回答中…"})
            full, truncated = yield from _pump(
                fc.reply_stream(hist, message, roots, sources, bare=bare, article=_article,
                                source=_source,
                                max_history=cfg.chat_context_messages,
                                url_contents=url_contents))
            cited = {int(n) for n in re.findall(r"\[(\d+)\]", full)}
            numbered = [{"n": i, "url": s.url, "title": s.title or s.url,
                         "kind": getattr(s, "kind", "web")}
                        for i, s in enumerate(sources, 1) if i in cited]
            # 有撒到、但沒被引用的來源 → 折疊區「也找到（未直接引用）」（不進存檔）
            extra = [{"n": i, "url": s.url, "title": s.title or s.url,
                      "kind": getattr(s, "kind", "web")}
                     for i, s in enumerate(sources, 1) if i not in cited]
            yield _sse({"type": "done", "text": full, "sources": numbered, "found_extra": extra,
                        "truncated": truncated})
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("場對話串流失敗", extra={"extra": {"reason": str(e)}})
            yield _sse({"type": "error", "text": str(e)})
        except Exception as e:  # noqa: BLE001 - 邊界要攔所有失敗，不只預期那種（同 digest builder 那條教訓）
            _log.error("場對話串流未預期失敗", extra={"extra": {"reason": str(e)}})
            yield _sse({"type": "error", "text": "對話中斷了，請重試。"})


    def _do_anoint(claim, ladder, evidence_urls, save_convo, history, temp_id, kind="",
                   src_from=0, src_to=0, domain_id=None,
                   source_entry_id=0, conversation_id=None, origin=""):
        """人閘門冊封（原則 5）：唯有人按此才寫 bedrock。冪等去重＋選用連對話由來（spec 023/028）。
        回 (status, claim, msg)。/chat/anoint 與 /api/chat/anoint 共用（行為一份、天然一致）。"""
        from ..chat.capture import norm_claim
        claim = (claim or "").strip()
        if not claim:
            return "empty", claim, None
        steps = [s.strip() for s in (ladder or "").splitlines() if s.strip()]
        urls = [u.strip() for u in (evidence_urls or "").replace("，", ",").replace("\n", ",").split(",")
                if u.strip().startswith("http")]
        repo = app.state.repo_factory(app.state.config)
        existing = {norm_claim(r.claim): r.id for r in repo.list_why_nodes("anointed")}
        key = norm_claim(claim)
        if key in existing:                     # 已收過→不重複新增（原則 6 反囤積）
            wid = existing[key]
            status = "exists"
            msg = f"這條你已經收過了：「{claim[:40]}」（沒有重複新增）"
        else:
            wid = repo.add_why_node(claim, urls, [], False, source_entry_id, _now_iso(),
                                    ladder=steps, kind=kind, src_from=src_from, src_to=src_to,
                                    conversation_id=conversation_id, origin=origin)
            repo.anoint_why_node(wid)
            status = "created"
            msg = f"已存進你的知識庫：「{claim[:40]}」（可到『理解』頁檢視或封存）"
        if save_convo == "1":                   # 連同這段對話存成由來（既有或新建都連）
            messages = _parse_history(history)
            if messages:
                tid = _temp_id(temp_id)
                if tid:                         # 有暫存→升永久同一筆＋連根因（spec 028，不新增）
                    repo.promote_conversation(tid, _convo_title(messages), wid)
                else:
                    # ⚠️ 這是**新建**的對話（`save_conversation` 不帶領域）
                    # ⇒ 它自己也是剛出生的葉節點，也要歸位，否則理解繼承到的是一個
                    #    住在根領域的父親——看起來像「繼承成功」，其實是退回當前領域。
                    cid = repo.save_conversation(_convo_title(messages), messages, wid)
                    repo.place_new("conversation", cid, current=domain_id)
                if status == "created":
                    msg += "，並存下這段互動當它的由來"
        # spec 051：出生就歸位。⚠️ **一定要在這裡**——上面的 save_convo 分支才剛把對話連上去，
        # 早一步呼叫的話 `_neighbours` 是空的，理解會安靜地落在根領域，
        # 而那看起來跟「本來就沒出處」一模一樣。
        if status == "created":
            repo.place_new("why_node", wid, current=domain_id)
        repo.close()
        return status, claim, msg


    # ══ /api：JSON/SSE 門面（re-platform 階段一，vision 階段 27）══
    # 共用上面的服務閉包（_stream_gen/_do_anoint/distill_factory/repo）——零邏輯重寫、行為天然一致。
    from fastapi.responses import JSONResponse as _JSON

    @app.get("/api/chat/state")
    async def api_chat_state():
        repo = app.state.repo_factory(app.state.config)
        temps = [c for c in repo.list_conversations()]
        repo.close()
        recent = temps[0] if temps else None
        return _JSON({"root_count": _root_count(),
                      "recent_temp": ({"id": recent.id, "title": recent.title,
                                       "messages": recent.messages} if recent else None)})

    @app.post("/api/chat/stream")
    async def api_chat_stream(request: Request):
        body = await request.json()
        hist = body.get("history") or []
        message = (body.get("message") or "").strip()
        return StreamingResponse(
            _stream_gen(hist, message, bool(body.get("bare")),
                        int(body.get("article_id") or 0),
                        str(body.get("source_url") or "").strip()),
            media_type="text/event-stream")

    @app.post("/api/chat/distill")
    async def api_chat_distill(request: Request):
        body = await request.json()
        try:
            cands = app.state.distill_factory(body.get("history") or [])
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("蒸餾候選失敗", extra={"extra": {"reason": str(e)}})
            return _JSON({"error": str(e)}, status_code=502)
        return _JSON({"candidates": [
            {"claim": c.claim, "kind": c.kind, "ladder": c.ladder,
             "evidence_urls": c.evidence_urls, "already": c.already,
             "src_from": getattr(c, "src_from", 0), "src_to": getattr(c, "src_to", 0)}
            for c in (cands or [])]})

    @app.post("/api/chat/anoint")
    async def api_chat_anoint(request: Request):
        """人閘門冊封（沿用 _do_anoint；React 也只能經此寫地基）。"""
        body = await request.json()
        status, claim, msg = _do_anoint(
            body.get("claim", ""), body.get("ladder", ""), body.get("evidence_urls", ""),
            "1" if body.get("save_convo") else "",
            json.dumps(body.get("history") or [], ensure_ascii=False),
            str(body.get("temp_id") or ""), body.get("kind", ""),
            int(body.get("src_from") or 0), int(body.get("src_to") or 0),
            domain_id=_domain_of(body))
        return _JSON({"status": status, "claim": claim, "msg": msg})

    @app.post("/api/understanding/write")
    async def api_understanding_write(request: Request):
        """spec 062：**人自己寫**一條理解——已經知道的事不必先跟 AI 聊一輪。

        ⚠️ **出處必填，而且是擋住不是警告**。理由是原則性的：AI 蒸餾的候選會經過
        gradient oracle（原則 5 要求它對自己 adversarial，防 folie à deux），
        人自己寫**跳過了那道檢查** ⇒ 出處是它的替代品。
        """
        b = await request.json()
        claim = str(b.get("claim") or "").strip()
        if not claim:
            return _JSON({"error": "理解不能是空的——寫一句你想留下來的主張。"}, status_code=400)

        cid = b.get("conversation_id")
        cid = int(cid) if cid else None
        # ⚠️ 來源的身分是 **url** 不是 id（spec 050 的裁決，`_KIND_TABLE` 同一份）
        #    ——前端拿得到的是 url，id 由這裡解析，別逼介面去猜一個它看不到的東西。
        sid = int(b.get("source_entry_id") or 0)
        if not sid and str(b.get("source_url") or "").strip():
            repo0 = app.state.repo_factory(app.state.config)
            row = repo0.conn.execute(
                f"SELECT MIN(id) AS id FROM digest_entries WHERE {repo0._OWN} AND url=%s",
                (str(b["source_url"]).strip(),)).fetchone()
            repo0.close()
            sid = int(row["id"]) if row and row["id"] else 0
        urls = str(b.get("evidence_urls") or "").strip()
        declared = str(b.get("origin") or "") == "self:judgment"
        has_source = bool(cid or sid or urls)

        # ⚠️ 四種出處擇一。第四種**不是逃生門**，是信任鏈的第三種終點
        #    ——它要**被宣告**，不能靠「什麼都沒填」推導出來。
        if not has_source and not declared:
            return _JSON({"error": "要標出處：選一段互動、一份來源、給一個網址，"
                                   "或明確勾選「這是我自己的判斷，沒有外部依據」。"},
                         status_code=400)
        # 宣告了自己的判斷卻又給了出處 ⇒ 以出處為準（有依據就不是純判斷）
        origin = "self" if has_source else "self:judgment"

        status, claim, msg = _do_anoint(
            claim, b.get("ladder", ""), urls, "", "[]", "", b.get("kind", ""),
            domain_id=_domain_of(b),
            source_entry_id=sid, conversation_id=cid, origin=origin)
        return _JSON({"status": status, "claim": claim, "msg": msg, "origin": origin})

    @app.post("/api/chat/autosave")
    async def api_chat_autosave(request: Request):
        body = await request.json()
        title = None
        try:
            repo = app.state.repo_factory(app.state.config)
            # spec 044：帶入物的由來（這段是帶著哪篇文章／哪份來源開的）。
            # ⚠️ 這是**元資料**——不進 messages、不進模型脈絡，只為了讓 audit 量得到。
            tid = repo.autosave_temporary(_temp_id(str(body.get("temp_id") or "")) or None,
                                          body.get("history") or [], _now_iso(),
                                          str(body.get("carried_kind") or "")[:16],
                                          str(body.get("carried_ref") or "")[:500],
                                          body.get("domain_id"))
            if tid:                        # 回落點標題，讓聊天頁抬頭即時顯示對話名
                c = repo.get_conversation(int(tid))
                title = c.title if c else None
            repo.close()
        except Exception as e:  # noqa: BLE001 - autosave 不擋聊天（教訓 3）
            _log.error("自動暫存失敗", extra={"extra": {"reason": str(e)}})
            tid = None
        return _JSON({"temp_id": tid, "title": title})

    @app.post("/api/chat/save")
    async def api_chat_save(request: Request):
        """獨立存這段對話成永久（人閘門，spec 028）。有暫存→升永久同一筆；無→新建。空→不存。"""
        b = await request.json()
        messages = b.get("history") or []
        if not messages:
            return _JSON({"saved": False, "msg": "這段互動還是空的，沒有東西可存。"})
        repo = app.state.repo_factory(app.state.config)
        tid = _temp_id(str(b.get("temp_id") or ""))
        if tid:                         # 有暫存→升永久同一筆＋生落點標題（不新增）
            repo.promote_conversation(tid, _convo_title(messages))
        else:
            repo.save_conversation(_convo_title(messages), messages, None)
        repo.close()
        return _JSON({"saved": True, "msg": "已存下這段互動（可到『互動存檔』檢視）"})

    @app.post("/api/chat/export")
    async def api_chat_export(request: Request):
        """匯出當前對話給 NotebookLM（as=md/urls）。純唯讀、不落庫（原則 6）。"""
        b = await request.json()
        return PlainTextResponse(
            _export_conversation(b.get("title", ""), b.get("history") or [], b.get("as") or "md"))

    @app.get("/api/roots")
    async def api_roots():
        repo = app.state.repo_factory(app.state.config)
        anointed = repo.list_why_nodes("anointed")
        candidates = repo.list_why_nodes("candidate")
        prov = repo.why_node_provenance()
        sprov = repo.why_node_source_provenance()
        repo.close()

        def _wn(w):
            return {"id": w.id, "claim": w.claim, "evidence_urls": w.evidence_urls,
                    "ladder": w.ladder, "touchstones": w.touchstones, "fog_flag": w.fog_flag,
                    "kind": getattr(w, "kind", ""),
                    "src_from": getattr(w, "src_from", 0), "src_to": getattr(w, "src_to", 0),
                    "origin": getattr(w, "origin", ""),
                    "source_quote": getattr(w, "source_quote", ""),
                    "source_page": getattr(w, "source_page", 0)}
        return _JSON({"anointed": [_wn(w) for w in anointed],
                      "candidates": [_wn(w) for w in candidates],
                      "provenance": {str(k): v for k, v in prov.items()},
                      "source_provenance": {str(k): v for k, v in sprov.items()}})

    # spec 071：把借來的判準收進**收件匣**（＝候選理解）。來源目前是 `knowie-crosscheck`，
    # ⚠️ 但路由**不用餵它的東西命名**——明天判準會從別人**發送**過來，形狀一樣。
    # ⚠️ 匯入是批次的，**收下不是**——一條一條走既有的 `/api/whynode/anoint`（FR-004）。
    #    匯入只是「東西送到你門口」，不等於你收了它。
    @app.post("/api/borrowed/import")
    async def api_borrowed_import(request: Request):
        b = await request.json()
        groups = b.get("groups") or []
        if not isinstance(groups, list):
            return _JSON({"error": "groups 要是一個陣列"}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        r = repo.import_borrowed(groups)
        repo.close()
        return _JSON({"added": len(r["added"]), "skipped": r["skipped"]})

    # ══ /api：其餘頁（re-platform 里程碑二）——共用既有 repo/service ══
    @app.post("/api/whynode/anoint")
    async def api_whynode_anoint(request: Request):
        b = await request.json()
        wid = int(b.get("id") or 0)
        if wid:
            repo = app.state.repo_factory(app.state.config)
            repo.anoint_why_node(wid, (b.get("claim") or "").strip() or None,
                                 (b.get("kind") or "").strip() or None)
            repo.place_new("why_node", wid, current=_domain_of(b))   # spec 051
            repo.close()
        return _JSON({"ok": True})

    @app.post("/api/whynode/remove")
    async def api_whynode_remove(request: Request):
        b = await request.json()
        wid = int(b.get("id") or 0)
        if wid:
            repo = app.state.repo_factory(app.state.config)
            repo.delete_why_node(wid)
            repo.close()
        return _JSON({"ok": True})

    @app.post("/api/article")
    async def api_article(request: Request):
        """知識的輸出（階段 30）：從已冊封理解生成高證實文章。守衛：只採已證實/推論、
        結構化 References、不回灌場。"""
        from ..backends.factory import make_embedder
        from ..output.article import generate_article
        b = await request.json()
        topic = str(b.get("topic") or "").strip()
        cid = int(b.get("conversation_id") or 0)      # spec 043：用某段對話冊封出的理解當骨幹
        length = str(b.get("length") or "medium")
        level = str(b.get("level") or "intermediate")
        repo = app.state.repo_factory(app.state.config)
        try:
            nodes = repo.list_why_nodes("anointed")
            pinned = []
            if cid:
                conv = repo.get_conversation(cid)
                if conv is None:
                    return _JSON({"error": "找不到那段互動（可能已封存）。"})
                ref_ids = {r["id"] for r in repo.conversation_referrers(cid)}
                if not ref_ids:
                    # FR-006：死路變成下一步——不是空白、也不是錯誤碼。
                    return _JSON({"error": "這段互動還沒精選出理解——先精選，再用它生應用。"})
                # ⚠️ 釘住的是**節點物件本身**（同一份 nodes 裡的），不是另外查一份：
                # 另查會拿到不同物件，去重就對不上、同一條被寫進去兩次。
                pinned = [w for w in nodes if getattr(w, "id", None) in ref_ids]
                if not topic:
                    topic = (getattr(conv, "title", "") or "").strip()
        finally:
            repo.close()
        if not topic:
            return _JSON({"error": "請給一個主題"}, status_code=400)
        try:
            emb = getattr(app.state, "embedder_for_test", None) or make_embedder(app.state.config)
            out = generate_article(topic, nodes, _chat_backend(), embedder=emb,
                                   length=length, level=level, pinned=pinned or None)
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("生成文章失敗", extra={"extra": {"reason": str(e)}})
            return _JSON({"error": str(e)}, status_code=502)
        if out.get("empty"):
            return _JSON({"error": "場裡還沒有夠格（已證實／推論）的理解可寫成應用"}, status_code=200)
        out["length"], out["level"] = length, level
        if cid:
            _log.info("從對話生文章", extra={"extra": {"cid": cid, "pinned": len(pinned),
                                                     "field": len(nodes)}})
        return _JSON(out)

    @app.post("/api/article/save")
    async def api_article_save(request: Request):
        """存下生成的文章（輸出物、唯讀存檔）。"""
        b = await request.json()
        if not (b.get("markdown") or "").strip():
            return _JSON({"error": "沒有內容可存"}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        aid = repo.save_article(b.get("topic", ""), b.get("title", ""), b["markdown"],
                                b.get("length", ""), b.get("level", ""), _now_iso(),
                                root_ids=b.get("root_ids") or [],
                                ext_ids=b.get("ext_ids") or [],
                                conversation_id=int(b.get("conversation_id") or 0) or None)
        repo.place_new("article", aid, current=_domain_of(b))   # spec 051
        repo.close()
        return _JSON({"id": aid})

    @app.get("/api/articles")
    async def api_articles():
        repo = app.state.repo_factory(app.state.config)
        arts = repo.list_articles()
        repo.close()
        return _JSON({"articles": arts})

    @app.get("/api/article/{aid}")
    async def api_article_get(aid: int):
        repo = app.state.repo_factory(app.state.config)
        art = repo.get_article(aid)
        repo.close()
        return _JSON(art or {}, status_code=200 if art else 404)

    @app.post("/api/article/{aid}/delete")
    async def api_article_delete(aid: int):
        repo = app.state.repo_factory(app.state.config)
        repo.delete_article(aid)
        repo.close()
        return _JSON({"ok": True})

    @app.get("/api/library")
    async def api_library():
        repo = app.state.repo_factory(app.state.config)
        groups = repo.list_source_groups()
        repo.close()
        return _JSON({"sources": groups})

    @app.get("/api/source")
    async def api_source(u: str = Query(""), raw: str = Query("0")):
        import re as _re

        from ..ingest.chunk import stitch_chunks
        from ..text import lang, s2t
        from ..ingest.media import load_paper_meta, source_pdf_name
        repo = app.state.repo_factory(app.state.config)
        chunks = repo.get_source_chunks(u)
        title = repo.source_title(u)
        meta = repo.source_meta(u)
        repo.close()
        if not chunks:
            return _JSON({"found": False}, status_code=404)
        md = _re.sub(r"<!--kf-page:\d+-->", "", stitch_chunks(chunks))   # 去頁碼標記（顯示/複製乾淨）
        # spec 037：簡→繁只在**顯示路徑**做，絕不回寫（FR-004，原文才是真相）。
        # raw=1＝憲章 VI 的可覆寫出口；非法值一律當 0（契約 C-004）。
        want_raw = raw.strip() == "1"
        s2t_applied = False
        if not want_raw:
            converted = s2t.convert(md)
            # 標題也是使用者在讀的內容（T024 真跑才照出：正文轉了、標題還留著簡體）
            conv_title = s2t.convert(title)
            s2t_applied = converted != md or conv_title != title   # 本非簡體→false，前端據此決定顯不顯示切換
            md, title = converted, conv_title
        mdir = Path(app.state.config.media_dir).resolve()               # 有存原始 PDF→回預覽路徑
        pdf_path = f"/media/{source_pdf_name(u)}" if (mdir / source_pdf_name(u)).exists() else ""
        paper = load_paper_meta(str(mdir), u)                          # 論文 metadata（Abstract/作者/日期）
        return _JSON({"found": True, "url": u, "title": title, "markdown": md,
                      "original_url": u if u.startswith("http") else "", "pdf_path": pdf_path,
                      "paper": paper, "note": meta["note"], "ingested_at": meta["ingested_at"],
                      "s2t_applied": s2t_applied,
                      "is_english": lang.is_english(md)})

    @app.post("/api/source/meta")
    async def api_source_meta(request: Request):
        b = await request.json()
        u = (b.get("u") or "").strip()
        if u:
            repo = app.state.repo_factory(app.state.config)
            repo.set_source_meta(u, b.get("note", ""), b.get("ingested_at", ""))
            repo.close()
        return _JSON({"ok": True})

    @app.get("/api/source/translate")
    async def api_source_translate(u: str = Query("")):
        """英→繁一鍵全文翻譯（spec 038）。SSE，協定沿用 /chat/stream 的 type-in-data。

        並行 8 路（實測 11.1 分 → 1.8 分）；單塊失敗或保護片段不完整 → 該塊退回原文。
        **不寫回儲存層**——譯文是衍生物，原文才是真相。
        """
        import re as _re

        from ..ingest.chunk import stitch_chunks
        from ..text import lang, translate as _tr

        def _join(parts, seps) -> str:
            """照 split_units 給的原分隔接回（不再比對接縫）。"""
            parts = list(parts)
            out = parts[0] if parts else ""
            for piece, sep in zip(parts[1:], seps):
                out += sep + piece
            return out

        def gen():
            repo = app.state.repo_factory(app.state.config)
            try:
                chunks = [_re.sub(r"<!--kf-page:\d+-->", "", c) for c in repo.get_source_chunks(u)]
                # spec 039 FR-005：順手清掉久未使用的譯文。翻譯是低頻動作，掃一次的成本可忽略，
                # 所以**不引入排程器**（YAGNI）；譯文能重生，清錯的代價只是下次要重翻一次。
                purged = repo.purge_stale_translations(_days_ago_iso(_TRANSLATION_TTL_DAYS))
                if purged:
                    _log.info("清掉久未使用的譯文", extra={"extra": {"count": purged}})
                if not chunks:
                    yield _sse({"type": "error", "message": "找不到這份來源。"})
                    return
                src = stitch_chunks(chunks)
                if not lang.is_english(src):
                    yield _sse({"type": "error", "message": "這份來源不是英文，不需要翻譯。"})
                    return
                # ⚠️ 不重用檢索用的塊——那是為 embedding 切的，會從單字中間切開
                # （實測 124 個接縫有 55 個是），"Conditioned Generat"＋"ion" 各自翻譯
                # 會變成「條件式 Generat」＋「離子」。先拼回全文，再切成合法的翻譯單位。
                pieces, seps = _tr.split_units(src)
                # ⚠️ 查快取必須排在**建後端之前**——後端不可用時，已快取的來源仍要看得到譯文。
                # 這是程式碼順序本身就是規格的一處，有測試釘住
                # （test_web_translate.py::test_cache_hit_does_not_need_the_backend）。
                keys = [_tr.content_key(p) for p in pieces]
                hits = repo.get_translation_units(keys, _now_iso())
            finally:
                repo.close()
            todo = [i for i, k in enumerate(keys) if k not in hits]
            _log.info("譯文快取", extra={"extra": {"url": u, "hit": len(pieces) - len(todo),
                                                  "miss": len(todo)}})
            if not todo:
                # 全命中：**不送 stage**（前端進度條靠 stage 驅動，送了會閃一下再瞬間結束）
                yield _sse({"type": "done", "total": len(pieces), "failed": 0,
                            "markdown": _join((hits[k] for k in keys), seps)})
                return
            from ..backends.factory import make_translate_backend
            backend = (getattr(app.state, "translate_backend_for_test", None)
                       or make_translate_backend(app.state.config))
            # 串流邏輯在 text/translate.py（那裡測得到時機）；這裡只負責包成 SSE。
            # 只翻沒命中的單位——進度回報的分母因此是**真正還要做的工作量**，不是總單位數。
            for kind, payload in _tr.translate_stream([pieces[i] for i in todo], backend):
                if kind == "stage":
                    yield _sse({"type": "stage", **payload})
                else:
                    out, oks = payload["chunks"], payload.get("ok") or []
                    merged = [hits.get(k, "") for k in keys]
                    save = []
                    for n, i in enumerate(todo):
                        merged[i] = out[n] if n < len(out) else pieces[i]
                        # FR-006：⚠️ **只存翻成功的單位**。失敗的永遠不進庫 ⇒ 下次一定重試，
                        # 那次失敗不會被固定下來——而成功的那些不必陪葬。
                        if n < len(oks) and oks[n]:
                            save.append((keys[i], merged[i]))
                    if save:
                        _r = app.state.repo_factory(app.state.config)
                        try:
                            _r.save_translation_units(save, _now_iso())
                        finally:
                            _r.close()
                    yield _sse({"type": "done", "total": payload["total"],
                                "failed": payload["failed"], "markdown": _join(merged, seps)})

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/api/source/distill")
    async def api_source_distill(request: Request):
        from ..ingest.activate import distill_source
        b = await request.json()
        url = (b.get("u") or "").strip()
        if not url:
            return _JSON({"ok": False, "err": "無來源"}, status_code=400)
        try:
            repo = app.state.repo_factory(app.state.config)
            try:
                cand = distill_source(repo, _extractor(), url, _now_iso())
            finally:
                repo.close()
        except SourceUnavailable as e:
            return _JSON({"ok": False, "err": str(e)}, status_code=502)
        if cand is None:
            return _JSON({"ok": False, "err": "這份來源沒有足夠內容可整理出理解"})
        return _JSON({"ok": True})

    @app.post("/api/library/reclassify")
    async def api_library_reclassify(request: Request):
        b = await request.json()
        url = (b.get("url") or "").strip()
        if url:
            repo = app.state.repo_factory(app.state.config)
            repo.set_source_class_by_url(url, b.get("source_class", "ordinary"))
            repo.close()
        return _JSON({"ok": True})

    @app.post("/api/library/remove")
    async def api_library_remove(request: Request):
        b = await request.json()
        url = (b.get("url") or "").strip()
        if url:
            repo = app.state.repo_factory(app.state.config)
            repo.delete_source(url)
            repo.close()
        return _JSON({"ok": True})

    def _ingest_result(kind, domain_id=None, **kw):
        try:
            res = _content_ingest(kind, **kw)
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("收進失敗", extra={"extra": {"reason": str(e)}})
            return _JSON({"status": "error", "err": str(e)}, status_code=502)
        # spec 051：收進來的來源生在你站的地方（來源沒有出處，所以純粹用當前領域）
        if res.status == "ingested" and getattr(res, "url", ""):
            repo = app.state.repo_factory(app.state.config)
            try:
                repo.place_new("source", res.url, current=domain_id)
            finally:
                repo.close()
        return _JSON({"status": res.status, "count": getattr(res, "count", 0),
                      "title": getattr(res, "title", "")})

    @app.post("/api/ingest/paste")
    async def api_ingest_paste(request: Request):
        b = await request.json()
        text, html = (b.get("text") or ""), (b.get("html") or "")
        if not text.strip() and not html.strip():
            return _JSON({"status": "empty", "count": 0})
        at = (b.get("ingested_at") or "").strip() or _now_iso()[:10]
        return _ingest_result("text", domain_id=_domain_of(b), text=text, title=b.get("title", ""), html=html,
                              clean=bool(b.get("clean")), source_url=b.get("source_url", ""),
                              note=b.get("note", ""), ingested_at=at)

    @app.post("/api/ingest/url")
    async def api_ingest_url(request: Request):
        b = await request.json()
        url = (b.get("url") or "").strip()
        if not url:
            return _JSON({"status": "empty", "count": 0})
        at = (b.get("ingested_at") or "").strip() or _now_iso()[:10]
        return _ingest_result("url", domain_id=_domain_of(b), url=url, title=b.get("title", ""),
                              note=b.get("note", ""), ingested_at=at)

    @app.post("/api/ingest/youtube")
    async def api_ingest_youtube(request: Request):
        b = await request.json()
        url = (b.get("url") or "").strip()
        if not url:
            return _JSON({"status": "empty", "count": 0})
        return _ingest_result("youtube", domain_id=_domain_of(b), url=url, title=b.get("title", ""))

    @app.post("/api/ingest/pdf")
    async def api_ingest_pdf(url: str = Form(""), title: str = Form(""),
                             file: UploadFile = File(None), note: str = Form(""),
                             ingested_at: str = Form("")):
        pdf_bytes = await file.read() if file is not None else None
        pdf_url = (url or "").strip()
        if not pdf_bytes and not pdf_url:
            return _JSON({"status": "empty", "count": 0})
        at = (ingested_at or "").strip() or _now_iso()[:10]
        return _ingest_result("pdf", domain_id=_domain_of(b), pdf_bytes=pdf_bytes, pdf_url=pdf_url, title=title,
                              note=note, ingested_at=at)

    @app.post("/api/ingest/share")
    async def api_ingest_share(request: Request):
        """PWA Web Share Target（里程碑四）：手機分享網址/文字進來→收進。"""
        ct = request.headers.get("content-type", "")
        b = (await request.json() if ct.startswith("application/json")
             else dict(await request.form()))
        url = str(b.get("url") or b.get("link") or "").strip()
        text = str(b.get("text") or "").strip()
        title = str(b.get("title") or "").strip()
        at = _now_iso()[:10]
        if url.startswith("http"):
            return _ingest_result("url", domain_id=_domain_of(b), url=url, title=title, note="手機分享", ingested_at=at)
        if text:
            return _ingest_result("text", domain_id=_domain_of(b), text=text, title=title, note="手機分享", ingested_at=at)
        return _JSON({"status": "empty", "count": 0})

    # ══ 領域樹（spec 048，階段 43）══
    # 領域＝節點、**主題 Topic ＝從根到節點的路徑**。⚠️ 路徑由 parent_id 導出、不另存字串。
    # ⚠️ 這一刀**完全不碰 grounding**：撒網仍看全場。樹是**導航**，不是檢索權重
    #（原則 5：權重由人冊封，不由位置給）。有測試釘住脈絡逐字不變。
    @app.middleware("http")
    async def _persona_ctx(request: Request, call_next):
        """spec 067：把 cookie 裡的身分放進 contextvar，供 `repo_factory` 取用。

        ⚠️ **不驗證那個 id 屬不屬於你**——不需要：`_own()` 是
        `owner=你 AND (persona IS NULL OR persona=那個)`，別人的 persona id
        在你的 owner 底下一列都對不上 ⇒ 最壞情況是**只看到共用層**，不是看到別人的東西。
        """
        raw = request.cookies.get("kf_persona") or ""
        _CURRENT_PERSONA.set(int(raw) if raw.isdigit() else None)
        return await call_next(request)

    @app.get("/api/personas")
    async def api_personas():
        repo = app.state.repo_factory(app.state.config)
        try:
            out = repo.list_personas()
        finally:
            repo.close()
        return _JSON({"personas": out, "current": _CURRENT_PERSONA.get()})

    @app.post("/api/personas")
    async def api_personas_create(request: Request):
        b = await request.json()
        name = str(b.get("name") or "").strip()
        if not name:
            return _JSON({"error": "身分要有名字。"}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            pid = repo.create_persona(name, str(b.get("color") or "")[:16])
        finally:
            repo.close()
        return _JSON({"id": pid, "name": name})

    @app.post("/api/personas/switch")
    async def api_personas_switch(request: Request):
        """切換身分。⚠️ 只寫 cookie——切換本身不動任何資料。"""
        b = await request.json()
        pid = b.get("id")
        r = _JSON({"current": int(pid) if pid else None})
        if pid:
            r.set_cookie("kf_persona", str(int(pid)), httponly=False, samesite="lax", path="/")
        else:
            r.delete_cookie("kf_persona", path="/")
        return r

    @app.get("/api/domains/{did}/context")
    async def api_domain_context(did: str):
        """spec 070：搜尋給不了的那三塊——⛓ 通往哪裡 · 🪂 快掉出去的 · 🧭 相鄰的區。

        ⚠️ 只用**已落庫**的向量，不呼叫 API：逛一頁不該花錢，也不該等。
        """
        from ..organize.neighbours import domain_context
        d = None if did in ("0", "root", "null") else int(did)
        repo = app.state.repo_factory(app.state.config)
        try:
            out = domain_context(repo, d, app.state.district_embedder_factory())
        finally:
            repo.close()
        return _JSON(out)

    @app.get("/api/rehearse")
    async def api_rehearse():
        """spec 068：一天三條複習。⚠️ 排序**只有時間**——熱門度是馬太陷阱。"""
        repo = app.state.repo_factory(app.state.config)
        try:
            out = repo.rehearse(3)
        finally:
            repo.close()
        return _JSON({"items": out})

    @app.get("/api/search")
    async def api_search(request: Request):
        """spec 066：全域搜尋。⚠️ 結果**不摻**「你可能也想看」——那是逛的工作（階段 64）。"""
        q = str(request.query_params.get("q") or "")
        repo = app.state.repo_factory(app.state.config)
        try:
            hits = repo.search(q)
        finally:
            repo.close()
        order = {"why_node": 0, "conversation": 1, "source": 2, "article": 3}
        groups: dict[str, list] = {}
        for h in hits:
            groups.setdefault(h["kind"], []).append(h)
        out = [{"kind": k, "count": len(v), "items": v}
               for k, v in sorted(groups.items(), key=lambda kv: order.get(kv[0], 9))]
        return _JSON({"q": q.strip(), "groups": out})

    @app.get("/api/domains/suggest")
    async def api_domains_suggest():
        """spec 065：建議怎麼整理。

        ⚠️ **只回建議，不動任何東西**——套用是逐夾、另一個端點。
        原則 5：提議是 AI 的事，冊封／歸位是人的事。
        """
        from ..organize.district import districts
        repo = app.state.repo_factory(app.state.config)
        try:
            chat = app.state.suggest_backend_factory()
            # spec 069：⚠️ 只劃**還沒有地址**的東西——沒有全量重劃那條路。
            folders = districts(repo, app.state.district_embedder_factory(), chat=chat)
        finally:
            repo.close()
        return _JSON({"folders": folders})

    @app.post("/api/domains/suggest/apply")
    async def api_domains_suggest_apply(request: Request):
        """套用**一個**建議夾：建領域 ＋ 把成員搬進去。

        ⚠️ 一次一夾，**沒有一次套用多夾的路徑**（FR-004）——
        「提議 ＋ 一個全部套用的按鈕」＝ 自動分類多按一下。
        """
        b = await request.json()
        name = str(b.get("name") or "").strip()
        if not name:
            return _JSON({"error": "資料夾要有名字。"}, status_code=400)
        items = _parse_items(b.get("items"))
        if not items:
            return _JSON({"error": "這一夾是空的，沒有東西可以搬。"}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            parent = b.get("parent_id")
            did = repo.create_domain(name, int(parent) if parent else None)
            # spec 049：搬動會拆散糾纏——**報出來**，但不自動連帶搬
            # spec 069：劃界接受的是**機器算的**地址 ⇒ 記下來，人的 override 才分得出
            tangles = repo.batch_move(items, did, bring_along=False, by="machine")
        finally:
            repo.close()
        return _JSON({"domain_id": did, "moved": len(items), "tangles": tangles})

    @app.get("/api/domains")
    async def api_domains():
        repo = app.state.repo_factory(app.state.config)
        try:
            ds = repo.list_domains()
            out = [{**d, "path": repo.domain_path(d["id"])} for d in ds]
        finally:
            repo.close()
        return _JSON({"domains": out})

    @app.post("/api/domains")
    async def api_domain_create(request: Request):
        b = await request.json()
        name = str(b.get("name") or "").strip()
        if not name:
            return _JSON({"ok": False, "err": "領域要有名字"}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            did = repo.create_domain(name, b.get("parent_id"))
        finally:
            repo.close()
        return _JSON({"ok": True, "id": did})

    @app.post("/api/domains/{did}/rename")
    async def api_domain_rename(did: int, request: Request):
        b = await request.json()
        name = str(b.get("name") or "").strip()
        if not name:
            return _JSON({"ok": False, "err": "領域要有名字"}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            repo.rename_domain(did, name)
        finally:
            repo.close()
        return _JSON({"ok": True})

    @app.get("/api/domains/{did}/archive-preview")
    async def api_domain_archive_preview(did: int):
        """封存這個領域會動到什麼。**不改任何東西。**"""
        repo = app.state.repo_factory(app.state.config)
        try:
            return _JSON({"ok": True, **repo.archive_domain_preview(did)})
        finally:
            repo.close()

    @app.post("/api/domains/{did}/archive")
    async def api_domain_archive(did: int):
        """**封存**一個領域：容器結束，內容回到場裡，而且留下遺骸（spec 055）。"""
        repo = app.state.repo_factory(app.state.config)
        try:
            moved = repo.archive_domain(did, _now_iso())
        finally:
            repo.close()
        _log.info("封存領域", extra={"extra": {"did": did, **moved}})
        return _JSON({"ok": True, **moved})

    @app.get("/api/domains/archived")
    async def api_domains_archived():
        """遺骸：封存過的領域（答得出「這裡本來叫什麼、什麼時候封的」）。"""
        repo = app.state.repo_factory(app.state.config)
        try:
            return _JSON({"ok": True, "domains": repo.archived_domains()})
        finally:
            repo.close()

    @app.post("/api/domains/{did}/restore")
    async def api_domain_restore(did: int):
        """復原。⚠️ **不把知識搬回來**——它們在新位置活過了（FR-006）。"""
        repo = app.state.repo_factory(app.state.config)
        try:
            repo.restore_domain(did)
        finally:
            repo.close()
        _log.info("復原領域", extra={"extra": {"did": did}})
        return _JSON({"ok": True})

    @app.post("/api/knowledge/archive")
    async def api_archive_knowledge(request: Request):
        """**封存**一批知識（spec 055）：離開活的場，留下遺骸。"""
        b = await request.json()
        try:
            items = _parse_items(b.get("items"))
        except (ValueError, TypeError) as e:
            return _JSON({"ok": False, "err": str(e)}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            now = _now_iso()
            for kind, ref in items:
                repo.archive_knowledge(kind, ref, now)
        finally:
            repo.close()
        _log.info("封存知識", extra={"extra": {"n": len(items)}})
        return _JSON({"ok": True, "archived": len(items)})

    @app.post("/api/knowledge/restore")
    async def api_restore_knowledge(request: Request):
        b = await request.json()
        try:
            items = _parse_items(b.get("items"))
        except (ValueError, TypeError) as e:
            return _JSON({"ok": False, "err": str(e)}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            for kind, ref in items:
                repo.restore_knowledge(kind, ref)
        except ValueError as e:
            # ⚠️ 抹除過的復原不了，那是**正確的拒絕**——不接住的話會變成 500，
            # 而 500 在使用者眼裡是「壞掉了」，不是「這件事不能做」。
            return _JSON({"ok": False, "err": str(e)}, status_code=400)
        finally:
            repo.close()
        return _JSON({"ok": True, "restored": len(items)})

    @app.post("/api/knowledge/erase")
    async def api_erase_knowledge(request: Request):
        """**第二次的死**（spec 056）：抹除，只留一塊疤。⚠️ 只接受已封存的。"""
        b = await request.json()
        try:
            items = _parse_items(b.get("items"))
        except (ValueError, TypeError) as e:
            return _JSON({"ok": False, "err": str(e)}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            now = _now_iso()
            for kind, ref in items:
                repo.erase_knowledge(kind, ref, now)
        except ValueError as e:
            return _JSON({"ok": False, "err": str(e)}, status_code=400)
        finally:
            repo.close()
        _log.info("抹除知識", extra={"extra": {"n": len(items)}})
        return _JSON({"ok": True, "erased": len(items)})

    @app.post("/api/knowledge/pointers")
    async def api_pointers(request: Request):
        """誰指著這些東西——抹除前要說出來（FR-004）。**不改任何東西。**"""
        b = await request.json()
        try:
            items = _parse_items(b.get("items"))
        except (ValueError, TypeError) as e:
            return _JSON({"ok": False, "err": str(e)}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            out, seen = [], set()
            moving = {(k, str(r)) for k, r in items}
            for kind, ref in items:
                for p in repo.pointers_to(kind, ref):
                    key = (p["kind"], str(p["ref"]))
                    if key in moving or key in seen:
                        continue
                    seen.add(key)
                    out.append({**p, "label": _knowledge_label(repo, p["kind"], p["ref"])})
        finally:
            repo.close()
        return _JSON({"ok": True, "pointers": out})

    @app.post("/api/domains/{did}/erase")
    async def api_domain_erase(did: int):
        """抹除一個領域遺骸。⚠️ **不連帶抹除**它底下的遺骸內容。"""
        repo = app.state.repo_factory(app.state.config)
        try:
            repo.erase_domain(did, _now_iso())
        except ValueError as e:
            return _JSON({"ok": False, "err": str(e)}, status_code=400)
        finally:
            repo.close()
        _log.info("抹除領域", extra={"extra": {"did": did}})
        return _JSON({"ok": True})

    @app.get("/api/archived")
    async def api_archived():
        """遺骸清單：封存過的知識與領域（「刪除又要不能不見」的那個『見』）。"""
        repo = app.state.repo_factory(app.state.config)
        try:
            return _JSON({"ok": True, "items": repo.archived_items(),
                          "domains": repo.archived_domains()})
        finally:
            repo.close()

    @app.post("/api/domains/{did}/move")
    async def api_domain_move(did: int, request: Request):
        b = await request.json()
        repo = app.state.repo_factory(app.state.config)
        try:
            repo.move_domain(did, b.get("parent_id"))
        except ValueError as e:      # 成環 → 明講，不靜默照做（FR-004）
            return _JSON({"ok": False, "err": str(e)})
        finally:
            repo.close()
        return _JSON({"ok": True})

    @app.post("/api/conversations/{cid}/domain")
    async def api_conversation_domain(cid: int, request: Request):
        b = await request.json()
        repo = app.state.repo_factory(app.state.config)
        try:
            repo.set_conversation_domain(cid, b.get("domain_id"))
        finally:
            repo.close()
        return _JSON({"ok": True})

    # ══ 整理與糾纏（spec 049，階段 44）══
    # ⚠️ 糾纏在整理之前就存在，這裡只是**讓它現形**。兩條界線在 repository 那層釘死：
    # 只算直接連結、連帶只走一層。
    # ══ 整理台（spec 050）══
    # ⚠️ 批次端點**取代**單件端點：單件操作＝送一個元素的清單。
    # 留兩套就是第三次「同一件事兩套介面」（spec 045／047 都是拿掉那個）。

    @app.get("/api/knowledge/inventory")
    async def api_inventory():
        """整理台的清冊：四種知識的 kind / ref / label / domain_id，扁平一份。

        ⚠️ 刻意**不**去擴 `/api/roots`、`/api/articles`、`/api/library`
        ——那三支各有自己的消費者，為整理台加欄會把它們綁在一起。
        ⓘ spec 052 起改用 `repo._inventory_rows()`，與領域視野**共用一份定義**
        （兩份定義會慢慢漂開，而漂開不會報錯）。
        """
        repo = app.state.repo_factory(app.state.config)
        try:
            out = repo._inventory_rows()
        finally:
            repo.close()
        return _JSON({"ok": True, "items": out})

    @app.get("/api/domains/{did}/view")
    async def api_domain_view(did: str):
        """站在一個領域看到的東西（spec 052）。`did='0'` ＝ 根領域＝整個知識庫。"""
        try:
            d = int(did) or None
        except (TypeError, ValueError):
            return _JSON({"ok": False, "err": "領域要是數字"}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            v = repo.domain_view(d)
            for o in v["outward"]:
                o["label"] = _knowledge_label(repo, o["kind"], o["ref"])
        finally:
            repo.close()
        return _JSON({"ok": True, **v})

    @app.post("/api/knowledge/tangles")
    async def api_batch_tangles(request: Request):
        """預覽：整批搬到某領域會拆散哪些直接鄰居。**不改任何東西。**"""
        b = await request.json()
        try:
            items = _parse_items(b.get("items"))
        except (ValueError, TypeError) as e:
            return _JSON({"ok": False, "err": str(e)}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            ts = repo.batch_tangles(items, b.get("domain_id"))
            for t in ts:
                t["label"] = _knowledge_label(repo, t["kind"], t["ref"])
        finally:
            repo.close()
        return _JSON({"ok": True, "tangles": ts})

    @app.post("/api/knowledge/move")
    async def api_batch_move(request: Request):
        b = await request.json()
        try:
            items = _parse_items(b.get("items"))
        except (ValueError, TypeError) as e:
            return _JSON({"ok": False, "err": str(e)}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        try:
            left = repo.batch_move(items, b.get("domain_id"), bool(b.get("bring_along")))
        finally:
            repo.close()
        _log.info("批次搬動", extra={"extra": {"n": len(items), "tangles": len(left),
                                             "bring_along": bool(b.get("bring_along"))}})
        return _JSON({"ok": True, "moved": len(items), "tangles": len(left)})

    @app.get("/api/conversations")
    async def api_conversations():
        repo = app.state.repo_factory(app.state.config)
        # spec 040：不再分暫存/永久，也不再依時間清理——移除的是機制，不是資料。
        convs = repo.list_conversations()
        # spec 045：「這段聊出了東西」要讀**事實來源**（why_nodes.conversation_id）。
        # ⚠️ 一次 GROUP BY，不是逐筆——清單是 N 筆。
        yields = repo.conversation_yield_counts()
        repo.close()

        def _cv(c):
            # why_node_id 照舊回傳（不破壞相容），但前端不再拿它判斷徽章：
            # 那欄只在 save_conversation 那條路才被填，冊封走 promote_conversation
            # 只更新 why_nodes 側 ⇒ 讀它會漏掉 2/3（正式庫實測 12 → 4）。
            return {"id": c.id, "title": c.title, "created_at": c.created_at,
                    "why_node_id": c.why_node_id, "count": len(c.messages),
                    "yield_count": yields.get(c.id, 0),
                    "domain_id": c.domain_id}
        return _JSON({"conversations": [_cv(c) for c in convs]})

    @app.get("/api/conversations/{cid}")
    async def api_conversation(cid: int, resume: int = Query(0)):
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        # referrers＝以此對話為由來的理解主張（給前端：編輯/重生時擋、護溯源）
        rows = repo.conversation_referrers(cid) if conv is not None else []
        refs = [r["claim"] for r in rows]
        # spec 046：讓對話頁標得出**哪幾則已冊封**。回**範圍**不回布林陣列——
        # ⚠️ 訊息數會變（接著聊），陣列會過期而錯位；範圍讓前端當下算。
        # 沒有範圍的舊冊封（正式庫 34/75）回 0/0，前端只在對話層級呈現，不猜是哪幾則。
        anointed = [{"id": r["id"], "claim": r["claim"],
                     "from": r["src_from"], "to": r["src_to"]} for r in rows]
        repo.close()
        if conv is None:
            return _JSON({"found": False}, status_code=404)
        return _JSON({"found": True, "id": conv.id, "title": conv.title,
                      "messages": conv.messages, "referrers": refs,
                      "anointed": anointed})

    @app.post("/api/conversations/{cid}/rename")
    async def api_conversation_rename(cid: int, request: Request):
        b = await request.json()
        repo = app.state.repo_factory(app.state.config)
        repo.rename_conversation(cid, b.get("title") or "")
        repo.close()
        return _JSON({"ok": True})

    @app.post("/api/conversations/{cid}/delete")
    async def api_conversation_delete(cid: int):
        """刪對話——但**被理解引用（由來）的刪不掉**（護溯源，原則 3）：回 blocked_by＝那些理解主張，
        使用者要先刪掉它們才能刪這段對話。"""
        repo = app.state.repo_factory(app.state.config)
        refs = repo.conversation_referrers(cid)
        if refs:
            repo.close()
            return _JSON({"deleted": False, "blocked_by": [r["claim"] for r in refs]})
        ok = repo.delete_conversation(cid)
        repo.close()
        return _JSON({"deleted": ok, "blocked_by": []})

    @app.post("/api/conversations/{cid}/retitle")
    async def api_conversation_retitle(cid: int):
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        title = conv.title if conv else ""
        if conv is not None:
            try:
                t = (app.state.title_factory(conv.messages) or "").strip()
            except Exception as e:  # noqa: BLE001
                _log.error("重生標題失敗", extra={"extra": {"reason": str(e)}})
                t = ""
            if t:
                repo.rename_conversation(cid, t)
                title = t
        repo.close()
        return _JSON({"ok": True, "title": title})

    @app.get("/api/conversations/{cid}/segment")
    async def api_conversation_segment(cid: int, refresh: int = Query(0)):
        """整理成章節（階段29：**持久化**避免每次重切）。切過→直接讀；refresh=1 或訊息長出→重切。
        失敗→整段一章、不崩。"""
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        if conv is None:
            repo.close()
            return _JSON({"found": False}, status_code=404)
        # 已切過且未過時（涵蓋到最後一則）→ 直接讀
        covered = conv.chapters and max((c.get("end", 0) for c in conv.chapters), default=0) >= len(conv.messages)
        if conv.chapters and covered and not refresh:
            repo.close()
            return _JSON({"found": True, "chapters": conv.chapters})
        try:
            raw = app.state.segment_factory(conv.messages)
        except Exception as e:  # noqa: BLE001
            _log.error("章節切分失敗", extra={"extra": {"reason": str(e)}})
            raw = [{"title": "全部", "start": 1, "end": len(conv.messages)}]
        chapters = [{"title": ch.get("title", ""), "start": ch.get("start", 0), "end": ch.get("end", 0)}
                    for ch in raw]
        repo.set_conversation_chapters(cid, chapters)
        repo.close()
        return _JSON({"found": True, "chapters": chapters})

    @app.get("/api/conversations-dedupe/preview")
    async def api_dedupe_preview():
        repo = app.state.repo_factory(app.state.config)
        plan = repo.dedupe_plan()
        repo.close()
        return _JSON({"n_groups": plan.n_groups, "n_extra": plan.n_extra, "n_roots": plan.n_roots})

    @app.post("/api/conversations-dedupe/apply")
    async def api_dedupe_apply():
        repo = app.state.repo_factory(app.state.config)
        summary = repo.apply_dedupe()
        repo.close()
        return _JSON({"ok": True, "removed": summary["removed"], "repointed": summary["repointed"]})

    # ══ 服務 React SPA（掛根 /；retire 完成、舊 Jinja 已退役，根路徑空出來給門面）══
    _DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if _DIST.is_dir():
        from starlette.exceptions import HTTPException as _StarletteHTTPExc
        from fastapi.staticfiles import StaticFiles

        @app.post("/share-target")
        async def app_share_target(request: Request):
            """PWA Web Share Target（里程碑四）：手機分享網址/文字進來→收進→導回知識庫。"""
            form = await request.form()
            url = str(form.get("url") or form.get("link") or "").strip()
            text = str(form.get("text") or "").strip()
            title = str(form.get("title") or "").strip()
            at = _now_iso()[:10]
            try:
                if url.startswith("http"):
                    _content_ingest("url", url=url, title=title, note="手機分享", ingested_at=at)
                elif text:
                    _content_ingest("text", text=text, title=title, note="手機分享", ingested_at=at)
            except (SourceUnavailable, OpenAIError) as e:  # best-effort（教訓 3）
                _log.error("手機分享收進失敗", extra={"extra": {"reason": str(e)}})
            return RedirectResponse("/sources", status_code=303)

        class _SpaStatic(StaticFiles):
            """服務 dist 靜態檔（含 manifest/sw/icon）；client 路由（非檔案）fallback 回 index.html。"""
            async def get_response(self, path, scope):
                try:
                    return await super().get_response(path, scope)
                except _StarletteHTTPExc as e:
                    if e.status_code == 404:
                        return await super().get_response("index.html", scope)
                    raise

        # mount 移到 create_app 最尾（所有 /api 與匯出路由都註冊完），否則掛在 / 會把它們吃掉。


    # --- 匯出給 NotebookLM（spec 024）：純唯讀、只把沉澱物匯出，不注入回場（原則 6）---
    def _export_conversation(title: str, messages: list, as_: str) -> str:
        from ..export.notebooklm import (
            conversation_evidence_urls,
            conversation_to_markdown,
        )
        if as_ == "urls":
            return "\n".join(conversation_evidence_urls(messages))
        return conversation_to_markdown(title, messages)


    @app.get("/conversations/{cid}/export")
    async def conversation_export(cid: int, as_: str = Query("md", alias="as"),
                                  from_: int = Query(0, alias="from"),
                                  to: int = Query(0)):
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        repo.close()
        if conv is None:
            return PlainTextResponse("找不到這段互動。", status_code=404)
        msgs = conv.messages
        if from_ and to:                     # 章節切片（spec 027 US3）：只匯出該章範圍
            msgs = msgs[max(0, from_ - 1):to]
        return PlainTextResponse(_export_conversation(conv.title, msgs, as_))


    @app.get("/roots/{wid}/export")
    async def root_export(wid: int, as_: str = Query("md", alias="as")):
        from ..export.notebooklm import dedup_urls, why_node_to_markdown
        repo = app.state.repo_factory(app.state.config)
        node = next((w for w in repo.list_why_nodes() if w.id == wid), None)
        repo.close()
        if node is None:
            return PlainTextResponse("找不到這條根因。", status_code=404)
        if as_ == "urls":
            return PlainTextResponse("\n".join(dedup_urls(node.evidence_urls)))
        return PlainTextResponse(
            why_node_to_markdown(node.claim, node.ladder, node.evidence_urls))

    # 收進圖片在地化：serve 下載的圖（放 SPA catch-all 之前；check_dir=False→目錄還沒建也不炸）
    from fastapi.staticfiles import StaticFiles as _StaticFiles
    app.mount("/media", _StaticFiles(directory=str(Path(app.state.config.media_dir).resolve()),
                                     check_dir=False), name="media")

    # 單人 Google 登入門鎖（spec 035）：只在設了 allowlist＋憑證時啟用；沒設＝全開（既有測試零回歸）。
    # 須在 SPA catch-all 之前註冊 /auth 路由，否則被 "/" mount 遮蔽。
    from .auth import setup_auth
    setup_auth(app)

    # SPA 掛在 / 當 catch-all（放最後，讓上面所有實體路由先比對）：非檔案→fallback index.html
    if _DIST.is_dir():
        app.mount("/", _SpaStatic(directory=str(_DIST), html=True), name="spa")

    return app


app = create_app()
