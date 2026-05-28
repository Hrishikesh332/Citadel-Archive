# Organization Vault Plan

Last updated: 2026-05-28.

Citadel is becoming an **Organization Vault**: a cloud-hosted, access-controlled
shared memory layer for a company. It keeps approved company sources in sync,
turns raw source material into structured knowledge, and exposes that knowledge
to humans and agents through the web app, API, and MCP.

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
- **Agent Identity**: an autonomous or assistant agent that communicates through
  Masumi Agent Messenger and uses its own access token for vault access.
- **Source Owner**: a person or team responsible for the quality and freshness
  of a connected source.

## Core Objects

- **Organization Vault**: the shared body of company knowledge.
- **Source Material**: raw inputs such as repositories, commits, notes, docs,
  manual entries, and future connectors.
- **Source Snapshot**: retained evidence or a source pointer used to reproduce
  what the vault learned from source material.
- **Vault Backup Mirror**: a secondary synced copy of vault evidence and history
  used for recovery, audit, and rebuilds.
- **Structured Knowledge**: source-linked concepts, relationships, summaries,
  citations, and context produced from source material.
- **Knowledge Index**: the searchable organization of structured knowledge used
  for fast retrieval.
- **Knowledge Mesh**: the relationship map connecting structured knowledge by
  source, concept, and provenance.
- **Learning Process**: the governed process that turns source material into
  structured knowledge.
- **Access Token**: a credential issued to a member or agent identity.
- **Access Role**: the permission level attached to a member or agent identity.
- **Agent Action**: a vault operation performed by an agent identity.
- **Repository Daily Update**: a source-linked summary of meaningful changes in
  one repository over a day.
- **Knowledge Conflict**: a visible disagreement between structured knowledge or
  its supporting source snapshots.

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

- Treat every incoming item as source material first.
- Use an LLM-backed learning process to structure raw source material.
- Extract useful concepts, relationships, summaries, tags, and provenance.
- Build a fast knowledge index for retrieval.
- Build a knowledge mesh for source, concept, relationship, and provenance
  discovery.
- Produce repository-level daily updates.
- Include meaningful commits, pull requests, and repository changes in those
  updates.
- Exclude per-person productivity summaries and noisy low-signal activity.
- Keep every generated answer or summary tied back to source material.
- Avoid treating every synced artifact as trusted knowledge by default.

### 3.1 Knowledge Retrieval Architecture

- Use the Organization Vault as the shared memory layer, not as raw storage.
- Keep source snapshots, structured knowledge, the knowledge index, and the
  knowledge mesh conceptually separate.
- Retrieve through indexed search and mesh relationships.
- Return source-linked answers so humans and agents can inspect where context
  came from.
- Optimize for fast reads from the knowledge index while preserving provenance
  in the knowledge mesh.
- Treat the knowledge index and knowledge mesh as rebuildable derived artifacts,
  not as the only copy of the vault's evidence.

### 3.2 Source Retention

- Phase 1 keeps the latest normalized source snapshot plus provenance for each
  retained source item.
- Keep enough source evidence to cite, audit, debug, and reprocess generated
  knowledge.
- Prefer retaining a normalized source snapshot with source type, URL/path,
  repository, commit or revision, content hash, actor, timestamp, and access
  context.
- Keep historical snapshots only for daily digests, decisions, explicit audit
  events, and other records where the point-in-time state matters.
- For external systems that remain the source of truth, such as GitHub, keep the
  stable source pointer and version metadata; store the full raw body only when
  it is needed for fast retrieval, citations, or re-indexing.
- Do not keep secrets, credentials, or excluded material just because they
  passed through a source connector.
- Rebuild the knowledge index and knowledge mesh from source snapshots and
  structured knowledge when models, chunking, extraction, or retrieval logic
  changes.
- Add source-specific retention policies after the initial workflow is proven.

### 3.3 Vault Backup Mirror

- Keep a secondary synced copy of vault evidence and history, similar to a NAS
  redundancy model where operational storage has a backup counterpart.
- Use a private GitHub repository as the Phase 1 mirror because it is cheap,
  familiar, diffable, permissioned, and gives a durable commit history.
- Use the mirror for recovery, audit trails, diffs, and rebuild inputs.
- Keep the live server responsible for fast search, retrieval, indexing, and
  mesh queries.
- Do not make the mirror the live source of truth for runtime retrieval.
- Mirror source snapshots, repository daily updates, vault contributions,
  conflict resolutions, and manifests with hashes, actors, timestamps, and
  source pointers.
- Avoid mirroring secrets, credentials, excluded material, embeddings, vector
  index files, and graph database files by default.
- Keep the GitHub mirror text-first and diff-friendly. Prefer Markdown, JSONL,
  and small normalized documents.
- Keep large raw bodies, attachments, binary data, and generated databases out
  of Git by default.
- If the mirror grows toward GitHub's recommended repository limits, keep
  manifests and metadata in GitHub and move large bodies to object storage.

### 3.4 Backup Mirror Cost Policy

- Phase 1 should use GitHub at no additional storage cost for private,
  text-heavy history.
