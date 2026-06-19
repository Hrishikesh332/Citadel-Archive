# Private GitHub Sync Security Plan

Citadel's GitHub sync is a private-data system when `CITADEL_GITHUB_TOKEN` can
read private repositories. Even without cloning source code, repository names,
PR titles, commit messages, authors, URLs, and digest text can reveal customer
work, unreleased products, incidents, or credentials accidentally pasted into
metadata.

## CSO Findings

### HIGH: Cron logs must not contain private metadata

Railway captures stdout and stderr for build and deployment logs:
https://docs.railway.com/guides/logs

Control implemented: `scripts/run_github_sync.py` now defaults to
`CITADEL_GITHUB_SYNC_OUTPUT_MODE=summary`. The summary includes operational
counts and security-scan counters, not repo names, commit messages, PR titles,
digest previews, or finding evidence.

Allowed modes:

```bash
CITADEL_GITHUB_SYNC_OUTPUT_MODE=summary  # default
CITADEL_GITHUB_SYNC_OUTPUT_MODE=none
CITADEL_GITHUB_SYNC_OUTPUT_MODE=full     # local debugging only; never for private repos
```

### HIGH: Private repo metadata must not be sent to external LLMs by default

The organization digest can use an LLM to summarize source packets. For private
repos, that source packet is sensitive.

Control implemented: if the GitHub sync result contains private repositories,
Citadel uses deterministic local digesting unless explicitly opted in:

```bash
CITADEL_ORG_DIGEST_LLM_ALLOW_PRIVATE=false
```

Do not set this to `true` unless the LLM provider, model, data-retention policy,
and contract are approved for private repository metadata.

### MEDIUM: Private repo inclusion must be explicit and filterable

GitHub's repository API can return private repositories visible to the token.
Citadel now exposes this as policy:

```bash
CITADEL_GITHUB_SYNC_INCLUDE_PRIVATE=true
CITADEL_GITHUB_SYNC_REPO_ALLOWLIST=masumi-network/citadel,masumi-network/private-*
CITADEL_GITHUB_SYNC_REPO_DENYLIST=masumi-network/archive-*,sandbox
```

Prefer a GitHub App or fine-grained token with only the repository metadata,
commit, and pull-request permissions needed. GitHub Apps can be installed on
selected repositories and their installation tokens lose access when a repo is
removed from the installation:
https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps

Fine-grained token permission reference:
https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens

### MEDIUM: Metadata needs a pre-ingest security gate

Control implemented: GitHub metadata is scanned before Cognee ingestion. The
scanner blocks ingestion at `high` severity by default and returns sanitized
findings only.

```bash
CITADEL_GITHUB_SYNC_SECURITY_SCAN_ENABLED=true
CITADEL_GITHUB_SYNC_SECURITY_BLOCK_SEVERITY=high
```

The built-in metadata scanner catches:

- Secret-looking tokens in repo descriptions, commit messages, PR titles, and
  event summaries.
- Risky URL forms: credentialed URLs, unsafe schemes, punycode domains, IP
  literal links, shorteners, and oversized URLs.
- Corruption/Trojan-source markers: bidirectional control characters,
  replacement characters, and unexpected control bytes.

The scanner does not clone repositories and does not execute code. Full malware,
SAST, dependency, and binary scanning must run in GitHub/CI.

## Required GitHub Controls

Enable these at org/repo level for every private repo that can affect Citadel,
Railway, production services, or team secrets.

### Secret scanning and push protection

Enable GitHub secret scanning, push protection, validity checks where available,
and partner patterns. This catches secrets before they land and alerts on
existing leaks.

Docs:
https://docs.github.com/en/code-security/secret-scanning/enabling-secret-scanning-features

Add a second OSS scanner in CI for defense in depth:

- Gitleaks: https://github.com/gitleaks/gitleaks
- TruffleHog: https://docs.trufflesecurity.com/scan-for-secrets

Response rule: if a real secret is found, rotate it. Deleting the commit or
removing it from the digest is not enough.

### Code scanning

Enable CodeQL default setup for supported languages. GitHub supports code
scanning for public repos and eligible organization private repos with GitHub
Code Security enabled.

Docs:
https://docs.github.com/en/code-security/code-scanning/enabling-code-scanning/configuring-default-setup-for-code-scanning

### Dependency and malware alerts

