# Citadel

Citadel is a thin self-hosted knowledge-base wrapper built on top of
[Cognee](https://github.com/topoteretes/cognee), which is Apache-2.0 licensed.

This repository does not vendor Cognee. It imports Cognee as a dependency so the
upstream package can be upgraded independently.

## What This Adds

- Pre-ingest filtering for empty, tiny, ignored, or duplicate inputs.
- Tag normalization and metadata helpers before content reaches Cognee.
- A small service layer around Cognee's public async API.
- Feedback helpers that write to Cognee session feedback and can trigger
  `cognee.improve()`.
- A simple `citadel` CLI for solo use today, with tenant/team config already
  represented through environment variables.

## Install

```bash
uv sync --dev
```

Copy `.env.example` to `.env` and fill in your providers and database settings.

## CLI

```bash
uv run citadel ingest "A useful note" --tag personal --tag research
uv run citadel ingest ./notes.md --dataset personal
uv run citadel search "What did I learn about Railway?"
uv run citadel feedback <qa-id> --score 1 --text "Useful answer"
uv run citadel improve
```

## Python API

```python
import asyncio
from kb import Citadel


async def main() -> None:
    kb = Citadel.from_env()
    await kb.ingest("Citadel keeps my knowledge base organized.", tags=["personal"])
    results = await kb.search("What does Citadel do?")
    print(results)


asyncio.run(main())
```

## Multi-Tenant Shape

Start solo with:

```bash
CITADEL_TENANT_ID=personal
CITADEL_DEFAULT_DATASET=personal
```

When adding teammates later, keep the same wrapper and change tenant/user
configuration at deployment or request boundaries. The service layer accepts
dataset, session, and tenant-aware configuration without changing Cognee internals.

## Railway Notes

For Railway, provision Postgres and configure Cognee through environment
variables. Typical settings live in `.env.example`; exact Cognee provider
variables are passed through untouched.

## Attribution

Citadel builds on Cognee and preserves upstream attribution. Cognee is developed
by Topoteretes UG and is licensed under Apache-2.0.
