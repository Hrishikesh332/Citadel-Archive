---
name: citadel-mcp-connector
description: Use when a user wants to connect Claude Code, Codex, Cursor, Pi, or any MCP-capable coding agent to Citadel Archive MCP using a Citadel URL and service-account token. Triggers include "connect citadel", "set up citadel mcp", "citadel mcp connector", "add citadel to claude/codex/cursor", or "configure citadel access".
---

# Citadel MCP Connector

Connect the user's MCP-capable coding agent to Citadel Archive.

## Inputs To Ask For

Ask only for missing values:

- **Citadel URL.** Default to `https://citadel-archive-production.up.railway.app`.
- **Citadel service-account token.** Tell the user to paste it once. Do not echo it
  back in chat. Token must start with `ctdl_`.
- **Client type:** Claude Code, Codex, Cursor, Pi, or other.
- **Role:** reader (search-only), writer (search + ingest), or admin (all operations).
  Default to reader unless the user says they need ingest.

Never ask for seed phrases, private keys, provider API keys, or admin keys. The
only secret needed here is a Citadel service-account token beginning with `ctdl_`.

## Safety Rules

- Do not commit the token to any git-tracked file.
- Do not write the token into repository files that may be shared.
- Do not echo the token in chat output.
- Prefer reader tokens for normal use.
- Approval-gate `citadel_ingest`, `citadel_record_feedback`,
  `citadel_run_learning_agent`, and `citadel_improve` when the client supports
  per-tool approval.
- Use HTTPS for hosted Citadel URLs. Plain HTTP is only acceptable for localhost.
- Set `CITADEL_MCP_MAX_INGEST_BYTES` to limit ingest payload size (default 200KB).

## Repo Path

The MCP wrapper runs from this repository:

```text
/Users/sarthiborkar/masumi/Citadel Archive
```

If the repo is in a different location, ask the user for the local path and
replace the path in the config snippets.

## Claude Code Config

Create or update the project `.mcp.json`, replacing `PASTE_CITADEL_TOKEN_HERE`.
If `.mcp.json` already exists, merge only the `citadel` server entry. Prefer
environment variable substitution (`${CITADEL_MCP_ACCESS_TOKEN}`) over
hard-coding.

```json
{
  "mcpServers": {
    "citadel": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/sarthiborkar/masumi/Citadel Archive",
        "run",
        "python",
        "-m",
        "kb.mcp_server"
      ],
      "env": {
        "CITADEL_HTTP_BASE_URL": "https://citadel-archive-production.up.railway.app",
        "CITADEL_MCP_ACCESS_TOKEN": "${CITADEL_MCP_ACCESS_TOKEN}",
        "CITADEL_MCP_MAX_INGEST_BYTES": "200000"
      }
    }
  }
}
```

## Codex Config

Append this to `~/.codex/config.toml`, replacing `PASTE_CITADEL_TOKEN_HERE`.
Write only to the user's local Codex config unless they ask for a snippet.

```toml
[mcp_servers.citadel]
command = "uv"
args = [
  "--directory",
  "/Users/sarthiborkar/masumi/Citadel Archive",
  "run",
  "python",
  "-m",
  "kb.mcp_server",
]
[mcp_servers.citadel.env]
CITADEL_HTTP_BASE_URL = "https://citadel-archive-production.up.railway.app"
CITADEL_MCP_ACCESS_TOKEN = "PASTE_CITADEL_TOKEN_HERE"
CITADEL_MCP_MAX_INGEST_BYTES = "200000"

[mcp_servers.citadel.tools.citadel_ingest]
approval_mode = "approve"

[mcp_servers.citadel.tools.citadel_record_feedback]
approval_mode = "approve"

[mcp_servers.citadel.tools.citadel_run_learning_agent]
approval_mode = "approve"

[mcp_servers.citadel.tools.citadel_improve]
approval_mode = "approve"
```

## Cursor Config

Open Cursor Settings → Features → Model Context Protocol. Add a new server:

- **Name**: `citadel`
- **Type**: `command`
- **Command**: `uv`
- **Args**: `--directory`, repo path, `run`, `python`, `-m`, `kb.mcp_server`
- **Env**: `CITADEL_HTTP_BASE_URL`, `CITADEL_MCP_ACCESS_TOKEN`, `CITADEL_MCP_MAX_INGEST_BYTES`

## Generic MCP Client

Any client that supports MCP stdio can connect by spawning:

```bash
uv --directory "/Users/sarthiborkar/masumi/Citadel Archive" run python -m kb.mcp_server
```

With env vars: `CITADEL_HTTP_BASE_URL`, `CITADEL_MCP_ACCESS_TOKEN`, `CITADEL_MCP_MAX_INGEST_BYTES`.

## Verification

After writing the config, ask the user to restart the client. Then verify by
calling `citadel_session`. If that succeeds, call `citadel_search` with a small
test query.

If the server fails to start:

1. Run `uv --directory "/Users/sarthiborkar/masumi/Citadel Archive" sync --dev`.
2. Check that the Citadel token is present in the client config.
3. Check that the Citadel URL is reachable (`curl $CITADEL_HTTP_BASE_URL/healthz`).
4. Do not print the token while debugging.
