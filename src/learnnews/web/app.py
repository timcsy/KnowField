"""FastAPI web app（階段 6）。唯一 import 框架之處；核心全複用、零改動。

頁面：/（今日匯整）、/pull（即時拉＋快取）、/interests（增刪）。
後端失敗經例外處理器攔成友善繁中頁（FR-009、experience 教訓 3）。
可覆寫點（app.state）供測試注入：repo_factory、pull_service_factory、cache。
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from ..backends.openai_api import OpenAIError
from ..config import Config
from ..interests.service import InterestService
from ..logging_setup import get_logger
from ..pull.types import PullResult
from ..store.repository import Repository
from .cache import TTLCache
from .views import entry_to_page

_log = get_logger("learnnews.web")
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def render_entry(entry) -> str:
    """把一則 PullEntry/DigestEntry 渲染成卡片 HTML 片段（供 SSE 逐則推送）。"""
    return _TEMPLATES.get_template("_entry.html").render({"e": entry_to_page(entry)})


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _default_repo_factory(config: Config) -> Repository:
    from ..cli.fetchers import DEFAULT_SOURCES
    repo = Repository(config.db_path)
    if not repo.list_sources():
        for s in DEFAULT_SOURCES:
            repo.upsert_source(s)
    return repo


def _default_pull_service_factory(config: Config):
    from ..cli.pull_cmd import build_backend_pull_service
    return build_backend_pull_service(config)


def _default_pull_stream(config: Config, repo_factory, service_factory, topic: str):
    """實際串流即時拉：組 adapter＋service→service.pull_stream。逐步 yield 進度事件。
    可被 app.state.pull_stream_factory 覆寫（測試）。web 縮小規模（少候選/少篇數）求快。"""
    from ..cli.pull_cmd import build_pull_adapters
    repo = repo_factory(config)
    sources = repo.list_sources(enabled_only=True)
    adapters = build_pull_adapters(sources, topic, max_results=12)
    service = service_factory(config)
    try:
        yield from service.pull_stream(adapters=adapters, topic=topic, limit=6)
    finally:
        repo.close()


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
                             explainer_weight=config.rag_explainer_weight)
        return service.answer(question, Scope(today=today), lang=lang)
    finally:
        repo.close()


def create_app() -> FastAPI:
    app = FastAPI(title="LearnNews")
    app.state.config = Config.from_env()
    app.state.cache = TTLCache()
    app.state.repo_factory = _default_repo_factory
    app.state.pull_service_factory = _default_pull_service_factory
    app.state.pull_stream_factory = lambda topic: _default_pull_stream(
        app.state.config, app.state.repo_factory, app.state.pull_service_factory, topic)
    app.state.rag_answer_factory = lambda question, today, lang: _default_rag_answer(
        app.state.config, app.state.repo_factory, question, today, lang)

    @app.exception_handler(OpenAIError)
    async def _backend_error(request: Request, exc: OpenAIError):
        _log.error("web 後端失敗", extra={"extra": {"reason": str(exc)}})
        return _TEMPLATES.TemplateResponse(
            request=request, name="error.html", context={"reason": str(exc)},
            status_code=503)

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        repo = app.state.repo_factory(app.state.config)
        digest = repo.get_last_digest()
        repo.close()
        entries = [entry_to_page(e) for e in digest.entries] if digest else []
        return _TEMPLATES.TemplateResponse(request=request, name="digest.html", context={
            "date": digest.date if digest else None,
            "entries": entries,
            "missing_sources": digest.missing_sources if digest else [],
        })

    @app.get("/pull", response_class=HTMLResponse)
    async def pull(request: Request, topic: str = ""):
        # 串流殼：頁面立即回，實際結果由 /pull/stream 逐則推送到前端（即時進度）
        return _TEMPLATES.TemplateResponse(
            request=request, name="pull.html", context={"topic": topic.strip()})

    @app.get("/pull/stream")
    async def pull_stream(topic: str = ""):
        topic = topic.strip()

        def gen():
            if not topic:
                yield _sse({"type": "done"})
                return
            cached = app.state.cache.get(topic)
            if cached is not None:                       # 快取：逐則秒推
                for e in cached.entries:
                    yield _sse({"type": "card", "html": render_entry(e)})
                if not cached.entries:
                    yield _sse({"type": "empty"})
                yield _sse({"type": "done"})
                return
            entries = []
            try:
                for ev in app.state.pull_stream_factory(topic):
                    if ev["type"] == "card":
                        entries.append(ev["entry"])
                        yield _sse({"type": "card", "html": render_entry(ev["entry"]),
                                    "progress": ev.get("progress")})
                    elif ev["type"] == "stage":
                        yield _sse({"type": "stage", "text": ev["text"]})
                    elif ev["type"] == "empty":
                        yield _sse({"type": "empty"})
                app.state.cache.set(topic, PullResult(topic=topic, entries=entries))
                yield _sse({"type": "done"})
            except OpenAIError as e:                     # 串流中失敗 → 推 error 事件
                _log.error("web 串流後端失敗", extra={"extra": {"reason": str(e)}})
                yield _sse({"type": "error", "text": str(e)})

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/ask", response_class=HTMLResponse)
    async def ask(request: Request, q: str = "", today: bool = False):
        # 問答幾秒內就回，不需 SSE；後端失敗經全域 OpenAIError 處理器攔成友善頁。
        question = q.strip()
        answer = None
        if question:
            answer = app.state.rag_answer_factory(
                question, today, app.state.config.article_lang)
        return _TEMPLATES.TemplateResponse(request=request, name="ask.html", context={
            "q": question, "today": today, "answer": answer})

    @app.get("/interests", response_class=HTMLResponse)
    async def interests(request: Request):
        repo = app.state.repo_factory(app.state.config)
        topics = InterestService(repo).list_topics()
        repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="interests.html", context={"topics": topics})

    @app.post("/interests/add")
    async def interests_add(topic: str = Form("")):
        if topic.strip():
            repo = app.state.repo_factory(app.state.config)
            InterestService(repo).add(topic.strip())
            repo.close()
        return RedirectResponse("/interests", status_code=303)

    @app.post("/interests/remove")
    async def interests_remove(topic: str = Form("")):
        if topic.strip():
            repo = app.state.repo_factory(app.state.config)
            InterestService(repo).remove(topic.strip())
            repo.close()
        return RedirectResponse("/interests", status_code=303)

    return app


app = create_app()
