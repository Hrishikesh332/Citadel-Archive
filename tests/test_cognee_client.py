from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from kb.cognee_client import CogneePublicClient


COGNEE_ENV_KEYS = (
    "DB_PROVIDER",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USERNAME",
    "DB_PASSWORD",
    "VECTOR_DB_HOST",
    "VECTOR_DB_PORT",
    "VECTOR_DB_NAME",
    "VECTOR_DB_USERNAME",
    "VECTOR_DB_PASSWORD",
    "GRAPH_DATABASE_HOST",
    "GRAPH_DATABASE_PORT",
    "GRAPH_DATABASE_NAME",
    "GRAPH_DATABASE_USERNAME",
    "GRAPH_DATABASE_PASSWORD",
)


@pytest.fixture(autouse=True)
def clean_derived_cognee_env(monkeypatch: Any) -> None:
    for key in COGNEE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


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


@pytest.mark.asyncio
async def test_cognee_public_client_wraps_data_item_metadata(monkeypatch: Any) -> None:
    received: dict[str, Any] = {}

    class DataItem:
        def __init__(
            self,
            data: Any,
            label: str | None = None,
            external_metadata: dict[str, Any] | None = None,
            data_id: str | None = None,
        ) -> None:
            self.data = data
            self.label = label
            self.external_metadata = external_metadata
            self.data_id = data_id

    async def run_startup_migrations() -> None:
        return None

    async def remember(*args: Any, **kwargs: Any) -> dict[str, Any]:
        received["args"] = args
        received["kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setitem(
        sys.modules,
        "cognee",
        SimpleNamespace(run_startup_migrations=run_startup_migrations, remember=remember),
    )
    monkeypatch.setitem(sys.modules, "cognee.tasks", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "cognee.tasks.ingestion", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "cognee.tasks.ingestion.data_item",
        SimpleNamespace(DataItem=DataItem),
    )

    client = CogneePublicClient()

    await client.remember(
        "note",
        dataset_name="notes",
        tags=("github",),
        source_metadata={"source": "repo_content", "path": "README.md"},
    )

    item = received["args"][0]
    assert isinstance(item, DataItem)
    assert item.external_metadata["source"] == "repo_content"
    assert item.external_metadata["path"] == "README.md"
    assert item.external_metadata["citadel_tags"] == ["github"]
    assert item.external_metadata["dataset"] == "notes"


@pytest.mark.asyncio
async def test_cognee_public_client_delegates_feedback_and_improve(monkeypatch: Any) -> None:
    calls: dict[str, Any] = {}

    async def run_startup_migrations() -> None:
        return None

    async def add_feedback(**kwargs: Any) -> bool:
        calls["feedback"] = kwargs
        return True

    async def improve(**kwargs: Any) -> dict[str, Any]:
        calls["improve"] = kwargs
        return {"ok": True}

    monkeypatch.setitem(
        sys.modules,
        "cognee",
        SimpleNamespace(
            run_startup_migrations=run_startup_migrations,
            session=SimpleNamespace(add_feedback=add_feedback),
            improve=improve,
        ),
    )
    client = CogneePublicClient()

    recorded = await client.add_feedback(
        session_id="session-1",
        qa_id="qa-1",
        score=5,
        text="useful",
    )
    improved = await client.improve(
        dataset="notes",
        session_ids=["session-1"],
        build_global_context_index=True,
    )

    assert recorded is True
    assert improved == {"ok": True}
    assert calls["feedback"] == {
        "session_id": "session-1",
        "qa_id": "qa-1",
        "feedback_score": 5,
        "feedback_text": "useful",
    }
    assert calls["improve"] == {
        "dataset": "notes",
        "session_ids": ["session-1"],
        "build_global_context_index": True,
    }


