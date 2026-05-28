# Citadel

Citadel is an organization knowledge context for shared, source-linked company memory. This language keeps product concepts distinct from storage, implementation, and integration mechanisms.

## Language

**Organization Vault**:
A cloud-hosted, access-controlled body of company knowledge that is shared across humans and agents.
_Avoid_: knowledge base, database, company Obsidian

**Source Material**:
Raw company material that may be used to produce structured knowledge.
_Avoid_: knowledge, truth, memory

**Structured Knowledge**:
Source-linked company knowledge that has been organized into explicit concepts, relationships, and context.
_Avoid_: raw data, unprocessed sync, dump

**Learning Process**:
The governed transformation of **Source Material** into **Structured Knowledge**.
_Avoid_: self-learning, magic sync, auto-truth

**Vault Member**:
A human participant who has permission to access an **Organization Vault**.
_Avoid_: user, teammate, account

**Agent Identity**:
A non-human actor that has permission to access an **Organization Vault**.
_Avoid_: bot, autonomous agent, service user

**Access Token**:
A revocable credential that lets a **Vault Member** or **Agent Identity** access an **Organization Vault**.
_Avoid_: MCP key, shared password, API secret

**Access Role**:
A named permission level that determines what a **Vault Member** or **Agent Identity** may do in an **Organization Vault**.
_Avoid_: read me access, write access key

## Relationships

- An **Organization Vault** is accessed by humans and agents.
- An **Organization Vault** contains **Structured Knowledge**.
- **Structured Knowledge** is derived from **Source Material** through a **Learning Process**.
- A **Vault Member** or **Agent Identity** uses an **Access Token** to access an **Organization Vault**.
- An **Access Role** limits what a **Vault Member** or **Agent Identity** may read or change.

## Example Dialogue

> **Dev:** "Should this GitHub repository be added to the database?"
> **Domain expert:** "Add it as **Source Material**. It becomes **Structured Knowledge** only after the **Learning Process** extracts useful context from it."
>
> **Dev:** "Should every teammate get an MCP key?"
> **Domain expert:** "Give each **Vault Member** or **Agent Identity** its own **Access Token** with the right **Access Role**."

## Flagged Ambiguities

- "knowledge base" and "database" were used for the same product concept; resolved: the product concept is **Organization Vault**.
- "self-learning" was used to mean automatic structuring of raw inputs; resolved: the domain term is **Learning Process**.
- "MCP key" and "access token" were used for credentials; resolved: the domain term is **Access Token**.
