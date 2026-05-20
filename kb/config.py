from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Iterable

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only before dependencies are installed.
    def load_dotenv(*args: object, **kwargs: object) -> bool:
        return False


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class CitadelConfig:
    tenant_id: str = "personal"
    user_id: str = "local"
    admin_key: str | None = None
    default_dataset: str = "personal"
    default_session: str = "personal-session"
    default_tags: tuple[str, ...] = field(default_factory=tuple)
    min_chars: int = 3
    exclude_patterns: tuple[str, ...] = (
        ".git/*",
        ".venv/*",
        "__pycache__/*",
        "node_modules/*",
    )
    auto_improve: bool = False
    build_global_context_index: bool = False

    @classmethod
    def from_env(cls, *, env_file: str | None = ".env") -> "CitadelConfig":
        if env_file:
            load_dotenv(env_file, override=False)

        return cls(
            tenant_id=os.getenv("CITADEL_TENANT_ID", "personal"),
            user_id=os.getenv("CITADEL_USER_ID", "local"),
            admin_key=os.getenv("CITADEL_ADMIN_KEY") or None,
            default_dataset=os.getenv("CITADEL_DEFAULT_DATASET", "personal"),
            default_session=os.getenv("CITADEL_DEFAULT_SESSION", "personal-session"),
            default_tags=tuple(_csv(os.getenv("CITADEL_DEFAULT_TAGS"))),
            min_chars=int(os.getenv("CITADEL_MIN_CHARS", "3")),
            exclude_patterns=tuple(
                _csv(os.getenv("CITADEL_EXCLUDE_PATTERNS"))
                or [".git/*", ".venv/*", "__pycache__/*", "node_modules/*"]
            ),
            auto_improve=_bool(os.getenv("CITADEL_AUTO_IMPROVE")),
            build_global_context_index=_bool(os.getenv("CITADEL_BUILD_GLOBAL_CONTEXT_INDEX")),
        )

    def with_tags(self, tags: Iterable[str]) -> "CitadelConfig":
        merged = tuple(dict.fromkeys([*self.default_tags, *tags]))
        return CitadelConfig(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            admin_key=self.admin_key,
            default_dataset=self.default_dataset,
            default_session=self.default_session,
            default_tags=merged,
            min_chars=self.min_chars,
            exclude_patterns=self.exclude_patterns,
            auto_improve=self.auto_improve,
            build_global_context_index=self.build_global_context_index,
        )
