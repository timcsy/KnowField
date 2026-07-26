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
from ..sources.base import SourceUnavailable
from ..interests.service import InterestService
from ..logging_setup import get_logger
from ..pull.types import PullResult
from ..store.repository import Repository
from .cache import TTLCache
from .views import entry_to_page

_log = get_logger("learnnews.web")
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _section_of(source_type: str | None) -> str:
    """分區（spec 017）：論文＋基礎部落格＝基礎知識（常青吸引子）；其餘（含未知/web）＝新聞流。"""
    return "foundational" if source_type in ("paper", "blog") else "news"


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
    app = FastAPI(title="LearnNews")
    app.state.config = Config.from_env()
    app.state.cache = TTLCache()
    app.state.repo_factory = _default_repo_factory
    app.state.pull_service_factory = _default_pull_service_factory
    app.state.pull_stream_factory = lambda topic: _default_pull_stream(
        app.state.config, app.state.repo_factory, app.state.pull_service_factory, topic)
    app.state.rag_answer_factory = lambda question, today, lang: _default_rag_answer(
        app.state.config, app.state.repo_factory, question, today, lang)
    app.state.seed_ingest_factory = lambda ref, explainer: _default_seed_ingest(
        app.state.config, app.state.repo_factory, ref, explainer)

    def _default_subscribe(url):
        from ..sources.subscribe import subscribe
        return subscribe(url)
    app.state.subscribe_factory = _default_subscribe

    def _default_web_search(query):
        from ..backends.factory import make_web_search
        return make_web_search(app.state.config).search(query)
    app.state.web_search_factory = _default_web_search

    def _default_smart_search(query, explore=False):
        from ..backends.factory import make_smart_search
        return make_smart_search(app.state.config).run(query, explore)
    app.state.smart_search_factory = _default_smart_search

    @app.exception_handler(OpenAIError)
    async def _backend_error(request: Request, exc: OpenAIError):
        _log.error("web 後端失敗", extra={"extra": {"reason": str(exc)}})
        return _TEMPLATES.TemplateResponse(
            request=request, name="error.html", context={"reason": str(exc)},
            status_code=503)

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request, msg: str = ""):
        from ..trend.keywords import trend_keywords
        config = app.state.config
        repo = app.state.repo_factory(config)
        digest = repo.get_last_digest()
        # 趨勢讀數（spec 013）：從最近幾份真實匯整標題統計熱詞（純統計、不落庫）
        titles = repo.recent_digest_titles(config.trend_recent_digests)
        # 分區（spec 017）：依來源 type 把條目分「新聞流 / 基礎知識」兩區（concept 流 vs 吸引子）
        type_by_id = {s.id: s.type for s in repo.list_sources()}
        repo.close()
        chips = trend_keywords(titles, top_n=config.trend_top_n)
        news_entries, foundational_entries = [], []
        for e in (digest.entries if digest else []):
            sec = _section_of(type_by_id.get(e.item.source_id))
            (foundational_entries if sec == "foundational" else news_entries).append(
                entry_to_page(e))
        return _TEMPLATES.TemplateResponse(request=request, name="digest.html", context={
            "date": digest.date if digest else None,
            "news_entries": news_entries,
            "foundational_entries": foundational_entries,
            "missing_sources": digest.missing_sources if digest else [],
            "chips": chips,
            "refresh_fail": msg == "refresh_fail",   # 重整失敗提示（spec 014）
        })

    def _default_digest_refresh(config, repo):
        """重跑分診（spec 014）：啟用來源→run_digest→save_digest。複用 CLI 管線，不重寫。"""
        from ..cli.digest_cmd import build_backend_builder, run_digest
        from ..cli.fetchers import DEFAULT_SOURCES, build_adapters
        sources = repo.list_sources(enabled_only=True)
        if not sources:
            for s in DEFAULT_SOURCES:
                repo.upsert_source(s)
            sources = repo.list_sources(enabled_only=True)
        adapters = build_adapters(sources, config)   # 傳 config → 啟用的 web 活水源生效（spec 015）
        digest = run_digest(repo, adapters, date=_now_iso()[:10],
                            limit=config.digest_limit,
                            builder=build_backend_builder(config))
        repo.save_digest(digest)
    app.state.digest_refresh_factory = _default_digest_refresh

    @app.post("/digest/refresh")
    async def digest_refresh():
        config = app.state.config
        repo = app.state.repo_factory(config)
        try:
            # 使用者明確觸發（原則 5）；同步重跑分診（會抓＋消化，較慢）
            app.state.digest_refresh_factory(config, repo)
            return RedirectResponse("/", status_code=303)
        except (SourceUnavailable, OpenAIError) as e:   # 外部失敗 → 友善、非 500（教訓 3）
            _log.error("重新整理失敗", extra={"extra": {"reason": str(e)}})
            return RedirectResponse("/?msg=refresh_fail", status_code=303)
        except Exception as e:                          # noqa: BLE001 - 任何異常都友善、不吐堆疊
            _log.error("重新整理失敗", extra={"extra": {"reason": str(e)}})
            return RedirectResponse("/?msg=refresh_fail", status_code=303)
        finally:
            repo.close()

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

    @app.get("/library", response_class=HTMLResponse)
    async def library(request: Request):
        repo = app.state.repo_factory(app.state.config)
        seeds = repo.list_seeds()
        repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="library.html", context={"seeds": seeds})

    @app.post("/library/remove")
    async def library_remove(entry_id: int = Form(0)):
        if entry_id:
            repo = app.state.repo_factory(app.state.config)
            repo.delete_seed(entry_id)             # 僅種子容器；每日流不動作（FR-005）
            repo.close()
        return RedirectResponse("/library", status_code=303)

    @app.post("/library/reclassify")
    async def library_reclassify(entry_id: int = Form(0),
                                 source_class: str = Form("ordinary")):
        if entry_id:
            repo = app.state.repo_factory(app.state.config)
            repo.set_seed_class(entry_id, source_class)
            repo.close()
        return RedirectResponse("/library", status_code=303)

    # --- 根因萃取（spec 012／階段 10）---
    def _default_extractor():
        from ..backends.factory import make_root_cause_extractor
        return make_root_cause_extractor(app.state.config)
    app.state.extractor_factory = _default_extractor

    # 場對新材料做工（spec 018）：可注入的 relate（測試覆寫）
    def _default_field_relate(title, body, exclude_url=None):
        from ..backends.factory import make_embedder, make_relation_judge
        from ..field.relate import FieldRelate
        cfg = app.state.config
        repo = app.state.repo_factory(cfg)
        try:
            return FieldRelate(make_embedder(cfg), make_relation_judge(cfg),
                               repo, cfg.rag_min_score).relate(title, body, exclude_url)
        finally:
            repo.close()
    app.state.field_relate_factory = _default_field_relate

    @app.post("/field/relate")
    async def field_relate(request: Request, entry_id: int = Form(0)):
        repo = app.state.repo_factory(app.state.config)
        seed = next((s for s in repo.list_seeds() if s.entry_id == entry_id), None)
        repo.close()
        if seed is None:
            return RedirectResponse("/library", status_code=303)
        try:
            # 材料在你的場裡跑一次 forward pass；排除材料自己（原則 5：只提關係、不改場）
            rel = app.state.field_relate_factory(seed.headline or seed.title, seed.body,
                                                 exclude_url=seed.url)
        except (SourceUnavailable, OpenAIError) as e:   # 判關係失敗 → 友善（教訓 3）
            _log.error("關聯到場失敗", extra={"extra": {"reason": str(e)}})
            rel = None
        return _TEMPLATES.TemplateResponse(
            request=request, name="field_relate.html",
            context={"material": {"title": seed.headline or seed.title, "url": seed.url},
                     "rel": rel})

    @app.get("/roots", response_class=HTMLResponse)
    async def roots(request: Request, msg: str = ""):
        repo = app.state.repo_factory(app.state.config)
        candidates = repo.list_why_nodes("candidate")
        anointed = repo.list_why_nodes("anointed")
        repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="roots.html",
            context={"candidates": candidates, "anointed": anointed, "msg": msg})

    @app.post("/whynode/extract")
    async def whynode_extract(entry_id: int = Form(0)):
        if not entry_id:
            return RedirectResponse("/library", status_code=303)
        repo = app.state.repo_factory(app.state.config)
        try:
            seed = next((s for s in repo.list_seeds() if s.entry_id == entry_id), None)
            if seed is None:
                repo.close()
                return RedirectResponse("/library", status_code=303)
            cand = app.state.extractor_factory().extract(seed.title, seed.body)
            if cand.no_material:                       # 抽不出有把握的根因 → 不建候選（不杜撰）
                repo.close()
                return RedirectResponse("/roots?msg=nomat", status_code=303)
            # grounding 落結構：候選必帶證據（種子 url）＋試金石，才可冊封（教訓 7）
            from ..config import SEEDS_DATE  # noqa: F401
            repo.add_why_node(cand.claim, [seed.url], cand.touchstones,
                              cand.fog_flag, entry_id, _now_iso(), ladder=cand.ladder)
            repo.close()
            return RedirectResponse("/roots", status_code=303)
        except SourceUnavailable as e:                 # 萃取失敗/逾時/無金鑰 → 友善繁中（教訓 3）
            repo.close()
            _log.error("根因萃取失敗", extra={"extra": {"reason": str(e)}})
            return RedirectResponse("/roots?msg=fail", status_code=303)

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

    @app.get("/sources", response_class=HTMLResponse)
    async def sources_get(request: Request):
        repo = app.state.repo_factory(app.state.config)
        srcs = repo.list_sources()
        repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="sources.html", context={"sources": srcs})

    @app.post("/sources/add", response_class=HTMLResponse)
    async def sources_add(request: Request, url: str = Form("")):
        from ..sources.base import SourceUnavailable
        url = url.strip()
        msg = err = None
        repo = app.state.repo_factory(app.state.config)
        if url:
            try:
                src = app.state.subscribe_factory(url)      # 探測＋驗證有料才回 Source
                if any(s.id == src.id for s in repo.list_sources()):
                    msg = f"已在追蹤：{src.name}"
                else:
                    repo.upsert_source(src)                 # 驗證過才落庫（不加壞來源）
                    msg = f"已加入來源：{src.name}"
            except SourceUnavailable as e:
                _log.error("web 加來源失敗", extra={"extra": {"reason": str(e)}})
                err = str(e)
        srcs = repo.list_sources()
        repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="sources.html",
            context={"sources": srcs, "msg": msg, "err": err})

    @app.post("/sources/toggle")
    async def sources_toggle(source_id: str = Form(""), enabled: str = Form("1")):
        if source_id:
            repo = app.state.repo_factory(app.state.config)
            repo.set_source_enabled(source_id, enabled == "1")
            repo.close()
        return RedirectResponse("/sources", status_code=303)

    @app.post("/sources/remove")
    async def sources_remove(source_id: str = Form("")):
        if source_id:
            repo = app.state.repo_factory(app.state.config)
            repo.delete_source(source_id)
            repo.close()
        return RedirectResponse("/sources", status_code=303)

    @app.get("/search", response_class=HTMLResponse)
    async def search_get(request: Request, q: str = "", explore: str = ""):
        q = q.strip()
        explore_on = bool(explore)                           # opt-in（spec 011）；預設關
        result = err = None
        if q:
            try:
                # 智慧搜尋：搜尋→排序→抓 top-N→grounded 整理（即算即棄、不落庫，FR-006）。
                # explore=True 時先多角度 fan-out＋合併去重（spec 011）。
                result = app.state.smart_search_factory(q, explore_on)
            except SourceUnavailable as e:                   # 搜尋層：未設金鑰/逾時/服務錯誤
                _log.error("web 搜尋失敗", extra={"extra": {"reason": str(e)}})
                err = str(e)
            except Exception as e:                           # noqa: BLE001 - 整理服務整體異常，友善不噴堆疊
                _log.error("智慧搜尋失敗", extra={"extra": {"reason": str(e)}})
                err = "整理服務暫時無法使用，請稍後再試。"
        return _TEMPLATES.TemplateResponse(
            request=request, name="search.html",
            context={"q": q, "result": result, "err": err, "explore": explore_on})

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