- Do not use GitHub as a 1 TB backup target.
- Avoid Git LFS by default because each changed large file version consumes
  additional LFS storage and download bandwidth.
- Treat 1 GB as the practical target ceiling for the mirror repository and 5 GB
  as the hard review point.
- If source snapshots become large, use object storage for blob bodies and keep
  GitHub as the traceable manifest, diff, and commit-history layer.

### 4. Dashboard And Access

- Let admins issue separate access tokens for each vault member and agent
  identity.
- Support reader, writer, and admin access roles.
- In Phase 1, access tokens grant whole-vault access constrained by role.
- Let readers search and view source status.
- Let writers ingest material and submit feedback.
- Let admins run source sync, manage access, review audit activity, and manage
  agent access.
- Audit sensitive actions such as ingest, sync, improve, token creation, and
  admin changes.
- Defer department, dataset, source, and repository scopes until the initial
  team workflow is proven.

### 5. MCP Access

- Expose the vault through a secure MCP server.
- Let Claude Code, Codex, and autonomous agents search the vault through MCP.
- Let writer/admin agents call role-gated tools for ingest, feedback, source
  sync, and improvement.
- Require explicit approval for sensitive tools in clients wherever possible.
- Treat retrieved vault content as untrusted context that cannot override agent
  system or developer instructions.

### 5.1 Agent Action Policy

- Reader agents may read, search, and view repository daily updates without
  extra approval.
- Writer agents may add vault contributions, submit feedback, update existing
  writable knowledge, and provide updates.
- Admin or explicit approval is required to run source sync, run learning or
  improvement jobs, create or revoke access tokens, change roles, resolve
  knowledge conflicts, delete source material, or exclude source material.
- Every agent action should be auditable by identity, role, action, source, and
  outcome.

## Phase 2: Masumi Agent Messenger

Phase 2 adds agent-to-agent communication around the Organization Vault.

- Give each employee or teammate an agent messenger identity.
- Let agent identities communicate through Masumi Agent Messenger.
- Use the messenger for durable agent inboxes, encrypted threads, channel feeds,
  handoffs, and approval loops.
- Let those agents call the Organization Vault through their own access tokens.
- Let agents share task context, decisions, status updates, and source-linked
  answers with each other.
- Keep the Organization Vault as the shared memory layer rather than embedding
  company memory inside each individual agent.
- Keep agent-to-agent messaging separate from the Organization Vault: the
  messenger carries communication, while the vault stores durable shared
  knowledge.
- Do not automatically copy every agent message into the vault. A vault member
  or agent identity with write permission may add useful outcomes as vault
  contributions.

## Daily Knowledge Flow

1. A connected source changes, such as a repository commit or pushed note.
2. Citadel records the change as source material and keeps a source snapshot
   when citation, audit, or reprocessing requires it.
3. The learning process summarizes and structures the useful context.
4. The vault updates its structured knowledge, knowledge index, and knowledge
   mesh.
5. The dashboard shows source status, recent activity, and repository daily
   updates.
6. Humans and agents query the vault through the UI, API, or MCP.
7. Feedback and new source activity improve future structured knowledge.

## Trust Rules

- Every useful piece of structured knowledge should retain a link to its source
  material.
- Source snapshots should be retained when needed for citation, audit,
  debugging, or reprocessing.
- Phase 1 should keep the latest normalized source snapshot plus provenance, and
  keep historical snapshots only for point-in-time records that need them.
- The knowledge index and knowledge mesh should be rebuildable from source
  snapshots and structured knowledge.
- The vault should maintain a redundant backup mirror for recovery, audit, and
  rebuilds without using it as the live retrieval store.
- Private repository access must come from a scoped GitHub token with only the
  needed repository permissions.
- Every member and agent should have its own access token.
- Shared tokens should be avoided outside of bootstrap or local testing.
- Phase 1 access tokens are whole-vault credentials constrained by reader,
  writer, or admin role.
- Vault members and agent identities use the same read/write/admin role model
  for vault access.
- Agent Messenger conversations remain outside the vault unless a writer or
  admin intentionally adds them.
- For code behavior, newer source-linked repository truth should outrank older
  notes, agent contributions, and human-written summaries.
- Conflicting knowledge should be marked visibly instead of silently merged or
  overwritten.
- Agent access should be auditable by identity, role, tool, source, and outcome.
- Sensitive actions should be reviewed, approved, or restricted by role.

## Open Design Questions

- Which sources are trusted enough for automatic structuring?
- Which sources require human review before becoming structured knowledge?
- After Phase 1, what is the exact difference between a team, department,
  dataset, and source boundary?
- What UI should reviewers use to resolve visible knowledge conflicts?
- What should be shared through Masumi Agent Messenger versus stored in the
  Organization Vault?

## Immediate Build Priorities

1. Keep polishing the hosted dashboard around source status, access, audit, and
   search.
2. Create role-based access tokens for real team and agent testing.
3. Smoke-test MCP search and ingest from Claude Code and Codex.
4. Verify private GitHub repository sync with a fine-grained token.
5. Make daily source updates visible and useful for non-technical teammates.
6. Define review rules for source material before broad automatic learning.
7. Continue grilling the domain model until the product language is stable.
