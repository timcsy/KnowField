"""`knowfield ask` 指令（spec 005）：對已落庫知識庫做可溯源 RAG 問答。

核心 `RagService` 與 CLI 解耦；此處只負責組後端、印答案＋來源、攔後端失敗（教訓 3）。
"""

from __future__ import annotations

from ..backends.factory import make_answerer, make_embedder
from ..backends.openai_api import OpenAIError
from ..config import Config
from ..logging_setup import get_logger
from ..rag.service import RagService
from ..rag.types import Scope
from ..store.repository import Repository

_log = get_logger("knowfield.cli")


def handle(args) -> int:
    config = Config.from_env()
    lang = getattr(args, "lang", None) or config.article_lang
    repo = Repository(args.db)
    service = RagService(
        repo=repo,
        embedder=make_embedder(config),
        answerer=make_answerer(config),
        top_k=getattr(args, "k", None) or config.rag_top_k,
        min_score=config.rag_min_score,
        explainer_weight=config.rag_explainer_weight,
        root_weight=config.rag_root_weight,
    )
    try:
        ans = service.answer(
            args.question, Scope(today=getattr(args, "today", False)), lang=lang
        )
    except OpenAIError as e:
        _log.error("後端失敗", extra={"extra": {"reason": str(e)}})
        print(f"❌ 真實後端（OpenAI 格式 API）失敗：{e}\n"
              f"　可稍後重試，或設 KNOWFIELD_BACKEND=offline 用離線後端。")
        repo.close()
        return 1

    if ans.no_material:
        print("沒有相關材料。（庫中找不到與問題相關的內容；若尚未產生匯整，請先執行 digest。）")
        repo.close()
        return 0

    print(ans.text)
    print("\n來源：")
    for s in ans.sources:
        print(f"[{s.n}] {s.title} — {s.url}")
    repo.close()
    return 0
