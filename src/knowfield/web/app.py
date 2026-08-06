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
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates

from ..backends.openai_api import OpenAIError
from ..config import Config
from ..sources.base import SourceUnavailable
from ..logging_setup import get_logger
from ..store.repository import Repository
from .cache import TTLCache

_log = get_logger("knowfield.web")
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _default_repo_factory(config: Config) -> Repository:
    from ..cli.fetchers import DEFAULT_SOURCES
    repo = Repository(config.db_path)
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

    def _content_ingest(kind, **kw):
        """貼上/PDF/URL 收進：切塊→存成 corpus（spec 030）。轉檔器/抓取器可注入。"""
        from ..backends.factory import make_embedder
        from ..ingest.service import ContentIngestService
        cfg = app.state.config
        repo = app.state.repo_factory(cfg)
        try:
            svc = ContentIngestService(repo, make_embedder(cfg), app.state.doc_converter,
                                       chat_backend=_chat_backend())
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

    def _default_chat(history, message, brainstorm=False):
        from ..chat.field_chat import FieldChat
        repo = app.state.repo_factory(app.state.config)
        try:
            roots = repo.list_why_nodes("anointed")
        finally:
            repo.close()
        fc = FieldChat(_chat_backend())
        url_contents = _fetch_message_urls(message)   # 貼的網址→讀進來（best-effort）
        if brainstorm:
            sources = []
        else:
            q = fc.search_query(history, message)        # LLM 先把問題轉成好 query（消歧義）
            # web 撒網＋收進的文章併成一個連號來源清單（web 在前、收進在後，帶 kind）
            sources = list(_chat_search(q)) + _chat_corpus(message)
        text = fc.reply(history, message, roots, sources, brainstorm=brainstorm,
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
        return _TEMPLATES.TemplateResponse(
            request=request, name="error.html", context={"reason": str(exc)},
            status_code=503)

    @app.get("/")
    async def home():
        # re-platform（階段 27）：門面＝React SPA（/app）。dist 未 build 時退回舊 Jinja /chat。
        _dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
        return RedirectResponse("/app/" if _dist.is_dir() else "/chat", status_code=307)

    @app.get("/ask")
    async def ask():
        # spec 029：問答併進聊天——「對收進內容發問」的能力現在在 /chat（帶膜、能引用「你收藏的」）。
        return RedirectResponse("/chat", status_code=302)

    @app.get("/ingest", response_class=HTMLResponse)
    async def ingest_get(request: Request):
        return _TEMPLATES.TemplateResponse(request=request, name="ingest.html", context={})

    @app.post("/ingest", response_class=HTMLResponse)
    async def ingest_post(request: Request, ref: str = Form(""),
                          explainer: bool = Form(False)):
        ref = ref.strip()
        result = error = None
        if ref:
            try:
                result = app.state.seed_ingest_factory(ref, explainer)
            except (SourceUnavailable, OpenAIError) as e:   # 表單頁內攔，不噴 500
                _log.error("web 種子 ingest 失敗", extra={"extra": {"reason": str(e)}})
                error = str(e)
        return _TEMPLATES.TemplateResponse(request=request, name="ingest.html", context={
            "ref": ref, "result": result, "error": error})

    @app.post("/ingest/paste", response_class=HTMLResponse)
    async def ingest_paste(request: Request):
        """貼上收進（spec 030 US1＋spec 031）：html 非空＝rich-paste 抽正文＋圖片；clean=1＝LLM 清理。"""
        # 手動 parse、拉高欄位上限（rich-paste 的 HTML 可能很大，預設 1MB 會爆）
        form = await request.form(max_part_size=24 * 1024 * 1024)
        text = str(form.get("text", "") or "")
        title = str(form.get("title", "") or "")
        html = str(form.get("html", "") or "")
        clean = str(form.get("clean", "") or "")
        source_url = str(form.get("source_url", "") or "")
        note = str(form.get("note", "") or "")
        at = str(form.get("ingested_at", "") or "").strip() or _now_iso()[:10]
        content_result = error = None
        if (text or "").strip() or (html or "").strip():
            try:
                content_result = app.state.content_ingest(
                    "text", text=text, title=title, html=html, clean=(clean == "1"),
                    source_url=source_url, note=note, ingested_at=at)
            except (SourceUnavailable, OpenAIError) as e:
                _log.error("貼上收進失敗", extra={"extra": {"reason": str(e)}})
                error = str(e)
        return _TEMPLATES.TemplateResponse(request=request, name="ingest.html", context={
            "content_result": content_result, "error": error})

    @app.post("/ingest/url", response_class=HTMLResponse)
    async def ingest_url(request: Request, url: str = Form(""), title: str = Form(""),
                         note: str = Form(""), ingested_at: str = Form("")):
        """收整篇網頁（spec 030 增量）：抓正文→markdown→切塊→存。best-effort。"""
        content_result = error = None
        at = (ingested_at or "").strip() or _now_iso()[:10]
        if (url or "").strip():
            try:
                content_result = app.state.content_ingest("url", url=url, title=title,
                                                          note=note, ingested_at=at)
            except (SourceUnavailable, OpenAIError) as e:
                _log.error("網頁收進失敗", extra={"extra": {"reason": str(e)}})
                error = str(e)
        return _TEMPLATES.TemplateResponse(request=request, name="ingest.html", context={
            "content_result": content_result, "error": error})

    @app.post("/ingest/youtube", response_class=HTMLResponse)
    async def ingest_youtube(request: Request, url: str = Form(""), title: str = Form("")):
        """收 YouTube 逐字稿（spec 030 增量）：抓字幕→切塊→存。抓不到→友善（改用貼上）。"""
        content_result = error = None
        if (url or "").strip():
            try:
                content_result = app.state.content_ingest("youtube", url=url, title=title)
            except (SourceUnavailable, OpenAIError) as e:
                _log.error("YouTube 收進失敗", extra={"extra": {"reason": str(e)}})
                error = str(e)
        return _TEMPLATES.TemplateResponse(request=request, name="ingest.html", context={
            "content_result": content_result, "error": error})

    @app.post("/ingest/pdf", response_class=HTMLResponse)
    async def ingest_pdf(request: Request, url: str = Form(""), title: str = Form(""),
                         file: UploadFile = File(None), note: str = Form(""),
                         ingested_at: str = Form("")):
        """PDF 收進（spec 030 US2）：轉檔→切塊→存成語料。>30 頁不崩、失敗 best-effort。"""
        content_result = error = None
        pdf_bytes = await file.read() if file is not None else None
        pdf_url = (url or "").strip()
        at = (ingested_at or "").strip() or _now_iso()[:10]
        if pdf_bytes or pdf_url:
            try:
                content_result = app.state.content_ingest(
                    "pdf", pdf_bytes=pdf_bytes, pdf_url=pdf_url, title=title,
                    note=note, ingested_at=at)
            except (SourceUnavailable, OpenAIError) as e:
                _log.error("PDF 收進失敗", extra={"extra": {"reason": str(e)}})
                error = str(e)
        return _TEMPLATES.TemplateResponse(request=request, name="ingest.html", context={
            "content_result": content_result, "error": error})

    @app.get("/library", response_class=HTMLResponse)
    async def library(request: Request):
        """知識庫：按來源（同 url）歸一列（spec 031 US1）。"""
        repo = app.state.repo_factory(app.state.config)
        sources = repo.list_source_groups()
        repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="library.html", context={"sources": sources})

    @app.get("/source", response_class=HTMLResponse)
    async def source_detail(request: Request, u: str = Query(""), err: str = Query("")):
        """來源詳情：把該來源的塊拼回、去重疊、render（spec 031 US2）。"""
        from ..ingest.chunk import stitch_chunks
        repo = app.state.repo_factory(app.state.config)
        chunks = repo.get_source_chunks(u)
        title = repo.source_title(u)
        meta = repo.source_meta(u)
        repo.close()
        if not chunks:
            return RedirectResponse("/library", status_code=303)
        return _TEMPLATES.TemplateResponse(
            request=request, name="source.html",
            context={"title": title, "url": u, "markdown": stitch_chunks(chunks),
                     "note": meta["note"], "ingested_at": meta["ingested_at"], "err": err})

    @app.post("/source/distill")
    async def source_distill(u: str = Form("")):
        """整理成核心理解（spec 032）：對一份收進來源抽候選根因 → 存候選 → 導 /roots 由人檢視冊封。
        只產候選、不冊封、不進地基（原則 6）；萃取失敗 best-effort 導回 /source（教訓 3）。"""
        from urllib.parse import quote

        from ..ingest.activate import distill_source
        url = (u or "").strip()
        if not url:
            return RedirectResponse("/library", status_code=303)
        try:
            repo = app.state.repo_factory(app.state.config)
            try:
                cand = distill_source(repo, _extractor(), url, _now_iso())
            finally:
                repo.close()
        except SourceUnavailable as e:
            return RedirectResponse(f"/source?u={quote(url)}&err={quote(str(e))}",
                                    status_code=303)
        if cand is None:
            return RedirectResponse(
                f"/source?u={quote(url)}&err={quote('這份來源沒有足夠內容可整理出核心理解')}",
                status_code=303)
        return RedirectResponse(
            f"/roots?msg={quote('已整理出候選核心理解，請檢視後收進你認同的')}",
            status_code=303)

    @app.post("/source/meta")
    async def source_meta_edit(u: str = Form(""), note: str = Form(""),
                               ingested_at: str = Form("")):
        """編輯來源的收進原因＋日期（脈絡註記，不進 embedding/chat）。"""
        if (u or "").strip():
            repo = app.state.repo_factory(app.state.config)
            repo.set_source_meta(u, note, ingested_at)
            repo.close()
        from urllib.parse import quote
        return RedirectResponse(f"/source?u={quote(u)}", status_code=303)

    @app.post("/library/remove")
    async def library_remove(url: str = Form("")):
        if (url or "").strip():
            repo = app.state.repo_factory(app.state.config)
            repo.delete_source(url)                 # 整份來源（所有塊）；每日流不動作
            repo.close()
        return RedirectResponse("/library", status_code=303)

    @app.post("/library/reclassify")
    async def library_reclassify(url: str = Form(""),
                                 source_class: str = Form("ordinary")):
        if (url or "").strip():
            repo = app.state.repo_factory(app.state.config)
            repo.set_source_class_by_url(url, source_class)  # 整份來源標解說文/改一般
            repo.close()
        return RedirectResponse("/library", status_code=303)

    @app.get("/roots", response_class=HTMLResponse)
    async def roots(request: Request, msg: str = ""):
        repo = app.state.repo_factory(app.state.config)
        candidates = repo.list_why_nodes("candidate")
        anointed = repo.list_why_nodes("anointed")
        provenance = repo.why_node_provenance()     # {why_node_id: conversation_id}（spec 023 由來連結）
        source_provenance = repo.why_node_source_provenance()  # {wid: source_url}（spec 032 源→根因由來）
        repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="roots.html",
            context={"candidates": candidates, "anointed": anointed, "msg": msg,
                     "provenance": provenance, "source_provenance": source_provenance})

    @app.post("/whynode/anoint")
    async def whynode_anoint(id: int = Form(0), claim: str = Form("")):
        if id:
            repo = app.state.repo_factory(app.state.config)
            repo.anoint_why_node(id, claim or None)    # 人冊封（可編輯）→ 正式吸引子（原則 5）
            repo.close()
        return RedirectResponse("/roots", status_code=303)

    @app.post("/whynode/remove")
    async def whynode_remove(id: int = Form(0)):
        if id:
            repo = app.state.repo_factory(app.state.config)
            repo.delete_why_node(id)
            repo.close()
        return RedirectResponse("/roots", status_code=303)

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

    @app.get("/chat", response_class=HTMLResponse)
    async def chat_get(request: Request):
        repo = app.state.repo_factory(app.state.config)
        repo.purge_expired_temporary(_now_iso())        # 順手懶清（spec 028）
        temps = [c for c in repo.list_conversations() if c.temporary]
        repo.close()
        recent = temps[0] if temps else None            # list_conversations 新到舊 → 最近暫存
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": [], "history_json": "[]", "root_count": _root_count(),
                     "recent_temp": recent})

    @app.post("/chat", response_class=HTMLResponse)
    async def chat_post(request: Request, history: str = Form("[]"), message: str = Form(""),
                        brainstorm: str = Form(""), last_captured: str = Form("0")):
        """一輪對話：從你冊封的根因往下推、反逢迎的膜（原則 5/6）。對話不落庫、不自動改場。
        brainstorm=1：純發想、不撒網找佐證（沙盒模式，principle 6）。"""
        hist = _parse_history(history)
        message = (message or "").strip()
        err = None
        if message:
            try:
                result = app.state.chat_factory(hist, message, brainstorm == "1")
                text, sources = result if isinstance(result, tuple) else (result, [])
                hist = hist + [{"role": "user", "content": message},
                               {"role": "assistant", "content": text, "sources": sources}]
            except (SourceUnavailable, OpenAIError) as e:        # 對話失敗→友善（教訓 3）
                _log.error("場對話失敗", extra={"extra": {"reason": str(e)}})
                hist = hist + [{"role": "user", "content": message}]
                err = str(e)
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": hist, "history_json": json.dumps(hist, ensure_ascii=False),
                     "err": err, "root_count": _root_count(),
                     "distill_nudge": _distill_nudge(hist, last_captured)})

    def _stream_gen(hist, message, bs):
        """SSE 生成器：/chat/stream 與 /api/chat/stream 共用（協定：stage/token/done/error）。"""
        from ..chat.field_chat import FieldChat
        cfg = app.state.config
        if not message:
            yield _sse({"type": "done", "text": ""})
            return
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
            if bs:
                sources = []
            else:
                yield _sse({"type": "stage", "text": "找關鍵字…"})
                q = fc.search_query(hist, message)
                yield _sse({"type": "stage", "text": "撒網找佐證…"})
                web = _chat_search(q)
                yield _sse({"type": "stage", "text": "翻你收進的資料…"})
                sources = list(web) + _chat_corpus(message)   # web＋收進併成連號清單
            yield _sse({"type": "stage", "text": "回答中…"})
            full = ""
            for delta in fc.reply_stream(hist, message, roots, sources, brainstorm=bs,
                                         max_history=cfg.chat_context_messages,
                                         url_contents=url_contents):
                full += delta
                yield _sse({"type": "token", "text": delta})
            cited = {int(n) for n in re.findall(r"\[(\d+)\]", full)}
            numbered = [{"n": i, "url": s.url, "title": s.title or s.url,
                         "kind": getattr(s, "kind", "web")}
                        for i, s in enumerate(sources, 1) if i in cited]
            # 有撒到、但沒被引用的來源 → 折疊區「也找到（未直接引用）」（不進存檔）
            extra = [{"n": i, "url": s.url, "title": s.title or s.url,
                      "kind": getattr(s, "kind", "web")}
                     for i, s in enumerate(sources, 1) if i not in cited]
            yield _sse({"type": "done", "text": full, "sources": numbered, "found_extra": extra})
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("場對話串流失敗", extra={"extra": {"reason": str(e)}})
            yield _sse({"type": "error", "text": str(e)})

    @app.post("/chat/stream")
    async def chat_stream(history: str = Form("[]"), message: str = Form(""),
                          brainstorm: str = Form("")):
        """串流版對話：分段進度＋逐 token 串流；只列被引用來源（沿用 _stream_gen）。"""
        hist = _parse_history(history)
        return StreamingResponse(
            _stream_gen(hist, (message or "").strip(), brainstorm == "1"),
            media_type="text/event-stream")

    @app.post("/chat/branch", response_class=HTMLResponse)
    async def chat_branch(request: Request, history: str = Form("[]"), draft: str = Form("")):
        """從某句開新分支：另開一頁、載入 history 前綴＋把那句放回輸入框（原對話那頁不動）。"""
        hist = _parse_history(history)
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": hist, "history_json": json.dumps(hist, ensure_ascii=False),
                     "draft": draft, "root_count": _root_count()})

    @app.post("/chat/distill", response_class=HTMLResponse)
    async def chat_distill(request: Request, history: str = Form("[]"),
                           temp_id: str = Form(""), as_: str = Form("", alias="as")):
        hist = _parse_history(history)
        cands = err = None
        try:
            cands = app.state.distill_factory(hist)      # 一到多條（可能不同層次、標 already）
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("蒸餾候選失敗", extra={"extra": {"reason": str(e)}})
            err = str(e)
        if as_ == "json":       # AJAX：原地渲染候選、不重載整頁（不跳離對話）
            from fastapi.responses import JSONResponse
            if err is not None:
                return JSONResponse({"error": err}, status_code=502)
            return JSONResponse({"candidates": [
                {"claim": c.claim, "kind": c.kind, "ladder": c.ladder,
                 "evidence_urls": c.evidence_urls, "already": c.already}
                for c in (cands or [])]})
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": hist, "history_json": json.dumps(hist, ensure_ascii=False),
                     "candidates": cands, "err": err, "root_count": _root_count(),
                     "temp_id": temp_id})     # 傳遞暫存 id → 候選冊封時升永久（spec 028）

    def _do_anoint(claim, ladder, evidence_urls, save_convo, history, temp_id):
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
            wid = repo.add_why_node(claim, urls, [], False, 0, _now_iso(), ladder=steps)
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

    @app.post("/chat/anoint", response_class=HTMLResponse)
    async def chat_anoint(request: Request, claim: str = Form(""),
                          ladder: str = Form(""), evidence_urls: str = Form(""),
                          save_convo: str = Form(""), history: str = Form("[]"),
                          temp_id: str = Form(""), as_: str = Form("", alias="as")):
        """人閘門：唯有此路由（人按）寫 bedrock（原則 5，沿用 _do_anoint）。"""
        status, claim, msg = _do_anoint(claim, ladder, evidence_urls, save_convo, history, temp_id)
        if as_ == "json":       # AJAX：原地標記、不重載（不清空對話、不跳主頁）
            from fastapi.responses import JSONResponse
            return JSONResponse({"status": status, "claim": claim, "msg": msg})
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": [], "history_json": "[]", "anoint_msg": msg,
                     "root_count": _root_count()})

    @app.post("/chat/autosave")
    async def chat_autosave(history: str = Form("[]"), temp_id: str = Form("")):
        """自動暫存（spec 028）：每輪 upsert 一筆暫存、回 temp_id。best-effort——失敗回 null、不擋聊天。"""
        from fastapi.responses import JSONResponse
        messages = _parse_history(history)
        try:
            repo = app.state.repo_factory(app.state.config)
            tid = repo.autosave_temporary(_temp_id(temp_id) or None, messages, _now_iso())
            repo.close()
        except Exception as e:  # noqa: BLE001 - autosave 不該擋聊天（教訓 3）
            _log.error("自動暫存失敗", extra={"extra": {"reason": str(e)}})
            tid = None
        return JSONResponse({"temp_id": tid})

    # ══ /api：JSON/SSE 門面（re-platform 階段一，vision 階段 27）══
    # 共用上面的服務閉包（_stream_gen/_do_anoint/distill_factory/repo）——零邏輯重寫、行為天然一致。
    from fastapi.responses import JSONResponse as _JSON

    @app.get("/api/chat/state")
    async def api_chat_state():
        repo = app.state.repo_factory(app.state.config)
        repo.purge_expired_temporary(_now_iso())
        temps = [c for c in repo.list_conversations() if c.temporary]
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
        return StreamingResponse(_stream_gen(hist, message, bool(body.get("brainstorm"))),
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
             "evidence_urls": c.evidence_urls, "already": c.already}
            for c in (cands or [])]})

    @app.post("/api/chat/anoint")
    async def api_chat_anoint(request: Request):
        """人閘門冊封（沿用 _do_anoint；React 也只能經此寫地基）。"""
        body = await request.json()
        status, claim, msg = _do_anoint(
            body.get("claim", ""), body.get("ladder", ""), body.get("evidence_urls", ""),
            "1" if body.get("save_convo") else "",
            json.dumps(body.get("history") or [], ensure_ascii=False),
            str(body.get("temp_id") or ""))
        return _JSON({"status": status, "claim": claim, "msg": msg})

    @app.post("/api/chat/autosave")
    async def api_chat_autosave(request: Request):
        body = await request.json()
        try:
            repo = app.state.repo_factory(app.state.config)
            tid = repo.autosave_temporary(_temp_id(str(body.get("temp_id") or "")) or None,
                                          body.get("history") or [], _now_iso())
            repo.close()
        except Exception as e:  # noqa: BLE001 - autosave 不擋聊天（教訓 3）
            _log.error("自動暫存失敗", extra={"extra": {"reason": str(e)}})
            tid = None
        return _JSON({"temp_id": tid})

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
                    "ladder": w.ladder, "touchstones": w.touchstones, "fog_flag": w.fog_flag}
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
            repo.anoint_why_node(wid, (b.get("claim") or "").strip() or None)
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

    @app.get("/api/library")
    async def api_library():
        repo = app.state.repo_factory(app.state.config)
        groups = repo.list_source_groups()
        repo.close()
        return _JSON({"sources": groups})

    @app.get("/api/source")
    async def api_source(u: str = Query("")):
        from ..ingest.chunk import stitch_chunks
        repo = app.state.repo_factory(app.state.config)
        chunks = repo.get_source_chunks(u)
        title = repo.source_title(u)
        meta = repo.source_meta(u)
        repo.close()
        if not chunks:
            return _JSON({"found": False}, status_code=404)
        return _JSON({"found": True, "url": u, "title": title,
                      "markdown": stitch_chunks(chunks),
                      "note": meta["note"], "ingested_at": meta["ingested_at"]})

    @app.post("/api/source/meta")
    async def api_source_meta(request: Request):
        b = await request.json()
        u = (b.get("u") or "").strip()
        if u:
            repo = app.state.repo_factory(app.state.config)
            repo.set_source_meta(u, b.get("note", ""), b.get("ingested_at", ""))
            repo.close()
        return _JSON({"ok": True})

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
        repo.purge_expired_temporary(_now_iso())
        convs = repo.list_conversations()
        repo.close()

        def _cv(c):
            return {"id": c.id, "title": c.title, "created_at": c.created_at,
                    "temporary": c.temporary, "why_node_id": c.why_node_id,
                    "count": len(c.messages)}
        return _JSON({"permanent": [_cv(c) for c in convs if not c.temporary],
                      "temporary": [_cv(c) for c in convs if c.temporary]})

    @app.get("/api/conversations/{cid}")
    async def api_conversation(cid: int, resume: int = Query(0)):
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        if conv is not None and resume and conv.temporary:
            repo.touch_conversation(cid, _now_iso())
        repo.close()
        if conv is None:
            return _JSON({"found": False}, status_code=404)
        return _JSON({"found": True, "id": conv.id, "title": conv.title,
                      "messages": conv.messages, "temporary": conv.temporary})

    @app.post("/api/conversations/{cid}/rename")
    async def api_conversation_rename(cid: int, request: Request):
        b = await request.json()
        repo = app.state.repo_factory(app.state.config)
        repo.rename_conversation(cid, b.get("title") or "")
        repo.close()
        return _JSON({"ok": True})

    @app.post("/api/conversations/{cid}/promote")
    async def api_conversation_promote_json(cid: int):
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        if conv is not None:
            try:
                t = (app.state.title_factory(conv.messages) or "").strip()
            except Exception:  # noqa: BLE001
                t = ""
            repo.promote_conversation(cid, t or conv.title)
        repo.close()
        return _JSON({"ok": True})

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

    # ══ 服務 React SPA（掛 /app，strangler：舊 Jinja / 與 /chat 不動）══
    _DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if _DIST.is_dir():
        from starlette.exceptions import HTTPException as _StarletteHTTPExc
        from fastapi.staticfiles import StaticFiles

        @app.post("/app/share-target")
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
            return RedirectResponse("/app/library", status_code=303)

        class _SpaStatic(StaticFiles):
            """服務 dist 靜態檔（含 manifest/sw/icon）；client 路由（非檔案）fallback 回 index.html。"""
            async def get_response(self, path, scope):
                try:
                    return await super().get_response(path, scope)
                except _StarletteHTTPExc as e:
                    if e.status_code == 404:
                        return await super().get_response("index.html", scope)
                    raise

        app.mount("/app", _SpaStatic(directory=str(_DIST), html=True), name="spa")

    @app.post("/conversations/{cid}/promote")
    async def conversation_promote(cid: int):
        """把暫存升為永久（spec 028，人按「轉永久」）：生落點標題、解除 TTL。"""
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        if conv is not None:
            try:
                t = (app.state.title_factory(conv.messages) or "").strip()
            except Exception:  # noqa: BLE001
                t = ""
            repo.promote_conversation(cid, t or conv.title)
        repo.close()
        return RedirectResponse("/conversations", status_code=303)

    @app.post("/chat/save", response_class=HTMLResponse)
    async def chat_save(request: Request, history: str = Form("[]"), temp_id: str = Form("")):
        """獨立存這段對話（spec 023，人閘門、原則 5）。有暫存→升永久同一筆（spec 028）。空對話→友善不存。"""
        messages = _parse_history(history)
        saved_msg = None
        if messages:
            repo = app.state.repo_factory(app.state.config)
            repo.purge_expired_temporary(_now_iso())
            tid = _temp_id(temp_id)
            if tid:                         # 有暫存→升永久同一筆＋生落點標題（不新增）
                repo.promote_conversation(tid, _convo_title(messages))
            else:
                repo.save_conversation(_convo_title(messages), messages, None)
            repo.close()
            saved_msg = "已存下這段對話（可到『對話存檔』檢視）"
        else:
            saved_msg = "這段對話還是空的，沒有東西可存。"
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": [], "history_json": "[]", "anoint_msg": saved_msg,
                     "root_count": _root_count()})

    @app.get("/conversations/dedupe", response_class=HTMLResponse)
    async def dedupe_preview(request: Request):
        """清理重複對話——預覽（唯讀、人閘門，原則 5）。算計畫、不動資料。"""
        repo = app.state.repo_factory(app.state.config)
        plan = repo.dedupe_plan()
        repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="dedupe.html",
            context={"n_groups": plan.n_groups, "n_extra": plan.n_extra,
                     "n_roots": plan.n_roots})

    @app.post("/conversations/dedupe")
    async def dedupe_apply(request: Request):
        """清理重複對話——執行（人確認後）：同指紋併一份、根因重指、刪其餘（非破壞）。"""
        repo = app.state.repo_factory(app.state.config)
        summary = repo.apply_dedupe()
        repo.close()
        return RedirectResponse(
            f"/conversations?cleaned=1&removed={summary['removed']}"
            f"&repointed={summary['repointed']}", status_code=303)

    @app.get("/conversations", response_class=HTMLResponse)
    async def conversations_list(request: Request, cleaned: str = "", removed: str = "",
                                 repointed: str = ""):
        """存下的對話清單（唯讀；不入地基，原則 6）。cleaned=1 時顯示清理成功 flash。"""
        repo = app.state.repo_factory(app.state.config)
        repo.purge_expired_temporary(_now_iso())      # 懶清過期暫存（spec 028，不開背景）
        convs = repo.list_conversations()
        repo.close()
        permanent = [c for c in convs if not c.temporary]
        temporary = [c for c in convs if c.temporary]
        return _TEMPLATES.TemplateResponse(
            request=request, name="conversations.html",
            context={"conversations": permanent, "temporary": temporary,
                     "cleaned": cleaned == "1", "removed": removed, "repointed": repointed})

    @app.get("/conversations/{cid}", response_class=HTMLResponse)
    async def conversation_view(request: Request, cid: int):
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        repo.close()
        if conv is None:
            return RedirectResponse("/conversations", status_code=303)
        return _TEMPLATES.TemplateResponse(
            request=request, name="conversation.html", context={"conv": conv})

    @app.get("/conversations/{cid}/resume", response_class=HTMLResponse)
    async def conversation_resume(request: Request, cid: int):
        """以存下的對話接著聊：載進 live /chat（原存檔是快照、不動）；載進去後可從任一句編輯/開分支。"""
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        if conv is not None and conv.temporary:
            repo.touch_conversation(cid, _now_iso())    # 接回暫存→重設計時（spec 028）
        rc = len(repo.list_why_nodes("anointed"))
        repo.close()
        if conv is None:
            return RedirectResponse("/conversations", status_code=303)
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": conv.messages,
                     "history_json": json.dumps(conv.messages, ensure_ascii=False),
                     # 接回暫存→續聊 autosave 更新同一筆（永久的則不帶，續聊會另開暫存）
                     "temp_id": cid if conv.temporary else "",
                     "root_count": rc})

    # --- 匯出給 NotebookLM（spec 024）：純唯讀、只把沉澱物匯出，不注入回場（原則 6）---
    def _export_conversation(title: str, messages: list, as_: str) -> str:
        from ..export.notebooklm import (
            conversation_evidence_urls,
            conversation_to_markdown,
        )
        if as_ == "urls":
            return "\n".join(conversation_evidence_urls(messages))
        return conversation_to_markdown(title, messages)

    @app.post("/chat/export")
    async def chat_export(history: str = Form("[]"), title: str = Form(""),
                          as_: str = Form("md", alias="as")):
        """匯出當前（live）對話。history 由前端帶回；純唯讀、不落庫。"""
        messages = _parse_history(history)
        return PlainTextResponse(_export_conversation(title, messages, as_))

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

    @app.post("/conversations/{cid}/rename")
    async def conversation_rename(cid: int, title: str = Form("")):
        """手動改名（spec 027 US1，人閘門）。空標題→不改。"""
        repo = app.state.repo_factory(app.state.config)
        repo.rename_conversation(cid, title)
        repo.close()
        return RedirectResponse(f"/conversations/{cid}", status_code=303)

    @app.post("/conversations/{cid}/retitle")
    async def conversation_retitle(cid: int):
        """重生自動標題（spec 027 US1，人按才做，反映落點）。失敗→不改、不崩。"""
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        if conv is not None:
            try:
                t = (app.state.title_factory(conv.messages) or "").strip()
            except Exception as e:  # noqa: BLE001
                _log.error("重生標題失敗", extra={"extra": {"reason": str(e)}})
                t = ""
            if t:
                repo.rename_conversation(cid, t)
        repo.close()
        return RedirectResponse(f"/conversations/{cid}", status_code=303)

    @app.post("/conversations/{cid}/segment", response_class=HTMLResponse)
    async def conversation_segment(request: Request, cid: int):
        """整理成章節（spec 027 US2，on-demand、不落庫）。失敗→整段一章、不崩。"""
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        repo.close()
        if conv is None:
            return RedirectResponse("/conversations", status_code=303)
        try:
            chapters = app.state.segment_factory(conv.messages)
        except Exception as e:  # noqa: BLE001 - 切分失敗退整段
            _log.error("章節切分失敗", extra={"extra": {"reason": str(e)}})
            from ..chat.capture import normalize_chapters
            chapters = normalize_chapters([], len(conv.messages))
        return _TEMPLATES.TemplateResponse(
            request=request, name="conversation.html",
            context={"conv": conv, "chapters": chapters})

    @app.post("/conversations/{cid}/distill", response_class=HTMLResponse)
    async def conversation_chapter_distill(request: Request, cid: int,
                                           from_: int = Query(0, alias="from"),
                                           to: int = Query(0)):
        """整理某一章成重點（spec 027 US3）：切片→既有蒸餾→候選頁（人閘門、不自動冊封）。"""
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        repo.close()
        if conv is None:
            return RedirectResponse("/conversations", status_code=303)
        slice_ = conv.messages[max(0, from_ - 1):to] if (from_ and to) else conv.messages
        cands = err = None
        try:
            cands = app.state.distill_factory(slice_)
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("整理章節失敗", extra={"extra": {"reason": str(e)}})
            err = str(e)
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": [], "history_json": json.dumps(slice_, ensure_ascii=False),
                     "candidates": cands, "err": err, "root_count": _root_count()})

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

    return app


app = create_app()
