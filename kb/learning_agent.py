from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from kb.github_sync import GitHubOrgSyncer
from kb.service import Citadel


class LearningAgent:
    """Runs source-learning jobs that teach Citadel and refresh Cognee indexes."""

    def __init__(
        self,
        citadel: Citadel,
        *,
        github_syncer: GitHubOrgSyncer | None = None,
    ) -> None:
        self.citadel = citadel
        self.github_syncer = github_syncer or GitHubOrgSyncer(citadel)

    @classmethod
    def from_env(cls) -> "LearningAgent":
        return cls(Citadel.from_env())

    async def status(self) -> dict[str, Any]:
        github_status = await self.github_syncer.status()
        return {
            "ok": True,
            "agent": "citadel-learning-agent",
            "mode": "github-source-learning",
            "sources": {
                "github": github_status,
            },
            "capabilities": [
                "scan_github_repositories",
                "summarize_github_events",
                "summarize_recent_commits",
                "ingest_source_digest",
                "run_cognee_improvement",
            ],
        }

    async def run(self, *, force: bool = False, dry_run: bool = False) -> dict[str, Any]:
        github_result = await self.github_syncer.run(force=force, dry_run=dry_run)
        return {
            "ok": True,
            "agent": "citadel-learning-agent",
            "sources": {
                "github": github_result,
            },
            "ingested": github_result.get("ingested", False),
            "improved": github_result.get("improved", False),
            "dry_run": dry_run,
        }


async def _run_agent(args: argparse.Namespace) -> None:
    agent = LearningAgent.from_env()
    if args.status:
        result = await agent.status()
    else:
        result = await agent.run(force=args.force, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m kb.learning_agent")
    parser.add_argument("--status", action="store_true", help="Print source-learning status")
    parser.add_argument("--force", action="store_true", help="Treat fetched source activity as new")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print without ingesting")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(_run_agent(args))


if __name__ == "__main__":
    main()
