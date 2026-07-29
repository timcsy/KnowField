"""FastAPI web app（階段 6）。唯一 import 框架之處；核心全複用、零改動。

頁面：/（今日匯整）、/pull（即時拉＋快取）、/interests（增刪）。
後端失敗經例外處理器攔成友善繁中頁（FR-009、experience 教訓 3）。
可覆寫點（app.state）供測試注入：repo_factory、pull_service_factory、cache。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request
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

    # 場驅動來源推薦（spec 020）：可注入的撒網＋驗證＋場驅動排序（測試覆寫）
    def _default_recommend():
        from ..backends.factory import make_embedder, make_web_search
        from ..sources.recommend import recommend_sources
        cfg = app.state.config
        repo = app.state.repo_factory(cfg)
        try:
            return recommend_sources(
                make_web_search(cfg), make_embedder(cfg), repo,
                queries=list(cfg.source_recommend_queries),
                limit=cfg.source_recommend_limit)
        finally:
            repo.close()
    app.state.recommend_factory = _default_recommend

    def _default_web_search(query):
        from ..backends.factory import make_web_search
        return make_web_search(app.state.config).search(query)
    app.state.web_search_factory = _default_web_search

    def _default_smart_search(query, explore=False):
        from ..backends.factory import make_smart_search
        return make_smart_search(app.state.config).run(query, explore)
    app.state.smart_search_factory = _default_smart_search

    # 反逢迎「值不值得」副手（spec 021）：可注入撒網獵心得＋反逢迎綜合（測試覆寫）
    def _default_worth(subject):
        from ..backends.factory import make_web_search, make_worthit_synthesizer
        from ..search.worthit import assess_worth
        cfg = app.state.config
        return assess_worth(make_web_search(cfg), make_worthit_synthesizer(cfg), subject)
    app.state.worth_factory = _default_worth

    def _default_worth_fetch_title(url):
        from ..seed.fetch import fetch_url
        return fetch_url(url).title
    app.state.worth_fetch_title = _default_worth_fetch_title

    # 跟你的場聊天（spec 022）：可注入的多輪對話／蒸餾／佐證（測試覆寫）
    def _chat_backend():
        from ..backends.factory import make_chat_backend
        return getattr(app.state, "chat_backend_for_test", None) or make_chat_backend(app.state.config)

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
            sources = _chat_search(q)
        text = fc.reply(history, message, roots, sources, brainstorm=brainstorm,
                        max_history=app.state.config.chat_context_messages,
                        url_contents=url_contents)
        # 只顯示回答真的引用到的來源（[n]）——沒被引用的（多半不相關）一律不列，濾掉垃圾
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
        numbered = [{"n": i, "url": s.url, "title": s.title or s.url}
                    for i, s in enumerate(sources, 1) if i in cited]
        return text, numbered
    app.state.chat_factory = _default_chat

    def _default_distill(history):
        from ..chat.field_chat import FieldChat
        return FieldChat(_chat_backend()).distill(history, [])
    app.state.distill_factory = _default_distill

    def _default_title(messages):
        from ..chat.field_chat import FieldChat
        return FieldChat(_chat_backend()).title(messages)
    app.state.title_factory = _default_title

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
        # spec 019：以 digest_entries.id 取任一條目材料（種子或每日流皆可），不再只找種子
        material = repo.get_entry_material(entry_id)
        repo.close()
        if material is None:
            return RedirectResponse("/", status_code=303)
        title, body, url = material
        try:
            # 材料在你的場裡跑一次 forward pass；排除材料自己（原則 5：只提關係、不改場）
            rel = app.state.field_relate_factory(title, body, exclude_url=url)
        except (SourceUnavailable, OpenAIError) as e:   # 判關係失敗 → 友善（教訓 3）
            _log.error("關聯到場失敗", extra={"extra": {"reason": str(e)}})
            rel = None
        return _TEMPLATES.TemplateResponse(
            request=request, name="field_relate.html",
            context={"material": {"title": title, "url": url}, "rel": rel})

    @app.get("/roots", response_class=HTMLResponse)
    async def roots(request: Request, msg: str = ""):
        repo = app.state.repo_factory(app.state.config)
        candidates = repo.list_why_nodes("candidate")
        anointed = repo.list_why_nodes("anointed")
        provenance = repo.why_node_provenance()     # {why_node_id: conversation_id}（spec 023 由來連結）
        repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="roots.html",
            context={"candidates": candidates, "anointed": anointed, "msg": msg,
                     "provenance": provenance})

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

    @app.get("/worth", response_class=HTMLResponse)
    async def worth_get(request: Request):
        return _TEMPLATES.TemplateResponse(request=request, name="worth.html", context={})

    @app.post("/worth", response_class=HTMLResponse)
    async def worth_post(request: Request, subject: str = Form(""),
                         content: str = Form(""), url: str = Form("")):
        """時刻 A：丟名字/內文/網址 → 撒網獵心得 → 反逢迎綜合（原則 5：不落庫、opt-in）。"""
        # subject 解析序：名字 ＞ 內文首行 ＞ url 抓到的標題（best-effort）＞ url 本身（收內容口，FR-002/007）
        subj = (subject or "").strip()
        if not subj and content.strip():
            subj = content.strip().splitlines()[0].strip()[:80]
        if not subj and url.strip():
            try:
                subj = (app.state.worth_fetch_title(url.strip()) or "").strip()[:80]
            except Exception as e:   # 伺服器抓被擋/牆內→退回用 url，不崩（教訓 3）
                _log.error("值不值得抓標題失敗", extra={"extra": {"reason": str(e)}})
                subj = ""
            if not subj:
                subj = url.strip()
        if not subj:
            return _TEMPLATES.TemplateResponse(
                request=request, name="worth.html",
                context={"err": "請貼一個名字、一段內文，或一個網址。"})
        verdict = err = None
        try:
            verdict = app.state.worth_factory(subj)
        except (SourceUnavailable, OpenAIError) as e:   # 搜尋/綜合失敗→友善（教訓 3）
            _log.error("值不值得綜合失敗", extra={"extra": {"reason": str(e)}})
            err = str(e)
        return _TEMPLATES.TemplateResponse(
            request=request, name="worth.html",
            context={"verdict": verdict, "err": err, "subject": subj})

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
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": [], "history_json": "[]", "root_count": _root_count()})

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

    @app.post("/chat/stream")
    async def chat_stream(history: str = Form("[]"), message: str = Form(""),
                          brainstorm: str = Form("")):
        """串流版對話：分段進度（找關鍵字→撒網→回答中）＋逐 token 串流；只列被引用來源。"""
        from ..chat.field_chat import FieldChat
        hist = _parse_history(history)
        message = (message or "").strip()
        bs = brainstorm == "1"
        cfg = app.state.config

        def gen():
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
                    sources = _chat_search(q)
                yield _sse({"type": "stage", "text": "回答中…"})
                full = ""
                for delta in fc.reply_stream(hist, message, roots, sources, brainstorm=bs,
                                             max_history=cfg.chat_context_messages,
                                             url_contents=url_contents):
                    full += delta
                    yield _sse({"type": "token", "text": delta})
                cited = {int(n) for n in re.findall(r"\[(\d+)\]", full)}
                numbered = [{"n": i, "url": s.url, "title": s.title or s.url}
                            for i, s in enumerate(sources, 1) if i in cited]
                yield _sse({"type": "done", "text": full, "sources": numbered})
            except (SourceUnavailable, OpenAIError) as e:
                _log.error("場對話串流失敗", extra={"extra": {"reason": str(e)}})
                yield _sse({"type": "error", "text": str(e)})

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/chat/branch", response_class=HTMLResponse)
    async def chat_branch(request: Request, history: str = Form("[]"), draft: str = Form("")):
        """從某句開新分支：另開一頁、載入 history 前綴＋把那句放回輸入框（原對話那頁不動）。"""
        hist = _parse_history(history)
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": hist, "history_json": json.dumps(hist, ensure_ascii=False),
                     "draft": draft, "root_count": _root_count()})

    @app.post("/chat/distill", response_class=HTMLResponse)
    async def chat_distill(request: Request, history: str = Form("[]")):
        hist = _parse_history(history)
        cands = err = None
        try:
            cands = app.state.distill_factory(hist)      # 一到多條（可能不同層次）
        except (SourceUnavailable, OpenAIError) as e:
            _log.error("蒸餾候選失敗", extra={"extra": {"reason": str(e)}})
            err = str(e)
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": hist, "history_json": json.dumps(hist, ensure_ascii=False),
                     "candidates": cands, "err": err, "root_count": _root_count()})

    @app.post("/chat/anoint", response_class=HTMLResponse)
    async def chat_anoint(request: Request, claim: str = Form(""),
                          ladder: str = Form(""), evidence_urls: str = Form(""),
                          save_convo: str = Form(""), history: str = Form("[]")):
        """人閘門：唯有此路由（人按）寫 bedrock（原則 5）。save_convo=1 連同存這段對話成由來（spec 023）。"""
        claim = (claim or "").strip()
        msg = None
        if claim:
            steps = [s.strip() for s in ladder.splitlines() if s.strip()]
            urls = [u.strip() for u in evidence_urls.replace("，", ",").replace("\n", ",").split(",")
                    if u.strip().startswith("http")]
            repo = app.state.repo_factory(app.state.config)
            wid = repo.add_why_node(claim, urls, [], False, 0, _now_iso(), ladder=steps)
            repo.anoint_why_node(wid)
            msg = f"已存進你的知識庫：「{claim[:40]}」（可到『根因』頁檢視或刪除）"
            if save_convo == "1":               # 連同這段對話存成由來（連到剛冊封的根因）
                messages = _parse_history(history)
                if messages:
                    repo.save_conversation(_convo_title(messages), messages, wid)
                    msg += "，並存下這段對話當它的由來"
            repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": [], "history_json": "[]", "anoint_msg": msg,
                     "root_count": _root_count()})

    @app.post("/chat/save", response_class=HTMLResponse)
    async def chat_save(request: Request, history: str = Form("[]")):
        """獨立存這段對話（spec 023，人閘門、原則 5）。空對話→友善不存。"""
        messages = _parse_history(history)
        saved_msg = None
        if messages:
            repo = app.state.repo_factory(app.state.config)
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
        convs = repo.list_conversations()
        repo.close()
        return _TEMPLATES.TemplateResponse(
            request=request, name="conversations.html",
            context={"conversations": convs,
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
        rc = len(repo.list_why_nodes("anointed"))
        repo.close()
        if conv is None:
            return RedirectResponse("/conversations", status_code=303)
        return _TEMPLATES.TemplateResponse(
            request=request, name="chat.html",
            context={"messages": conv.messages,
                     "history_json": json.dumps(conv.messages, ensure_ascii=False),
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
    async def conversation_export(cid: int, as_: str = Query("md", alias="as")):
        repo = app.state.repo_factory(app.state.config)
        conv = repo.get_conversation(cid)
        repo.close()
        if conv is None:
            return PlainTextResponse("找不到這段對話。", status_code=404)
        return PlainTextResponse(_export_conversation(conv.title, conv.messages, as_))

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

    @app.post("/sources/recommend", response_class=HTMLResponse)
    async def sources_recommend(request: Request):
        """opt-in 撒網找新來源（原則 5：人按才跑、訂閱才進名冊）。"""
        repo = app.state.repo_factory(app.state.config)
        srcs = repo.list_sources()
        repo.close()
        recs = []
        rec_msg = rec_err = None
        try:
            recs = app.state.recommend_factory()
            if not recs:
                rec_msg = "這次沒找到可訂的新來源——過一陣子再試，或直接貼網址追蹤。"
        except (SourceUnavailable, OpenAIError) as e:   # 搜尋/抓 feed 失敗 → 友善（教訓 3）
            _log.error("找新來源失敗", extra={"extra": {"reason": str(e)}})
            rec_err = str(e)
        return _TEMPLATES.TemplateResponse(
            request=request, name="sources.html",
            context={"sources": srcs, "recommendations": recs,
                     "rec_msg": rec_msg, "rec_err": rec_err})

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
