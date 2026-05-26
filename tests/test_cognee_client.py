from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from kb.cognee_client import CogneePublicClient


@pytest.mark.asyncio
async def test_cognee_public_client_runs_startup_migrations_once(monkeypatch: Any) -> None:
    calls: list[str] = []

    async def run_startup_migrations() -> None:
        calls.append("migrate")

    async def remember(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"ok": True}

    async def recall(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"ok": True}]

    monkeypatch.setitem(
        sys.modules,
        "cognee",
        SimpleNamespace(
            run_startup_migrations=run_startup_migrations,
            remember=remember,
            recall=recall,
        ),
    )
    client = CogneePublicClient()

    await client.remember("note", dataset_name="notes")
    await client.recall("note", dataset="notes")

    assert calls == ["migrate"]


@pytest.mark.asyncio
async def test_cognee_public_client_creates_database_and_retries_migrations(
    monkeypatch: Any,
) -> None:
    calls: list[str] = []

    async def run_startup_migrations() -> None:
        calls.append("migrate")
        if calls == ["migrate"]:
            raise RuntimeError("missing enum")

    async def remember(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"ok": True}

    monkeypatch.setitem(
        sys.modules,
        "cognee",
        SimpleNamespace(
            run_startup_migrations=run_startup_migrations,
            remember=remember,
        ),
    )
    client = CogneePublicClient()

    async def create_database() -> None:
        calls.append("create")

    monkeypatch.setattr(client, "_create_cognee_database", create_database)

    await client.remember("note", dataset_name="notes")

    assert calls == ["migrate", "create", "migrate"]


@pytest.mark.asyncio
async def test_cognee_public_client_does_not_pass_external_metadata_keyword(
    monkeypatch: Any,
) -> None:
    received: dict[str, Any] = {}

    async def run_startup_migrations() -> None:
        return None

    async def remember(*args: Any, **kwargs: Any) -> dict[str, Any]:
        received["args"] = args
        received["kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setitem(
        sys.modules,
        "cognee",
        SimpleNamespace(
            run_startup_migrations=run_startup_migrations,
            remember=remember,
        ),
    )
    client = CogneePublicClient()

    await client.remember("note", dataset_name="notes", tags=("github", "daily-sync"))

    assert received["kwargs"] == {
        "dataset_name": "notes",
        "session_id": None,
    }