@pytest.mark.asyncio
async def test_cognee_public_client_uses_chunk_search_by_default(monkeypatch: Any) -> None:
    received: dict[str, Any] = {}

    async def run_startup_migrations() -> None:
        return None

    async def recall(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        received["recall"] = {"args": args, "kwargs": kwargs}
        return []

    async def search(**kwargs: Any) -> list[dict[str, Any]]:
        received["search"] = kwargs
        return [{"ok": True}]

    monkeypatch.setitem(
        sys.modules,
        "cognee",
        SimpleNamespace(
            SearchType=SimpleNamespace(CHUNKS="chunks"),
            run_startup_migrations=run_startup_migrations,
            recall=recall,
            search=search,
        ),
    )
    client = CogneePublicClient()

    result = await client.recall("note", dataset="notes")

    assert result == [{"ok": True}]
    assert "recall" not in received
    assert received["search"]["query_type"] == "chunks"
    assert received["search"]["datasets"] == ["notes"]


@pytest.mark.asyncio
async def test_cognee_public_client_returns_session_recall_before_chunk_search(
    monkeypatch: Any,
) -> None:
    received: dict[str, Any] = {}

    async def run_startup_migrations() -> None:
        return None

    async def recall(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        received["recall"] = {"args": args, "kwargs": kwargs}
        return [{"source": "session"}]

    async def search(**kwargs: Any) -> list[dict[str, Any]]:
        received["search"] = kwargs
        return [{"source": "graph"}]

    monkeypatch.setitem(
        sys.modules,
        "cognee",
        SimpleNamespace(
            SearchType=SimpleNamespace(CHUNKS="chunks"),
            run_startup_migrations=run_startup_migrations,
            recall=recall,
            search=search,
        ),
    )
    client = CogneePublicClient()

    result = await client.recall("note", dataset="notes", session_id="source-session")

    assert result == [{"source": "session"}]
    assert received["recall"]["kwargs"]["scope"] == "session"
    assert received["recall"]["kwargs"]["session_id"] == "source-session"
    assert "search" not in received


@pytest.mark.asyncio
async def test_cognee_public_client_returns_empty_results_for_empty_store(
    monkeypatch: Any,
) -> None:
    class NoDataError(Exception):
        pass

    async def run_startup_migrations() -> None:
        return None

    async def search(**kwargs: Any) -> list[dict[str, Any]]:
        raise NoDataError("No data found in the system, please add data first.")

    monkeypatch.setitem(
        sys.modules,
        "cognee",
        SimpleNamespace(
            SearchType=SimpleNamespace(CHUNKS="chunks"),
            run_startup_migrations=run_startup_migrations,
            search=search,
        ),
    )
    client = CogneePublicClient()

    result = await client.recall("note", dataset="notes")

    assert result == []


@pytest.mark.asyncio
async def test_cognee_public_client_falls_back_when_session_has_no_data(
    monkeypatch: Any,
) -> None:
    class NoDataError(Exception):
        pass

    received: dict[str, Any] = {}

    async def run_startup_migrations() -> None:
        return None

    async def recall(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        received["recall"] = {"args": args, "kwargs": kwargs}
        raise NoDataError("No data found in the system, please add data first.")

    async def search(**kwargs: Any) -> list[dict[str, Any]]:
        received["search"] = kwargs
        return [{"source": "chunks"}]

    monkeypatch.setitem(
        sys.modules,
        "cognee",
        SimpleNamespace(
            SearchType=SimpleNamespace(CHUNKS="chunks"),
            run_startup_migrations=run_startup_migrations,
            recall=recall,
            search=search,
        ),
    )
    client = CogneePublicClient()

    result = await client.recall("note", dataset="notes", session_id="source-session")

    assert result == [{"source": "chunks"}]
    assert received["recall"]["kwargs"]["scope"] == "session"
    assert received["search"]["datasets"] == ["notes"]


def test_cognee_public_client_derives_db_env_from_database_url(monkeypatch: Any) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://db_user:db%23pass@db.example:6543/citadel")
    monkeypatch.setenv("VECTOR_DB_PROVIDER", "pgvector")
    for key in (
        "DB_PROVIDER",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USERNAME",
        "DB_PASSWORD",
        "VECTOR_DB_HOST",
        "VECTOR_DB_PORT",
        "VECTOR_DB_NAME",
        "VECTOR_DB_USERNAME",
        "VECTOR_DB_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)

    CogneePublicClient()._prepare_cognee_environment()

    assert os.environ["DB_PROVIDER"] == "postgres"
    assert os.environ["DB_HOST"] == "db.example"
    assert os.environ["DB_PORT"] == "6543"
    assert os.environ["DB_NAME"] == "citadel"
    assert os.environ["DB_USERNAME"] == "db_user"
    assert os.environ["DB_PASSWORD"] == "db#pass"
    assert os.environ["VECTOR_DB_HOST"] == "db.example"
    assert os.environ["VECTOR_DB_PORT"] == "6543"
    assert os.environ["VECTOR_DB_NAME"] == "citadel"
    assert os.environ["VECTOR_DB_USERNAME"] == "db_user"
    assert os.environ["VECTOR_DB_PASSWORD"] == "db#pass"


def test_cognee_public_client_preserves_explicit_vector_db_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("DB_HOST", "relational.example")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "railway")
    monkeypatch.setenv("DB_USERNAME", "postgres")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("VECTOR_DB_PROVIDER", "pgvector")
    monkeypatch.setenv("VECTOR_DB_HOST", "vector.example")

    CogneePublicClient()._prepare_cognee_environment()

    assert os.environ["VECTOR_DB_HOST"] == "vector.example"
    assert os.environ["VECTOR_DB_PORT"] == "5432"
    assert os.environ["VECTOR_DB_NAME"] == "railway"
    assert os.environ["VECTOR_DB_USERNAME"] == "postgres"
    assert os.environ["VECTOR_DB_PASSWORD"] == "secret"


def test_cognee_public_client_derives_postgres_graph_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("DB_HOST", "postgres.example")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "railway")
    monkeypatch.setenv("DB_USERNAME", "postgres")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("GRAPH_DATABASE_PROVIDER", "postgres")

    CogneePublicClient()._prepare_cognee_environment()

    assert os.environ["GRAPH_DATABASE_HOST"] == "postgres.example"
    assert os.environ["GRAPH_DATABASE_PORT"] == "5432"
    assert os.environ["GRAPH_DATABASE_NAME"] == "railway"
    assert os.environ["GRAPH_DATABASE_USERNAME"] == "postgres"
    assert os.environ["GRAPH_DATABASE_PASSWORD"] == "secret"
