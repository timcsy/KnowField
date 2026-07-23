"""`learnnews interests` 指令（US2）。"""

from __future__ import annotations

import json

from ..interests.service import InterestService
from ..store.repository import Repository


def _emit(topics: list[str], as_json: bool) -> None:
    if as_json:
        print(json.dumps({"explicit_topics": topics}, ensure_ascii=False))
    else:
        if topics:
            print("目前的興趣主題：")
            for t in topics:
                print(f"  • {t}")
        else:
            print("（尚未設定任何興趣主題，將採用預設清單。）")


def handle(args) -> int:
    repo = Repository(args.db)
    svc = InterestService(repo)
    action = args.interests_action
    if action == "list":
        topics = svc.list_topics()
    elif action == "add":
        topics = svc.add(args.topic)
    elif action == "remove":
        topics = svc.remove(args.topic)
    elif action == "set":
        topics = svc.set(args.topics)
    else:
        print("未知的子指令")
        repo.close()
        return 2
    _emit(topics, args.json)
    repo.close()
    return 0
