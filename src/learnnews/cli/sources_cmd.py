"""`learnnews sources` 指令（維運）。"""

from __future__ import annotations

import json

from ..store.repository import Repository
from .fetchers import DEFAULT_SOURCES


def handle(args) -> int:
    repo = Repository(args.db)
    if not repo.list_sources():
        for s in DEFAULT_SOURCES:
            repo.upsert_source(s)

    action = args.sources_action
    if action == "enable":
        repo.set_source_enabled(args.source_id, True)
    elif action == "disable":
        repo.set_source_enabled(args.source_id, False)

    sources = repo.list_sources()
    if args.json:
        print(json.dumps([
            {"id": s.id, "name": s.name, "type": s.type,
             "enabled": s.enabled, "last_status": s.last_status}
            for s in sources
        ], ensure_ascii=False))
    else:
        print("來源清單：")
        for s in sources:
            state = "啟用" if s.enabled else "停用"
            print(f"  [{state}] {s.id} — {s.name}（{s.type}）")
    repo.close()
    return 0
