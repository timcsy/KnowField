"""learnnews CLI 入口（argparse）。"""

from __future__ import annotations

import argparse
import sys

from . import ask_cmd, digest_cmd, ingest_cmd, interests_cmd, pull_cmd, sources_cmd


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="learnnews", description="AI 新聞/論文每日分診工具")
    p.add_argument("--db", default="learnnews.db", help="SQLite 資料庫路徑")
    p.add_argument("--json", action="store_true", help="以 JSON 輸出")
    sub = p.add_subparsers(dest="command", required=True)

    # digest
    d = sub.add_parser("digest", help="產出當日匯整（推：分診＋散文消化）")
    d.add_argument("--date", default=None)
    d.add_argument("--limit", type=int, default=15)
    d.add_argument("--format", choices=["terminal", "markdown"], default="terminal")
    d.add_argument("--output", default=None)
    d.add_argument("--raw", "--no-summary", dest="raw", action="store_true",
                   help="純原礦：僅標題＋來源＋連結，不生成散文或圖")
    d.add_argument("--ai-image", dest="ai_image", action="store_true",
                   help="無原文圖時允許 AI 示意圖（必標示）")
    d.add_argument("--lang", default=None, help="消化散文的語言（預設繁體中文）")
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

    # pull
    pl = sub.add_parser("pull", help="對主題擴展、去重、溯源（拉模式）")
    pl.add_argument("topic", nargs="?", default=None, help="要深挖的主題")
    pl.add_argument("--limit", type=int, default=30)
    pl.add_argument("--raw", "--no-summary", dest="raw", action="store_true",
                    help="純原礦：僅標題＋來源＋連結，不生成任何文字")
    pl.add_argument("--from-digest", dest="from_digest", type=int, default=None,
                    help="以最近匯整第 N 則的主題發起拉取")
    pl.add_argument("--ai-image", dest="ai_image", action="store_true",
                    help="無原文圖時允許 AI 示意圖（必標示）")
    pl.add_argument("--lang", default=None, help="消化散文的語言（預設繁體中文）")
    pl.add_argument("--format", choices=["terminal", "markdown"], default="terminal")
    pl.add_argument("--output", default=None)
    pl.set_defaults(func=pull_cmd.handle)

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
