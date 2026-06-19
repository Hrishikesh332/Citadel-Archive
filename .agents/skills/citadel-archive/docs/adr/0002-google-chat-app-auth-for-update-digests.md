# Use Google Chat App Authentication For Organization Update Digests

Citadel will deliver Phase 1 **Organization Update Digests** to Google Chat as outbound-only messages from a Google Chat app using Chat API app authentication, rather than incoming webhooks. Incoming webhooks are faster to set up, but they are space-specific and do not establish the durable app identity or future inbound-command path that Citadel needs for an organization-wide communication surface.

**Considered Options**

- Incoming webhooks: lowest setup cost, one-way only, tied to a single space URL.
- Chat API app authentication: more setup, but one app can be installed in multiple spaces and later support inbound Google Chat events.
- Full interactive Chat app immediately: useful for mentions and commands, but too much surface area for Phase 1.

**Consequences**

- Phase 1 is outbound-only; mentions, slash commands, and Chat-to-vault ingestion are out of scope.
- Google service account credentials become production secrets and must not be logged, committed, mirrored, or exposed in Chat output.
- Digest delivery is a communication adapter over the **Organization Vault**, not a separate source of vault truth.
