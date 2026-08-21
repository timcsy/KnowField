"""FastAPI web app。唯一 import 框架之處；核心全複用、零改動。

頁面（產品轉向後，新聞分診子系統已退役，見 knowledge/history/068）：
/（導向 /chat）、/chat*、/roots、/conversations*、/ingest、/library、/ask。
後端失敗經例外處理器攔成友善繁中頁（FR-009、experience 教訓 3）。
可覆寫點（app.state）供測試注入：repo_factory、chat_factory、rag_answer_factory 等。
"""

from __future__ import annotations

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


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _default_repo_factory(config: Config) -> Repository:
    from ..cli.fetchers import DEFAULT_SOURCES
    repo = Repository(config.database_url or None)   # spec 034：PG DSN（env）
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
        """根因萃取後端（spec 032 整理成核心理解，復用階段 10）；可注入離線 stub（教訓 1）。"""
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
        # bare＝這輪屏蔽知識庫：不查核心理解、不撒網、不查收藏
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
            roots = repo.list_why_nodes("anointed")   # 傳既有核心理解→標「已收過」（去重）
        finally:
            repo.close()
        return FieldChat(_chat_backend()).distill(history, roots)
    app.state.distill_factory = _default_distill

    def _default_title(messages):
        from ..chat.field_chat import FieldChat
        return FieldChat(_chat_backend()).title(messages)
    app.state.title_factory = _default_title

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


    def _stream_gen(hist, message, bare, article_id=0):
        """SSE 生成器：/chat/stream 與 /api/chat/stream 共用（協定：stage/token/done/error）。
        bare＝這輪暫時屏蔽知識庫：不注入核心理解、不撒網、不查收藏。
        article_id＝使用者**明確**帶進來的一篇生成文章（spec 041），0＝沒帶。"""
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
                yield _sse({"type": "error", "message": "找不到那篇文章（可能已刪除）。"})
                return
            _article = {"id": _a.get("id", article_id),
                        "title": _a.get("title") or "",
                        "markdown": _a.get("markdown") or ""}
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
            yield _sse({"type": "stage", "text": "回答中…"})
            full, truncated = yield from _pump(
                fc.reply_stream(hist, message, roots, sources, bare=bare, article=_article,
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
                   src_from=0, src_to=0):
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
            wid = repo.add_why_node(claim, urls, [], False, 0, _now_iso(), ladder=steps, kind=kind,
                                    src_from=src_from, src_to=src_to)
            repo.anoint_why_node(wid)
            status = "created"
            msg = f"已存進你的知識庫：「{claim[:40]}」（可到『核心理解』頁檢視或刪除）"
        if save_convo == "1":                   # 連同這段對話存成由來（既有或新建都連）
            messages = _parse_history(history)
            if messages:
                tid = _temp_id(temp_id)
                if tid:                         # 有暫存→升永久同一筆＋連根因（spec 028，不新增）
                    repo.promote_conversation(tid, _convo_title(messages), wid)
                else:
                    repo.save_conversation(_convo_title(messages), messages, wid)
                if status == "created":
                    msg += "，並存下這段對話當它的由來"
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
                        int(body.get("article_id") or 0)),
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
            int(body.get("src_from") or 0), int(body.get("src_to") or 0))
        return _JSON({"status": status, "claim": claim, "msg": msg})

    @app.post("/api/chat/autosave")
    async def api_chat_autosave(request: Request):
        body = await request.json()
        title = None
        try:
            repo = app.state.repo_factory(app.state.config)
            tid = repo.autosave_temporary(_temp_id(str(body.get("temp_id") or "")) or None,
                                          body.get("history") or [], _now_iso())
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
            return _JSON({"saved": False, "msg": "這段對話還是空的，沒有東西可存。"})
        repo = app.state.repo_factory(app.state.config)
        tid = _temp_id(str(b.get("temp_id") or ""))
        if tid:                         # 有暫存→升永久同一筆＋生落點標題（不新增）
            repo.promote_conversation(tid, _convo_title(messages))
        else:
            repo.save_conversation(_convo_title(messages), messages, None)
        repo.close()
        return _JSON({"saved": True, "msg": "已存下這段對話（可到『對話存檔』檢視）"})

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
                    "source_quote": getattr(w, "source_quote", ""),
                    "source_page": getattr(w, "source_page", 0)}
        return _JSON({"anointed": [_wn(w) for w in anointed],
                      "candidates": [_wn(w) for w in candidates],
                      "provenance": {str(k): v for k, v in prov.items()},
                      "source_provenance": {str(k): v for k, v in sprov.items()}})

    # ══ /api：其餘頁（re-platform 里程碑二）——共用既有 repo/service ══
    @app.post("/api/whynode/anoint")
    async def api_whynode_anoint(request: Request):
        b = await request.json()
        wid = int(b.get("id") or 0)
        if wid:
            repo = app.state.repo_factory(app.state.config)
            repo.anoint_why_node(wid, (b.get("claim") or "").strip() or None,
                                 (b.get("kind") or "").strip() or None)
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
        """知識的輸出（階段 30）：從已冊封核心理解生成高證實文章。守衛：只採已證實/推論、
        結構化 References、不回灌場。"""
        from ..backends.factory import make_embedder
        from ..output.article import generate_article
        b = await request.json()
        topic = str(b.get("topic") or "").strip()
        if not topic:
            return _JSON({"error": "請給一個主題"}, status_code=400)
        length = str(b.get("length") or "medium")
        level = str(b.get("level") or "intermediate")
        repo = app.state.repo_factory(app.state.config)
        try:
            nodes = repo.list_why_nodes("anointed")
        finally:
            repo.close()
        try:
            emb = getattr(app.state, "embedder_for_test", None) or make_embedder(app.state.config)
            out = generate_article(topic, nodes, _chat_backend(), embedder=emb, length=length, level=level)
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("生成文章失敗", extra={"extra": {"reason": str(e)}})
            return _JSON({"error": str(e)}, status_code=502)
        if out.get("empty"):
            return _JSON({"error": "場裡還沒有夠格（已證實／推論）的核心理解可寫成文章"}, status_code=200)
        out["length"], out["level"] = length, level
        return _JSON(out)

    @app.post("/api/article/save")
    async def api_article_save(request: Request):
        """存下生成的文章（輸出物、唯讀存檔）。"""
        b = await request.json()
        if not (b.get("markdown") or "").strip():
            return _JSON({"error": "沒有內容可存"}, status_code=400)
        repo = app.state.repo_factory(app.state.config)
        aid = repo.save_article(b.get("topic", ""), b.get("title", ""), b["markdown"],
                                b.get("length", ""), b.get("level", ""), _now_iso())
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

        def gen():
            repo = app.state.repo_factory(app.state.config)
            chunks = [_re.sub(r"<!--kf-page:\d+-->", "", c) for c in repo.get_source_chunks(u)]
            repo.close()
            if not chunks:
                yield _sse({"type": "error", "message": "找不到這份來源。"})
                return
            if not lang.is_english(stitch_chunks(chunks)):
                yield _sse({"type": "error", "message": "這份來源不是英文，不需要翻譯。"})
                return
            from ..backends.factory import make_translate_backend
            backend = make_translate_backend(app.state.config)
            # ⚠️ 不重用檢索用的塊——那是為 embedding 切的，會從單字中間切開
            # （實測 124 個接縫有 55 個是），"Conditioned Generat"＋"ion" 各自翻譯
            # 會變成「條件式 Generat」＋「離子」。先拼回全文，再切成合法的翻譯單位。
            pieces, seps = _tr.split_units(stitch_chunks(chunks))
            # 串流邏輯在 text/translate.py（那裡測得到時機）；這裡只負責包成 SSE。
            for kind, payload in _tr.translate_stream(pieces, backend):
                if kind == "stage":
                    yield _sse({"type": "stage", **payload})
                else:
                    out = payload["chunks"]
                    md_out = out[0] if out else ""
                    for piece, sep in zip(out[1:], seps):   # 照原本的分隔接回，不再比對
                        md_out += sep + piece
                    yield _sse({"type": "done", "total": payload["total"],
                                "failed": payload["failed"], "markdown": md_out})

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
            return _JSON({"ok": False, "err": "這份來源沒有足夠內容可整理出核心理解"})
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

    def _ingest_result(kind, **kw):
        try:
            res = _content_ingest(kind, **kw)
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("收進失敗", extra={"extra": {"reason": str(e)}})
            return _JSON({"status": "error", "err": str(e)}, status_code=502)
        return _JSON({"status": res.status, "count": getattr(res, "count", 0),
                      "title": getattr(res, "title", "")})

    @app.post("/api/ingest/paste")
    async def api_ingest_paste(request: Request):
        b = await request.json()
        text, html = (b.get("text") or ""), (b.get("html") or "")
        if not text.strip() and not html.strip():
            return _JSON({"status": "empty", "count": 0})
        at = (b.get("ingested_at") or "").strip() or _now_iso()[:10]
        return _ingest_result("text", text=text, title=b.get("title", ""), html=html,
                              clean=bool(b.get("clean")), source_url=b.get("source_url", ""),
                              note=b.get("note", ""), ingested_at=at)

    @app.post("/api/ingest/url")
    async def api_ingest_url(request: Request):
        b = await request.json()
        url = (b.get("url") or "").strip()
        if not url:
            return _JSON({"status": "empty", "count": 0})
        at = (b.get("ingested_at") or "").strip() or _now_iso()[:10]
        return _ingest_result("url", url=url, title=b.get("title", ""),
                              note=b.get("note", ""), ingested_at=at)

    @app.post("/api/ingest/youtube")
    async def api_ingest_youtube(request: Request):
        b = await request.json()
        url = (b.get("url") or "").strip()
        if not url:
            return _JSON({"status": "empty", "count": 0})
        return _ingest_result("youtube", url=url, title=b.get("title", ""))

    @app.post("/api/ingest/pdf")
    async def api_ingest_pdf(url: str = Form(""), title: str = Form(""),
                             file: UploadFile = File(None), note: str = Form(""),
                             ingested_at: str = Form("")):
        pdf_bytes = await file.read() if file is not None else None
        pdf_url = (url or "").strip()
        if not pdf_bytes and not pdf_url:
            return _JSON({"status": "empty", "count": 0})
        at = (ingested_at or "").strip() or _now_iso()[:10]
        return _ingest_result("pdf", pdf_bytes=pdf_bytes, pdf_url=pdf_url, title=title,
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
            return _ingest_result("url", url=url, title=title, note="手機分享", ingested_at=at)
        if text:
            return _ingest_result("text", text=text, title=title, note="手機分享", ingested_at=at)
        return _JSON({"status": "empty", "count": 0})

    @app.get("/api/conversations")
    async def api_conversations():
        repo = app.state.repo_factory(app.state.config)
        # spec 040：不再分暫存/永久，也不再依時間清理——移除的是機制，不是資料。
        convs = repo.list_conversations()
        repo.close()

        def _cv(c):
            return {"id": c.id, "title": c.title, "created_at": c.created_at,
                    "why_node_id": c.why_node_id, "count": len(c.messages)}
        return _JSON({"conversations": [_cv(c) for c in convs]})

    @app.get("/api/conversations/{cid}")
    async def api_conversation(cid: int, resume: int = Query(0)):
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        # referrers＝以此對話為由來的核心理解主張（給前端：編輯/重生時擋、護溯源）
        refs = [r["claim"] for r in repo.conversation_referrers(cid)] if conv is not None else []
        repo.close()
        if conv is None:
            return _JSON({"found": False}, status_code=404)
        return _JSON({"found": True, "id": conv.id, "title": conv.title,
                      "messages": conv.messages, "referrers": refs})

    @app.post("/api/conversations/{cid}/rename")
    async def api_conversation_rename(cid: int, request: Request):
        b = await request.json()
        repo = app.state.repo_factory(app.state.config)
        repo.rename_conversation(cid, b.get("title") or "")
        repo.close()
        return _JSON({"ok": True})

    @app.post("/api/conversations/{cid}/delete")
    async def api_conversation_delete(cid: int):
        """刪對話——但**被核心理解引用（由來）的刪不掉**（護溯源，原則 3）：回 blocked_by＝那些核心理解主張，
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
            return PlainTextResponse("找不到這段對話。", status_code=404)
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
