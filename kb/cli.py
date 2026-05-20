from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from kb.models import FeedbackRequest
from kb.service import Citadel


def _print_json(value: Any) -> None:
    print(json.dumps(value, default=str, indent=2))


async def _ingest(args: argparse.Namespace) -> None:
    kb = Citadel.from_env()
    result = await kb.ingest(
        args.data,
        dataset=args.dataset,
        tags=args.tag,
        session_id=args.session,
    )
    _print_json(result.__dict__)


async def _search(args: argparse.Namespace) -> None:
    kb = Citadel.from_env()
    results = await kb.search(
        args.query,
        dataset=args.dataset,
        session_id=args.session,
        top_k=args.top_k,
    )
    _print_json(results)


async def _feedback(args: argparse.Namespace) -> None:
    kb = Citadel.from_env()
    result = await kb.feedback(
        FeedbackRequest(
            qa_id=args.qa_id,
            score=args.score,
            text=args.text,
            session_id=args.session,
            dataset=args.dataset,
        )
    )
    _print_json(result.__dict__)


async def _improve(args: argparse.Namespace) -> None:
    kb = Citadel.from_env()
    result = await kb.improve(dataset=args.dataset, session_ids=args.session_id)
    _print_json(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="citadel")
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest = subcommands.add_parser("ingest", help="Ingest text or a path through Cognee")
    ingest.add_argument("data")
    ingest.add_argument("--dataset")
    ingest.add_argument("--session")
    ingest.add_argument("--tag", action="append", default=[])
    ingest.set_defaults(handler=_ingest)

    search = subcommands.add_parser("search", help="Search the knowledge base")
    search.add_argument("query")
    search.add_argument("--dataset")
    search.add_argument("--session")
    search.add_argument("--top-k", type=int, default=10)
    search.set_defaults(handler=_search)

    feedback = subcommands.add_parser("feedback", help="Attach feedback to a Cognee QA entry")
    feedback.add_argument("qa_id")
    feedback.add_argument("--score", type=int, choices=[-1, 0, 1])
    feedback.add_argument("--text")
    feedback.add_argument("--dataset")
    feedback.add_argument("--session")
    feedback.set_defaults(handler=_feedback)

    improve = subcommands.add_parser("improve", help="Run Cognee improvement")
    improve.add_argument("--dataset")
    improve.add_argument("--session-id", action="append")
    improve.set_defaults(handler=_improve)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(args.handler(args))


if __name__ == "__main__":
    main()
