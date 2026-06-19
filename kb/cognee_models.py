from __future__ import annotations

from typing import Any


CITADEL_GRAPH_PROMPT = """Extract Citadel Organization Vault memory.

Prefer explicit source-linked concepts:
- SourceSnapshot: source evidence, path, URL, and source type.
- VaultContribution: durable decisions, runbooks, architecture notes, and project facts.

Keep private seat chatter and raw transient observations out of durable organization facts
unless the text clearly marks them as approved or org-bound.
"""


def citadel_domain_graph_options() -> dict[str, Any]:
    """Return Cognee graph customization options lazily.

    Importing Cognee's DataPoint at module import time makes test and bootstrap
    environments brittle, so the optional domain schema is only constructed when
    the feature flag asks for it.
    """

    from cognee.low_level import DataPoint

    class SourceSnapshotType(DataPoint):
        name: str = "Source Snapshot"

    class VaultContributionType(DataPoint):
        name: str = "Vault Contribution"

    class SourceSnapshot(DataPoint):
        name: str
        source: str | None = None
        source_url: str | None = None
        path: str | None = None
        is_type: SourceSnapshotType
        metadata: dict[str, Any] = {"index_fields": ["name", "source", "path"]}

    class VaultContribution(DataPoint):
        name: str
        summary: str | None = None
        tags: list[str] | None = None
        supported_by: list[SourceSnapshot] | None = None
        is_type: VaultContributionType
        metadata: dict[str, Any] = {"index_fields": ["name", "summary"]}

    return {
        "graph_model": VaultContribution,
        "custom_prompt": CITADEL_GRAPH_PROMPT,
    }
