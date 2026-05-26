# Security Policy

Action Marshall is action-level release control for AI agents. Because Action Marshall sits in the path of agent actions that change production systems, vulnerabilities in Action Marshall can have real-world impact. We take security reports seriously.

## Supported Versions

Action Marshall is currently pre-1.0. Until a `1.0.0` release ships:

- Only the `main` branch and the latest tagged release are supported.
- Security fixes are applied to `main` and backported to the latest tag if it is less than 30 days old.

After `1.0.0`, the most recent minor version will receive security fixes.

## Reporting a Vulnerability

**Do not file a public GitHub issue for security vulnerabilities.**

Instead, please email a private report. Include as much of the following as you can:

- A description of the vulnerability and its impact.
- Steps to reproduce, ideally with a minimal proof-of-concept.
- The affected version, commit SHA, or deployment configuration.
- Whether you believe the vulnerability has been exploited.
- Your name and contact details, and whether you want public credit.

We aim to:

- Acknowledge receipt within **72 hours**.
- Provide an initial assessment within **7 days**.
- Coordinate a fix and disclosure timeline with you (typically 30–90 days depending on severity).

We will credit reporters in the changelog and any security advisory unless you ask us not to.

## Scope

In scope:

- The Action Marshall backend API (`backend/`).
- The Action Marshall Python SDK (`sdk/`).
- The Action Marshall web UI (`ui/`).
- Official Docker images and `docker-compose.yaml`.
- Example connectors that ship in this repo.

Out of scope:

- Third-party SaaS systems Action Marshall integrates with (ServiceNow, Jira, Slack, etc.). Report those to their vendors.
- Customer-written policies that produce unexpected decisions.
- Connector credentials managed outside Action Marshall.
- The hosted Action Marshall product (when it exists, it will have its own security contact).

## Threat Model

Action Marshall is designed to reduce risk from:

- Uncontrolled bulk actions taken by agents.
- Over-permissioned agents reaching tools they should not.
- Accidental production changes.
- Unreviewed tool calls.
- Missing audit evidence after an incident.
- Action-level compliance gaps.

Action Marshall is **not** designed to defend against:

- Model hallucination by itself.
- Compromise of the customer's identity provider.
- A malicious infrastructure administrator with direct database or signing-key access.
- Bad policies written by the customer.
- Connector credentials leaked outside Action Marshall.
- Compromise of the customer's application code that calls Action Marshall.

For each threat, the specific controls (and known weaknesses) are documented in [docs/security.md](docs/security.md).

## Cryptographic Material

Action Marshall signs audit receipts with HMAC-SHA256 using a secret from the `PROOF_SECRET` environment variable. The same secret is required to verify receipts. Do not commit this value to source control. In production, generate a long random value and store it in your secret manager.

For the full crypto inventory (signing, hashing, canary subset selection, password storage and its known weaknesses) see [docs/security.md](docs/security.md).

## Disclosures

Past security advisories will be listed here as they are issued. None at this time.
