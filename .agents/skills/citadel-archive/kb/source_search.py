from __future__ import annotations

from hashlib import sha256
import json
import re
from pathlib import Path
from typing import Any

from kb.config import CitadelConfig


MIN_WORD_LENGTH = 2
MAX_CHUNK_CHARS = 8_000
GITHUB_SOURCE_URL_TEMPLATE = "https://github.com/orgs/{org}/repositories"
GITHUB_DOC_ID_PREFIX = "ghsync"


def github_section_id(org: str, title: str) -> str:
    """Stable document id for a GitHub digest section.

    Stable across reruns for the same org/section title so a search hit can be
    re-fetched through ``GET /api/documents/{id}``.
    """
    digest = sha256(f"{org}\n{title}".encode("utf-8")).hexdigest()[:16]
    return f"{GITHUB_DOC_ID_PREFIX}:{digest}"


def github_section_document(document_id: str, config: CitadelConfig) -> dict[str, Any] | None:
    """Resolve a GitHub digest section by its stable id, or None if unknown."""
    state_path = Path(config.github_sync_state_path)
    state = _load_state(state_path)
    digest = str(state.get("last_digest") or "").strip()
    if not digest:
        return None
    org = str(state.get("org") or config.github_org)
    source_url = GITHUB_SOURCE_URL_TEMPLATE.format(org=org)
    for title, content in _digest_sections(digest):
        if github_section_id(org, title) == document_id:
            return {
                "id": document_id,
                "source": "github_sync_state",
                "source_type": "github",
                "dataset": config.github_sync_dataset,
                "session_id": config.github_sync_session,
                "title": title,
                "body": content[:MAX_CHUNK_CHARS],
                "metadata": {
                    "org": org,
                    "source_url": source_url,
                    "checked_at": state.get("last_checked_at"),
                    "digest_at": state.get("last_digest_at"),
                },
            }
    return None


def _tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for word in re.findall(r"\b\w+\b", text.lower()):
        if len(word) < MIN_WORD_LENGTH:
            continue
        if len(word) > 3 and word.endswith("s"):
            word = word[:-1]
        tokens.add(word)
    return tokens


def _load_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _digest_sections(digest: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    title = "GitHub source digest"
    lines: list[str] = []

    def flush() -> None:
        content = "\n".join(lines).strip()
        if content:
            sections.append((title, content))

    for line in digest.splitlines():
        if line.startswith("# "):
            flush()
            title = line.removeprefix("# ").strip() or title
            lines = [line]
            continue
        if line.startswith("## "):
            flush()
            title = line.removeprefix("## ").strip() or title
            lines = [line]
            continue
        lines.append(line)

    flush()
    return sections


def search_github_sync_state(
    query: str,
    config: CitadelConfig,
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    state_path = Path(config.github_sync_state_path)
    state = _load_state(state_path)
    digest = str(state.get("last_digest") or "").strip()
    if not digest:
        return []

    query_tokens = _tokenize(query)
    scored_sections: list[tuple[int, int, str, str]] = []
    for position, (title, content) in enumerate(_digest_sections(digest)):
        content_tokens = _tokenize(f"{title}\n{content}")
        score = len(query_tokens & content_tokens)
        scored_sections.append((score, position, title, content))

    scored_sections.sort(key=lambda item: (-item[0], item[1]))
    selected = scored_sections[: max(1, top_k)]
    org = str(state.get("org") or config.github_org)
    source_url = GITHUB_SOURCE_URL_TEMPLATE.format(org=org)

    return [
        {
            "id": github_section_id(org, title),
            "source": "github_sync_state",
            "dataset": config.github_sync_dataset,
            "session_id": config.github_sync_session,
            "title": title,
            "content": content[:MAX_CHUNK_CHARS],
            "score": score,
            "metadata": {
                "org": org,
                "source_url": source_url,
                "checked_at": state.get("last_checked_at"),
                "digest_at": state.get("last_digest_at"),
            },
        }
        for score, _position, title, content in selected
    ]
