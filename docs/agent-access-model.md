# Citadel Agent Access Model

Research date: 2026-05-21.

This note defines how Citadel should become a shared knowledge base for humans,
Claude Code, Codex, and autonomous agents.

## Recommendation

Build one secure Citadel MCP server as the integration layer. Package small
Claude/Codex skills or plugins around it for team workflows.

Skills should teach agents when and how to use Citadel. MCP should be the
actual capability boundary that exposes search, source status, ingestion,
feedback, and admin operations. This keeps one access-control model instead of
separate one-off integrations for every agent.

## Why MCP First

- Claude Code supports project-scoped MCP servers via `.mcp.json`, which can be
  committed so a team has the same tool configuration.
- Codex supports MCP servers directly in `~/.codex/config.toml`, and Codex
  plugins can bundle MCP server configuration.
- OpenAI Responses/Agents workflows can call remote MCP servers, including
  authenticated remote MCP endpoints.
- MCP cleanly separates model-callable tools, read-only resources, and
  user-invoked prompts.

Useful source docs:

- OpenAI Codex skills and plugins: https://developers.openai.com/codex/concepts/customization
- OpenAI Codex plugin MCP bundling: https://developers.openai.com/codex/plugins/build
- OpenAI remote MCP tools: https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- Claude Code MCP: https://code.claude.com/docs/en/mcp
- Claude Code skills: https://code.claude.com/docs/en/slash-commands
- MCP authorization: https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
- MCP tools/resources/prompts: https://modelcontextprotocol.io/specification/2025-06-18/server/tools

## MCP Surface

Expose these tools first:

- `citadel_search`
  - Role: reader
  - Input: `query`, optional `dataset`, optional `top_k`
  - Output: answer, cited chunks, dataset, confidence notes

- `citadel_list_sources`
  - Role: reader
  - Output: configured sources, sync status, last run, failure state

- `citadel_get_mesh`
  - Role: reader
  - Output: current graph/mesh summary and counters

- `citadel_ingest`
  - Role: writer
  - Input: `data`, `dataset`, `tags`
  - Output: accepted/rejected, reason, created record IDs

- `citadel_record_feedback`
  - Role: writer
  - Input: `qa_id`, `score`, optional `text`
  - Output: recorded/improved

- `citadel_run_source_sync`
  - Role: admin
  - Requires explicit approval in clients

- `citadel_improve`
  - Role: admin
  - Requires explicit approval in clients

Expose these resources:

- `citadel://session`
- `citadel://datasets`
- `citadel://sources`
- `citadel://events/recent`

Expose these prompts:

- `citadel_answer_from_kb`
- `citadel_ingest_decision`
- `citadel_summarize_source_changes`

## Team Access Model

Current local implementation uses simple role keys:

- `CITADEL_READER_KEYS`
- `CITADEL_WRITER_KEYS`
- `CITADEL_ADMIN_KEY`

That is acceptable for local testing and small trusted teams, but it should not
be the long-term sharing model. Production should have durable principals:

- `User`: a human login identity.
- `ServiceAccount`: an agent identity.
- `Team`: a group that owns datasets and sources.
- `Membership`: user or service account plus role inside a team.
- `Dataset`: logical knowledge boundary.
- `Source`: GitHub repo, URL, file upload, manual note, or future connector.
- `ApiToken`: hashed token, owner, scopes, expiry, last-used timestamp.
- `AuditEvent`: immutable trail of search, ingest, source sync, admin action.

Roles:

- Reader: search, view sources/status/events, read resources.
- Writer: reader plus ingest and feedback.
- Admin: writer plus source sync, access management, agent tokens, settings.

Scopes:

- `kb:read`
- `kb:search`
- `kb:ingest`
- `kb:feedback`
- `sources:read`
- `sources:sync`
- `agents:manage`
- `access:manage`
- `audit:read`

## Security Rules

- Use browser sessions for humans and bearer tokens/OAuth for agents.
- Store API tokens hashed, never plaintext.
- Let admins create, rotate, disable, and expire agent tokens.
- Scope every token to a role, dataset/team, and tool allowlist.
- Rate limit per user/service account, especially search and ingest.
- Audit every MCP call with actor, role, tool, dataset, success/failure, and
  request ID.
- Treat retrieved KB content as untrusted context. Do not allow retrieved text to
  override system/developer instructions.
- Sensitive MCP tools must require client approval: sync, improve, delete,
  reindex, invite, token creation.
- Prefer OAuth 2.1 + Protected Resource Metadata for hosted remote MCP. Local
  stdio MCP can use env-provided credentials.

## Dashboard Model

Citadel should feel like an operating-system dashboard with separate apps, not
one crowded page.

Primary navigation:

- Home: status, recent events, health, shortcuts.
- Search: the default page for most users.
- Knowledge: datasets, tags, graph/mesh, indexed material.
- Sources: GitHub sync, file/upload sources, connectors, ingest jobs.
- Ingest: manual ingest and review queue; hidden from readers.
- Agents: MCP setup, Claude/Codex skill install snippets, service accounts.
- Access: users, teams, invites, roles, tokens.
- Audit: searchable log of sensitive activity.
- Settings: environment, model/provider, retention, backup.

Role-specific defaults:

- Reader starts on Search and sees no write/admin actions.
- Writer starts on Search or Sources and can ingest/feedback.
- Admin starts on Home and sees Access, Agents, Audit, and Settings.

## Why Search And Ingest Are Separate

Search is a read workflow. Ingest is a write workflow. Keeping them separate is
important because readers should not be able to mutate the knowledge base.

We can still make the product feel simple:

- Search remains the main page.
- Sources can auto-ingest approved repos/files.
- Ingest becomes a focused admin/writer workflow for manual notes, uploads, and
  rejected-source review.

## Build Plan

1. Keep the current role-key system for immediate local testing.
2. Add a persistent access store for users, service accounts, roles, tokens, and
   audit events.
3. Add an admin Access page for inviting teammates and issuing scoped agent
   tokens.
4. Build `kb/mcp_server.py` around the existing FastAPI service methods.
5. Add `.mcp.json` for Claude Code project setup, using env-token expansion.
6. Add a Codex plugin or repo skill that bundles the MCP server and Citadel
   workflows.
7. Add dashboard Agents and Audit pages.
8. Move hosted deployments to OAuth/OIDC when the team grows beyond shared
   trusted local users.
