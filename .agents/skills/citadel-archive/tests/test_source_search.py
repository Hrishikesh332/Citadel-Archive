from __future__ import annotations

import json
from typing import Any

from kb.config import CitadelConfig
from kb.source_search import (
    GITHUB_DOC_ID_PREFIX,
    github_section_document,
    search_github_sync_state,
)

DIGEST = """# masumi-network GitHub daily update

Checked at: 2026-06-01T00:00:00Z
Source: https://github.com/orgs/masumi-network/repositories

## Changed repositories
- masumi-network/agent (TypeScript): pushed 2026-06-01. Agent runtime.

## Recent commits
- 2026-06-01: sarthib7 committed abc123 to masumi-network/agent: teach the archive about commits.
"""


def _config(tmp_path: Any) -> CitadelConfig:
    state = {
        "org": "masumi-network",
        "last_checked_at": "2026-06-01T00:00:00Z",
        "last_digest_at": "2026-06-01T00:00:00Z",
        "last_digest": DIGEST,
    }
    path = tmp_path / "github_state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return CitadelConfig(
        github_sync_dataset="masumi-network",
        github_sync_state_path=str(path),
    )


def test_search_results_carry_stable_ids(tmp_path: Any) -> None:
    config = _config(tmp_path)

    results = search_github_sync_state("commits about the archive", config, top_k=5)

    assert results
    for result in results:
        assert str(result["id"]).startswith(f"{GITHUB_DOC_ID_PREFIX}:")
    # Stable across calls.
    again = search_github_sync_state("commits about the archive", config, top_k=5)
    assert [r["id"] for r in results] == [r["id"] for r in again]


def test_search_hit_drills_down_to_document(tmp_path: Any) -> None:
    config = _config(tmp_path)
    hit = search_github_sync_state("commits about the archive", config, top_k=1)[0]

    document = github_section_document(hit["id"], config)

    assert document is not None
    assert document["id"] == hit["id"]
    assert document["title"] == hit["title"]
    assert "teach the archive about commits" in document["body"]
    assert document["source_type"] == "github"


def test_unknown_document_id_returns_none(tmp_path: Any) -> None:
    config = _config(tmp_path)

    assert github_section_document(f"{GITHUB_DOC_ID_PREFIX}:deadbeefdeadbeef", config) is None
