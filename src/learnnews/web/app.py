"""FastAPI web app（階段 6）。唯一 import 框架之處；核心全複用、零改動。

頁面：/（今日匯整）、/pull（即時拉＋快取）、/interests（增刪）。
後端失敗經例外處理器攔成友善繁中頁（FR-009、experience 教訓 3）。
可覆寫點（app.state）供測試注入：repo_factory、pull_service_factory、cache。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..backends.openai_api import OpenAIError
from ..config import Config
from ..interests.service import InterestService
from ..logging_setup import get_logger
from ..store.repository import Repository
from .cache import TTLCache
from .views import entry_to_page

_log = get_logger("learnnews.web")
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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


def _default_pull_runner(config: Config, repo_factory, service_factory, topic: str):
    """實際即時拉：組 adapter＋service→run_pull。可被 app.state.pull_runner 覆寫（測試）。

    web 上為求互動回應快，縮小規模：較少候選（少 embedding 呼叫）＋較少消化篇數
    （少 LLM 呼叫）。要更廣更深仍可用 CLI `learnnews pull`。
    """
    from ..cli.pull_cmd import build_pull_adapters, run_pull
    repo = repo_factory(config)
    sources = repo.list_sources(enabled_only=True)
    adapters = build_pull_adapters(sources, topic, max_results=12)  # 少候選＝少去重/排序
    service = service_factory(config)
    result = run_pull(adapters, topic, service=service, limit=6)    # 少消化＝快回應
    repo.close()
    return result


def create_app() -> FastAPI:
    app = FastAPI(title="LearnNews")
    app.state.config = Config.from_env()
    app.state.cache = TTLCache()
    app.state.repo_factory = _default_repo_factory
    app.state.pull_service_factory = _default_pull_service_factory
    app.state.pull_runner = lambda topic: _default_pull_runner(
        app.state.config, app.state.repo_factory, app.state.pull_service_factory, topic)

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
        topic = topic.strip()
        entries = []
        empty = True
        if topic:
            result = app.state.cache.get(topic)
            if result is None:
                result = app.state.pull_runner(topic)   # OpenAIError → 例外處理器
                app.state.cache.set(topic, result)
            entries = [entry_to_page(e) for e in result.entries]
            empty = result.is_empty
        return _TEMPLATES.TemplateResponse(request=request, name="pull.html", context={
            "topic": topic, "entries": entries, "empty": empty,
        })

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
