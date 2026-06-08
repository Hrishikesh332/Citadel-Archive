from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

from kb.agent_messenger import AgentMessengerClient, AgentMessengerError


def test_agent_messenger_thread_send_builds_json_cli_command(monkeypatch: Any) -> None:
    calls: list[list[str]] = []

    def fake_which(command: str) -> str:
        return f"/usr/local/bin/{command}"

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"ok": True, "data": {"privateKey": "secret", "id": "msg-1"}}),
            stderr="",
        )

    monkeypatch.setattr("kb.agent_messenger.shutil.which", fake_which)
    monkeypatch.setattr("kb.agent_messenger.subprocess.run", fake_run)
    client = AgentMessengerClient(
        command="masumi-agent-messenger",
        profile="citadel",
        agent_slug="citadel-scout",
    )

    result = client.send_thread(
        to="research-agent",
        message="hello",
        content_type="application/json",
        headers=["x-citadel-run: test"],
    )

    assert result["sent"] is True
    assert result["result"]["data"]["privateKey"] == "[REDACTED]"
    assert calls == [
        [
            "masumi-agent-messenger",
            "thread",
            "send",
            "research-agent",
            "hello",
            "--agent",
            "citadel-scout",
            "--content-type",
            "application/json",
            "--header",
            "x-citadel-run: test",
            "--json",
            "--profile",
            "citadel",
        ]
    ]


def test_agent_messenger_status_reports_missing_cli(monkeypatch: Any) -> None:
    monkeypatch.setattr("kb.agent_messenger.shutil.which", lambda _command: None)

    result = AgentMessengerClient().status()

    assert result["ok"] is False
    assert result["reason"] == "command_not_found"


def test_agent_messenger_raises_sanitized_cli_error(monkeypatch: Any) -> None:
    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            1,
            stdout=json.dumps({"ok": False, "code": "NO_SESSION", "error": "login required"}),
            stderr="",
        )

    monkeypatch.setattr("kb.agent_messenger.subprocess.run", fake_run)
    client = AgentMessengerClient(agent_slug="citadel-scout")

    with pytest.raises(AgentMessengerError, match="NO_SESSION: login required"):
        client.send_channel(channel="public-discussion", message="hello")
