from __future__ import annotations

import re
from typing import Iterable

_SEPARATOR = re.compile(r"[^a-z0-9:_-]+")


def normalize_tag(tag: str) -> str:
    normalized = _SEPARATOR.sub("-", tag.strip().lower()).strip("-")
    return normalized


def normalize_tags(tags: Iterable[str] | None) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags or []:
        value = normalize_tag(tag)
        if value and value not in seen:
            normalized.append(value)
            seen.add(value)
    return tuple(normalized)


def merge_tags(default_tags: Iterable[str], tags: Iterable[str] | None) -> tuple[str, ...]:
    return normalize_tags([*default_tags, *(tags or [])])


def tag_metadata(tags: Iterable[str]) -> dict[str, object]:
    tag_tuple = normalize_tags(tags)
    return {"citadel_tags": list(tag_tuple), "citadel_tag_string": ",".join(tag_tuple)}
