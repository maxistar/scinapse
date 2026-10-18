"""CLI: ``scinapse build`` / ``scinapse check``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import checker
from .config import DEFAULT_CHAT_MODEL, BuildConfig, load_dotenv


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scinapse",
                                     description="Research-paper discovery graph generator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build a graph document from seed DOIs")
    b.add_argument("--seed", action="append", required=True,
                   help="seed DOI (repeatable)")
    b.add_argument("--question", required=True, help="research question")
    b.add_argument("--out", default="graph.json", help="output path (default graph.json)")
    b.add_argument("--layers", type=int, default=3)
    b.add_argument("--top-k", type=int, default=8)
    b.add_argument("--top-entry-n", type=int, default=6)
    b.add_argument("--recent-min-year", type=int, default=2025)
    b.add_argument("--cache-dir", default=None)
    b.add_argument("--chat-model", default=DEFAULT_CHAT_MODEL)
    b.add_argument("--embed-model", default="", help="Token Factory embedding model ('' = TF-IDF)")
    b.add_argument("--no-llm", action="store_true", help="skip Token Factory assessments")
    b.add_argument("--smoke", action="store_true", help="tiny cheap profile (1 layer, small caps)")
    b.add_argument("--strict", action="store_true", help="exit 1 if the checker reports errors")

    c = sub.add_parser("check", help="validate a graph document against the contract")
    c.add_argument("path", help="document to check")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _build_parser().parse_args(argv)

    if args.cmd == "check":
        doc = json.loads(Path(args.path).read_text(encoding="utf-8"))
        errors = checker.check(doc)
        if errors:
            print(f"{len(errors)} problem(s) in {args.path}:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print(f"{args.path}: OK "
              f"({len(doc.get('nodes') or [])} nodes, {len(doc.get('edges') or [])} edges)")
        return 0

    # build
    from .pipeline import run  # deferred: keeps `scinapse check` import-light

    overrides = {}
    if args.cache_dir:
        overrides["cache_dir"] = Path(args.cache_dir)
    cfg = BuildConfig(
        seeds=tuple(args.seed),
        question=args.question,
        layers=args.layers,
        top_k_per_layer=args.top_k,
        top_entry_n=args.top_entry_n,
        recent_min_year=args.recent_min_year,
        chat_model=args.chat_model,
        embed_model=args.embed_model,
        **overrides,
    )
    if args.smoke:
        cfg = cfg.smoke()
    doc = run(cfg, no_llm=args.no_llm)

    errors = checker.check(doc)
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out} ({len(doc['nodes'])} nodes / {len(doc['edges'])} edges)")
    if errors:
        print(f"checker: {len(errors)} problem(s):", file=sys.stderr)
        for e in errors[:20]:
            print(f"  - {e}", file=sys.stderr)
        if args.strict:
            return 1
    else:
        print("checker: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
