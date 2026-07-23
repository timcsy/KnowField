"""learnnews CLI 入口（argparse）。"""

from __future__ import annotations

import argparse
import sys

from . import digest_cmd, interests_cmd, sources_cmd


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="learnnews", description="AI 新聞/論文每日分診工具")
    p.add_argument("--db", default="learnnews.db", help="SQLite 資料庫路徑")
    p.add_argument("--json", action="store_true", help="以 JSON 輸出")
    sub = p.add_subparsers(dest="command", required=True)

    # digest
    d = sub.add_parser("digest", help="產出當日匯整")
    d.add_argument("--date", default=None)
    d.add_argument("--limit", type=int, default=15)
    d.add_argument("--format", choices=["terminal", "markdown"], default="terminal")
    d.add_argument("--output", default=None)
    d.set_defaults(func=digest_cmd.handle)

    # interests
    i = sub.add_parser("interests", help="管理興趣清單")
    isub = i.add_subparsers(dest="interests_action", required=True)
    isub.add_parser("list")
    ia = isub.add_parser("add")
    ia.add_argument("topic")
    ir = isub.add_parser("remove")
    ir.add_argument("topic")
    iset = isub.add_parser("set")
    iset.add_argument("topics", nargs="+")
    i.set_defaults(func=interests_cmd.handle)

    # sources
    s = sub.add_parser("sources", help="檢視/啟用來源")
    ssub = s.add_subparsers(dest="sources_action", required=True)
    ssub.add_parser("list")
    se = ssub.add_parser("enable")
    se.add_argument("source_id")
    sd = ssub.add_parser("disable")
    sd.add_argument("source_id")
    s.set_defaults(func=sources_cmd.handle)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
