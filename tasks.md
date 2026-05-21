# Citadel Tasks

## Done

- Repo reset from Cognee fork -> clean Citadel wrapper.
- Cognee kept as dep only. No vendored upstream source.
- Python package `citadel`, import package `kb`.
- CLI added: ingest, search, feedback, improve.
- FastAPI service added.
- Railway config added.
- Hosted UI added at `/`.
- Live mesh UI added:
  - graph canvas
  - index panels
  - ingest form
  - search form
  - self-upgrade button
  - SSE live events
- Admin key gate added:
  - `/login`
  - `/admin/session`
  - `/admin/logout`
  - UI/API/SSE protected
  - `/healthz` public for Railway health
- Railway resources created/wired:
  - app service: `Citadel-Archive`
  - Postgres service: `Postgres`
  - app volume: `/data`
  - Postgres refs wired into app vars
  - Kuzu graph path -> `/data/.cognee_system`
  - data path -> `/data/.data_storage`
- Runtime deps made explicit via `requirements.txt`.
- Tests passing locally: `18 passed`.
- GitHub organization sync added:
  - fetches `masumi-network` repos and public org events
  - creates a daily digest
  - ingests digest into Citadel
  - runs improvement for `masumi-github-daily`
  - persists scan state at `/data/.citadel/github_sync_state.json`
  - admin API added: `/api/github-sync`, `/api/github-sync/run`
- UI pass added:
  - GitHub sync status/manual run panel
  - richer runtime stats
  - better loading/empty/error states
  - improved mobile layout and focus/interaction states
- Feedback UI added:
  - manual QA ID feedback form
  - score selection and optional note/dataset/session metadata
  - search-result helper button when a QA ID is present
  - mesh feedback counter/status updates
- OS dashboard redesign added:
  - top system bar and persistent status chrome
  - separate pages for overview, search, ingest, feedback, sources, events, and access
  - left workspace navigation rail
  - central mesh window and runtime metrics strip
  - responsive mobile/tablet layout smoke-checked with browser automation
- Role-based access keys added:
  - reader keys can view/search only
  - writer keys can ingest and record feedback
  - admin key can run GitHub sync, self-upgrade, and view access setup
  - `/api/session` exposes current role/capabilities to the UI
- Agent access research captured:
  - docs note: `docs/agent-access-model.md`
  - decision: build one secure Citadel MCP server as the shared capability layer
  - wrap the MCP server with thin Claude/Codex skills or plugins for workflows
  - keep Search and Ingest as separate read/write surfaces
- Persistent access-token foundation added:
  - JSON-backed access store at `CITADEL_ACCESS_STORE_PATH`
  - `User`/`ServiceAccount`-style principals
  - hashed API tokens with prefix, role, scopes, expiry, last-used timestamp,
    and revoked state
  - admin APIs for access snapshot, token creation, token revocation, and audit
  - Access page token creation/list/revoke/audit UI
  - tests passing locally: `20 passed`
- Production health verified on 2026-05-21:
  - `Citadel-Archive`, `Citadel-GitHub-Sync`, and `Postgres` all `SUCCESS`
  - `/healthz` returns `{"ok":true,"service":"citadel"}`
  - `/` redirects to `/login`
- Railway cron service created:
  - service: `Citadel-GitHub-Sync`
  - schedule: `0 3 * * *`
  - volume: `/data`

## Current Railway State

- Web service is live:
  - `https://citadel-archive-production.up.railway.app/healthz`
  - `https://citadel-archive-production.up.railway.app/`
- Cron service is deployed from commit `451efdf18f039d4586b3afa4505d024ca06b3864`.
- Local feedback UI, OS dashboard, and role-key changes have not been deployed yet.
- OpenRouter is configured through `OPENROUTER_API_KEY` and
  `LLM_MODEL=openrouter/free` on both Railway services.

## Needed From User

- OpenRouter model/key config is done:
  - `OPENROUTER_API_KEY` is set on `Citadel-Archive`.
  - `Citadel-GitHub-Sync` references the same key.
  - Citadel maps `OPENROUTER_API_KEY` to Cognee's expected `LLM_API_KEY`
    at runtime.
  - `LLM_PROVIDER=custom`
  - `LLM_ENDPOINT=https://openrouter.ai/api/v1`
  - `LLM_MODEL=openrouter/free`
