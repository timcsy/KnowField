"""knowfield CLI 入口（argparse）。"""

from __future__ import annotations

import argparse
import sys

from . import ask_cmd, ingest_cmd


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="knowfield", description="AI 知識庫問答／收進工具")
    import os
    p.add_argument("--db", default=os.environ.get("KNOWFIELD_DATABASE_URL"),
                   help="Postgres 連線 DSN（postgresql://…）；預設讀 env KNOWFIELD_DATABASE_URL")
    p.add_argument("--json", action="store_true", help="以 JSON 輸出")
    sub = p.add_subparsers(dest="command", required=True)

    # ask（RAG 問答，spec 005）
    a = sub.add_parser("ask", help="對已落庫知識庫問答（RAG，可溯源）")
    a.add_argument("question", help="一句自然語言問題")
    a.add_argument("--today", action="store_true", help="只查最近一份匯整（預設跨累積）")
    a.add_argument("--lang", default=None, help="答案語言（預設繁體中文）")
    a.add_argument("-k", type=int, default=None, help="取回條目數上限")
    a.set_defaults(func=ask_cmd.handle)

    # ingest（種子 spec 006）
    ing = sub.add_parser("ingest", help="把一篇經典/解說文收進知識庫（種子，深度吸引子）")
    ing.add_argument("ref", help="arXiv ID 或文章 URL")
    ing.add_argument("--explainer", action="store_true", help="標為解說文（檢索權重加成）")
    ing.add_argument("--lang", default=None, help="消化語言（預設繁體中文）")
    ing.set_defaults(func=ingest_cmd.handle)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