Enable Dependabot alerts and security updates. Dependabot alerts trigger when
the dependency graph changes or a new advisory is added.

Docs:
https://docs.github.com/en/code-security/dependabot/dependabot-alerts/about-dependabot-alerts

Enable Dependabot malware alerts for package malware coverage where supported:
https://docs.github.com/code-security/concepts/supply-chain-security/dependabot-malware-alerts

Add OSV-Scanner for lockfiles, SBOMs, and container images. OSV-Scanner can scan
lockfiles and SBOMs, and its docs note that package names, versions, ecosystems,
and file hashes are sent to OSV/deps.dev unless offline mode is used.

Docs:
https://google.github.io/osv-scanner-v1/usage/
https://github.com/google/osv-scanner

For higher-signal SCA, add a reachability-aware tool such as Semgrep Supply
Chain, especially for malicious dependency detection:
https://semgrep.dev/docs/semgrep-supply-chain/malicious-dependencies

### CI/CD hardening

Use the OWASP Top 10 CI/CD risks as the review checklist:
https://owasp.org/www-project-top-10-ci-cd-security-risks/

Minimum rules:

- Pin GitHub Actions to immutable commit SHAs for sensitive workflows.
- Set `permissions:` to least privilege, usually `contents: read`.
- Avoid `pull_request_target` unless the workflow is explicitly hardened.
- Do not run untrusted PR code with secrets available.
- Do not echo secrets, full env dumps, tokens, or private repo metadata.
- Require branch protection/rulesets, status checks, and review before merge.

Use OpenSSF Scorecard to measure workflow permissions, branch protection, pinned
dependencies, and other supply-chain posture:
https://scorecard.dev/

### SBOM and supply-chain integrity

Use OWASP SCVS as the maturity model:
https://owasp.org/www-project-software-component-verification-standard/

For component inventory, publish CycloneDX SBOMs and track them in Dependency-
Track or an equivalent platform:
https://www.dependencytrack.org/triage/dependency-check/

For build artifact integrity, use SLSA provenance and verify artifacts before
deployment:
https://slsa.dev/spec/latest/

## Phishing and URL Handling

Citadel's metadata scanner flags risky URL shapes locally. For reputation
checks, use Google Safe Browsing or Web Risk. Google states the Safe Browsing
API checks URLs against unsafe web-resource lists:
https://developers.google.com/safe-browsing/reference/rest

If urlscan.io is used, submit with `visibility=private` and strip PII first.
urlscan documents public, unlisted, and private scan visibility:
https://urlscan.io/docs/api/

Never submit private repo URLs, pre-signed URLs, invite links, customer URLs, or
URLs containing tokens to public reputation services.

## Malware and Binary Handling

Citadel's current sync does not download binaries. If a future scanner fetches
files or release artifacts:

- Never execute downloaded code.
- Store artifacts in a quarantine directory.
- Hash files before and after scanning.
- Scan with ClamAV or an equivalent malware scanner.
- Apply YARA rules for organization-specific indicators.

ClamAV scanning docs:
https://docs.clamav.net/manual/Usage/Scanning.html

## Data Corruption Controls

Required controls for GitHub sync state, backup mirror, and future scanner state:

- Atomic writes for state files.
- JSON schema/version validation before using state.
- SHA-256 checksums in backup manifests.
- Idempotent scan records keyed by repo, PR/commit SHA, scanner, and timestamp.
- Periodic restore tests from Backup Mirror.
- Never mark a blocked unsafe digest as successfully ingested.

## Operational Workflow

1. A teammate opens or updates a PR.
2. GitHub-native controls run first: secret scanning, CodeQL, Dependabot,
   dependency review, and CI scanners.
3. Citadel cron fetches metadata only.
4. Citadel metadata scanner runs before digest ingestion.
5. If a high/critical finding exists, Citadel blocks ingestion and records only
   sanitized scanner metadata.
6. A human reviews the source PR/commit in GitHub, rotates any leaked secrets,
   and fixes the issue.
7. After remediation, rerun the cron or wait for the next scheduled run.

## What Citadel Should Not Do

- Do not clone every private repo into the Citadel web service.
- Do not execute teammate code in the Citadel runtime.
- Do not send private repo metadata to external LLMs by default.
- Do not store raw secret values, full suspicious URLs, or raw scanner evidence.
- Do not depend on one scanner. Use GitHub-native controls plus independent CI
  scanners.
