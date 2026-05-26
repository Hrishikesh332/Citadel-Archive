from __future__ import annotations

from typing import Any

from scripts import run_github_sync


def _clear_sync_env(monkeypatch: Any) -> None:
    for name in (
        "CITADEL_ADMIN_KEY",
        "CITADEL_BASE_URL",
        "CITADEL_GITHUB_SYNC_ACCESS_KEY",
        "CITADEL_GITHUB_SYNC_DRY_RUN",
        "CITADEL_GITHUB_SYNC_ENDPOINT",
        "CITADEL_GITHUB_SYNC_FORCE",
        "CITADEL_GITHUB_SYNC_TARGET_URL",
        "CITADEL_WEB_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_scheduled_sync_posts_to_web_learning_agent(monkeypatch: Any) -> None:
    _clear_sync_env(monkeypatch)
    calls: list[dict[str, Any]] = []

    def post_json(
        url: str,
        *,
        payload: dict[str, Any],
        access_key: str,
        timeout: int,
    ) -> tuple[int, dict[str, Any]]:
        calls.append(
            {
                "url": url,
                "payload": payload,
                "access_key": access_key,
                "timeout": timeout,
            }
        )
        return (
            200,
            {
                "ok": True,
                "ingested": True,
                "improved": True,
                "sources": {
                    "github": {
                        "repos_scanned": 40,
                        "changed_count": 2,
                        "event_count": 3,
                        "commit_count": 4,
                    }
                },
            },
        )

    monkeypatch.setenv("CITADEL_GITHUB_SYNC_TARGET_URL", "https://citadel.example")
    monkeypatch.setenv("CITADEL_GITHUB_SYNC_ACCESS_KEY", "secret")
    monkeypatch.setenv("CITADEL_GITHUB_SYNC_FORCE", "true")
    monkeypatch.setenv("CITADEL_GITHUB_SYNC_DRY_RUN", "false")
    monkeypatch.setattr(run_github_sync, "_post_json", post_json)

    assert run_github_sync.run() == 0
    assert calls == [
        {
            "url": "https://citadel.example/api/learning-agent/run",
            "payload": {"force": True, "dry_run": False},
            "access_key": "secret",
            "timeout": 900,
        }
    ]


def test_scheduled_sync_requires_access_key_for_web_target(monkeypatch: Any) -> None:
    _clear_sync_env(monkeypatch)
    monkeypatch.setenv("CITADEL_GITHUB_SYNC_TARGET_URL", "https://citadel.example")

    assert run_github_sync.run() == 1


def test_scheduled_sync_fails_on_remote_http_error(monkeypatch: Any) -> None:
    _clear_sync_env(monkeypatch)

    def post_json(
        url: str,
        *,
        payload: dict[str, Any],
        access_key: str,
        timeout: int,
    ) -> tuple[int, dict[str, Any]]:
        return 500, {"detail": "boom"}

    monkeypatch.setenv("CITADEL_GITHUB_SYNC_TARGET_URL", "https://citadel.example")
    monkeypatch.setenv("CITADEL_GITHUB_SYNC_ACCESS_KEY", "secret")
    monkeypatch.setattr(run_github_sync, "_post_json", post_json)

    assert run_github_sync.run() == 1