- Enable pgvector in Railway Postgres.
  - Run in DB console/psql:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

- Optional: rotate `CITADEL_ADMIN_KEY` after first login test.

## Research-Backed Direction

- Citadel should act like a workspace OS for the knowledge base, not a single
  crowded dashboard page.
- MCP is the main integration surface for Claude Code, Codex, OpenAI
  Responses/Agents workflows, and future autonomous agents.
- Skills/plugins are distribution and workflow wrappers. They should not own
  authorization or duplicate Citadel business logic.
- Team access should move from shared env keys to durable principals:
  - users
  - service accounts
  - teams
  - memberships
  - scoped API tokens
  - audit events
- Human access should use browser sessions. Agent access should use bearer
  tokens first, then OAuth/OIDC for hosted production.
- Sensitive agent tools must require approval:
  - source sync
  - self-improve
  - reindex/delete
  - invite/team changes
  - token creation

## Next

- Verify cron service next scheduled execution after 03:00 UTC.
- Verify admin key unlocks UI.
- Verify `/api/github-sync` in the hosted UI.
- Run GitHub sync once manually.
- Test real ingest -> Cognee -> Postgres/pgvector/Kuzu.
- Test search.
- Test hosted feedback with a real Cognee QA ID.
- Test self-upgrade.
- Deploy local OS dashboard and role-key changes to Railway after local smoke
  test is complete.

## Next: Team Access

- Add full team/membership model:
  - named teams
  - memberships between users/service accounts and teams
  - dataset-scoped grants
- Add token expiry validation UI and creation controls.
- Add token rotation flow.
- Add disabled principal flow.
- Add admin Access UI:
  - edit teammate/service-account role
  - assign dataset/team scope
  - rotate token
  - disable principal
- Keep existing env role keys as bootstrap/local fallback.

## Next: Agent Integrations

- Build `kb/mcp_server.py` on top of existing Citadel service methods.
- Expose reader MCP tools:
  - `citadel_search`
  - `citadel_list_sources`
  - `citadel_get_mesh`
- Expose writer MCP tools:
  - `citadel_ingest`
  - `citadel_record_feedback`
- Expose admin MCP tools:
  - `citadel_run_source_sync`
  - `citadel_improve`
- Expose MCP resources:
  - `citadel://session`
  - `citadel://datasets`
  - `citadel://sources`
  - `citadel://events/recent`
- Expose MCP prompts:
  - `citadel_answer_from_kb`
  - `citadel_ingest_decision`
  - `citadel_summarize_source_changes`
- Add project `.mcp.json` for Claude Code with env-token expansion.
- Add Codex skill or plugin package:
  - `SKILL.md` workflow instructions
  - bundled MCP server config
  - install/setup docs
- Add Claude Code skill:
  - search-before-answer workflow
  - ingest-project-decision workflow
  - source-sync/admin workflow

## Next: Dashboard

- Add OS-style pages:
  - Knowledge
  - Agents
  - Audit
  - Settings
- Make Search the default reader page.
- Make Sources/Ingest the default writer workspace.
- Make Home/Access/Agents/Audit the admin workspace.
- Add Agents page:
  - Claude Code MCP setup snippet
  - Codex MCP/plugin setup snippet
  - service account token list
  - tool/scopes matrix
- Add Audit page:
  - search events
  - ingest events
  - MCP tool calls
  - source sync/admin actions
- Add Settings page:
  - model/provider state
  - source retention
  - backup/export controls
  - health/config checks

## Later

- OAuth/OIDC login for hosted team deployments.
- Dataset-level and team-level ACLs.
- Approval queue for high-impact agent actions.
- Rate limiting per user/service account/tool.
- Structured audit export.
- Secret rotation reminders.
- Prompt-injection hardening for retrieved KB content:
  - mark retrieved text as untrusted context
  - keep source citations
  - reject tool instructions found inside retrieved content
- OAuth 2.1 + Protected Resource Metadata for remote hosted MCP.
- Secure MCP tunnel option for private/on-prem deployments.
- Mesh introspection:
  - pull real Cognee graph nodes
  - pull real vector index stats
  - show failed pipeline jobs
  - show memify/self-upgrade history
