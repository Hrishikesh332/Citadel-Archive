# Organization Vault Plan

Last updated: 2026-05-28.

Citadel is becoming an **Organization Vault**: a cloud-hosted, access-controlled
memory layer for a company. It keeps approved company sources in sync, turns raw
source material into structured knowledge, and exposes that knowledge to humans
and agents through the web app, API, and MCP.

## Goal

The end goal is a shared organizational memory that behaves like an
Obsidian-style vault for the company, but is hosted, governed, source-linked,
and agent-accessible.

The vault should answer questions like:

- What changed in our repositories today?
- Which team, project, or source owns this knowledge?
- What context should a teammate or agent know before working on a task?
- Which documents, commits, notes, and decisions support this answer?
- What can this member or agent read, write, sync, or administer?

## Product Boundaries

Citadel is not a generic database. The database stores data, but the product is
the governed organization vault on top of it.

Citadel is not a full Obsidian clone. It borrows the vault mental model, links,
backlinks, graph, and workspace feel, while adding cloud hosting, source sync,
access control, provenance, and MCP access.

Citadel is not a replacement for GitHub. GitHub remains the source of truth for
code and repository activity. Citadel learns from GitHub and produces structured
context, daily summaries, and searchable memory.

## Core Actors

- **Vault Admin**: manages sources, access roles, tokens, sync policy, and audit
  visibility.
- **Vault Member**: searches, reads, and optionally contributes knowledge based
  on their role.
- **Agent Identity**: an autonomous or assistant agent that uses its own access
  token and role-scoped MCP capabilities.
- **Source Owner**: a person or team responsible for the quality and freshness
  of a connected source.

## Core Objects

- **Organization Vault**: the shared body of company knowledge.
- **Source Material**: raw inputs such as repositories, commits, notes, docs,
  manual entries, and future connectors.
- **Structured Knowledge**: source-linked concepts, relationships, summaries,
  citations, and context produced from source material.
- **Learning Process**: the governed process that turns source material into
  structured knowledge.
- **Access Token**: a credential issued to a member or agent identity.
- **Access Role**: the permission level attached to a member or agent identity.

## Phase 1: Shared Organization Vault

Phase 1 proves that Citadel can be the company's shared, cloud-hosted knowledge
vault.

### 1. Hosted Vault

- Run Citadel as a cloud-hosted service.
- Provide a web dashboard for vault status, search, sources, access, and audit.
- Keep the UI focused on a workspace experience rather than a marketing page.
- Preserve a clear separation between read workflows and write/admin workflows.

### 2. Source Sync

- Sync selected GitHub organization repositories.
- Include private repositories when the configured GitHub token has access.
- Track repository activity, recent commits, and source freshness.
- Support selected Obsidian vault material through explicit push from the plugin
  or API.
- Keep raw source material distinguishable from structured knowledge.

### 3. Learning Process

- Use an LLM-backed learning process to structure raw source material.
- Extract useful concepts, relationships, summaries, tags, and provenance.
- Produce daily repository activity updates.
- Keep every generated answer or summary tied back to source material.
- Avoid treating every synced artifact as trusted knowledge by default.

### 4. Dashboard And Access

- Let admins issue separate access tokens for each vault member and agent
  identity.
- Support reader, writer, and admin access roles.
- Let readers search and view source status.
- Let writers ingest material and submit feedback.
- Let admins run source sync, manage access, review audit activity, and manage
  agent access.
- Audit sensitive actions such as ingest, sync, improve, token creation, and
  admin changes.

### 5. MCP Access

- Expose the vault through a secure MCP server.
- Let Claude Code, Codex, and autonomous agents search the vault through MCP.
- Let writer/admin agents call role-scoped tools for ingest, feedback, source
  sync, and improvement.
- Require explicit approval for sensitive tools in clients wherever possible.
- Treat retrieved vault content as untrusted context that cannot override agent
  system or developer instructions.

## Phase 2: Masumi Agent Messenger

Phase 2 adds agent-to-agent coordination around the Organization Vault.

- Give each employee or teammate an agent messenger identity.
- Let agent identities communicate and coordinate through Masumi Agent
  Messenger.
- Let those agents call the Organization Vault through their own scoped access
  tokens.
- Let agents share task context, decisions, status updates, and source-linked
  answers with each other.
- Keep the Organization Vault as the shared memory layer rather than embedding
  company memory inside each individual agent.

## Daily Knowledge Flow

1. A connected source changes, such as a repository commit or pushed note.
2. Citadel records the change as source material with provenance.
3. The learning process summarizes and structures the useful context.
4. The vault updates its structured knowledge and relationship graph.
5. The dashboard shows source status, recent activity, and daily updates.
6. Humans and agents query the vault through the UI, API, or MCP.
7. Feedback and new source activity improve future structured knowledge.

## Trust Rules

- Every useful piece of structured knowledge should retain a link to its source
  material.
- Private repository access must come from a scoped GitHub token with only the
  needed repository permissions.
- Every member and agent should have its own access token.
- Shared tokens should be avoided outside of bootstrap or local testing.
- Reader, writer, and admin permissions must stay distinct.
- Agent access should be auditable by identity, role, tool, source, and outcome.
- Sensitive actions should be reviewed, approved, or restricted by role.

## Open Design Questions

- Which sources are trusted enough for automatic structuring?
- Which sources require human review before becoming structured knowledge?
- What is the exact difference between a team, department, dataset, and source
  boundary?
- Should daily updates be per repository, per department, per person, or all
  three?
- How should conflicting knowledge be marked when repositories, notes, and
  human feedback disagree?
- Which actions should agents be allowed to perform without human approval?
- What should be shared through Masumi Agent Messenger versus stored in the
  Organization Vault?

## Immediate Build Priorities

1. Keep polishing the hosted dashboard around source status, access, audit, and
   search.
2. Create scoped access tokens for real team and agent testing.
3. Smoke-test MCP search and ingest from Claude Code and Codex.
4. Verify private GitHub repository sync with a fine-grained token.
5. Make daily source updates visible and useful for non-technical teammates.
6. Define review rules for source material before broad automatic learning.
7. Continue grilling the domain model until the product language is stable.
