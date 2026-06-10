from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from kb.access import AccessStore, default_scopes, validate_role_scopes


def store(tmp_path: Path) -> AccessStore:
    return AccessStore(tmp_path / "access.json")


def iso_offset(**delta: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(**delta)).isoformat()


def rejection_events(access_store: AccessStore) -> list[dict[str, Any]]:
    return [
        event
        for event in access_store.snapshot()["audit_events"]
        if event["action"] == "access.token.rejected"
    ]


def test_valid_token_authenticates_and_updates_last_used(tmp_path: Path) -> None:
    access_store = store(tmp_path)
    created = access_store.create_principal_token(
        name="ci-bot",
        kind="service_account",
        role="reader",
    )

    session = access_store.authenticate_token(created.token)

    assert session is not None
    assert session.identity.role == "reader"
    assert session.identity.actor_name == "ci-bot"
    assert session.identity.token_id == created.api_token.id
    tokens = access_store.snapshot()["tokens"]
    assert tokens[0]["last_used_at"] is not None


def test_expired_token_is_rejected_with_audit_event(tmp_path: Path) -> None:
    access_store = store(tmp_path)
    created = access_store.create_principal_token(
        name="expired-bot",
        kind="service_account",
        role="reader",
        expires_at=iso_offset(hours=-1),
    )

    assert access_store.authenticate_token(created.token) is None

    events = rejection_events(access_store)
    assert len(events) == 1
    assert events[0]["success"] is False
    assert events[0]["detail"]["reason"] == "expired"
    assert events[0]["detail"]["token_id"] == created.api_token.id


def test_future_expiry_still_authenticates(tmp_path: Path) -> None:
    access_store = store(tmp_path)
    created = access_store.create_principal_token(
        name="fresh-bot",
        kind="service_account",
        role="writer",
        expires_at=iso_offset(hours=1),
    )

    session = access_store.authenticate_token(created.token)

    assert session is not None
    assert rejection_events(access_store) == []


def test_revoked_token_is_rejected_with_audit_event(tmp_path: Path) -> None:
    access_store = store(tmp_path)
    created = access_store.create_principal_token(
        name="revoked-bot",
        kind="service_account",
        role="admin",
    )

    revoked = access_store.revoke_token(created.api_token.id)

    assert revoked is not None
    assert access_store.authenticate_token(created.token) is None
    events = rejection_events(access_store)
    assert events[0]["detail"]["reason"] == "revoked"


def test_token_session_lookup_enforces_expiry(tmp_path: Path) -> None:
    access_store = store(tmp_path)
    created = access_store.create_principal_token(
        name="cookie-bot",
        kind="service_account",
        role="reader",
        expires_at=iso_offset(seconds=-1),
    )

    assert access_store.token_session(created.api_token.id) is None
    assert rejection_events(access_store)[0]["detail"]["reason"] == "expired"


def test_unknown_token_returns_none_without_audit_noise(tmp_path: Path) -> None:
    access_store = store(tmp_path)
    access_store.create_principal_token(name="real", kind="service_account", role="reader")

    assert access_store.authenticate_token("ctdl_not_a_real_token") is None
    assert rejection_events(access_store) == []


def test_scopes_cannot_exceed_role(tmp_path: Path) -> None:
    access_store = store(tmp_path)

    with pytest.raises(ValueError, match="exceed reader role"):
        access_store.create_principal_token(
            name="greedy-reader",
            kind="service_account",
            role="reader",
            scopes=["kb:read", "kb:ingest"],
        )


def test_scopes_can_reduce_within_role(tmp_path: Path) -> None:
    access_store = store(tmp_path)
    created = access_store.create_principal_token(
        name="narrow-writer",
        kind="service_account",
        role="writer",
        scopes=["kb:read", "kb:search"],
    )

    session = access_store.authenticate_token(created.token)

    assert session is not None
    assert session.identity.scopes == ("kb:read", "kb:search")


def test_token_role_downgrade_gets_downgraded_default_scopes(tmp_path: Path) -> None:
    access_store = store(tmp_path)
    principal = access_store.create_principal(
        name="ops-admin",
        kind="user",
        role="admin",
    )

    created = access_store.create_token(
        principal_id=principal.id,
        name="read-only-key",
        role="reader",
    )

    assert created.api_token.role == "reader"
    assert created.api_token.scopes == default_scopes("reader")


def test_validate_role_scopes_rejects_unknown_role_and_dedupes() -> None:
    with pytest.raises(ValueError, match="Unsupported role"):
        validate_role_scopes("owner", ["kb:read"])

    assert validate_role_scopes("reader", ["kb:read", "kb:read", " kb:search "]) == (
        "kb:read",
        "kb:search",
    )


def test_has_tokens_ignores_revoked_tokens(tmp_path: Path) -> None:
    access_store = store(tmp_path)
    created = access_store.create_principal_token(
        name="only-token",
        kind="service_account",
        role="reader",
    )
    assert access_store.has_tokens() is True

    access_store.revoke_token(created.api_token.id)

    assert access_store.has_tokens() is False
