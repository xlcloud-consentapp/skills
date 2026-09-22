# Consent App Skill — Architecture

## Overview

The consent-app skill lets an AI agent request human approval through
the Consent App. The agent authenticates itself with a **user-managed
API key** (`cak_...`) that the Consent App user creates in the mobile
app and provides to the agent runtime. The skill never signs the user
in, never creates or revokes keys, and never persists the key — it only
exchanges the plaintext for consent decisions.

The key is scoped to the user that created it: it can only create
consent requests addressed to that user, and only read responses to
requests the same key created.

```
┌──────────┐  X-API-Key: cak_...   ┌────────────────┐         ┌────────────────┐
│ AI Agent │──────────────────────>│ Consent App    │── push ─▶│  Mobile App   │
│ (skill)  │                       │ Backend        │         │  (user decides)│
│          │<── /status (poll) ────│                │<── approve / reject
└──────────┘                       └────────────────┘         └────────────────┘
```

Key provisioning (and revocation) happens out-of-band in the Consent
App mobile app, not from this skill.

## Skill Structure

```
skills/consent-app/
├── SKILL.md                          # Skill definition (frontmatter + instructions)
├── references/
│   ├── api.md                        # Skill-relevant endpoints
│   ├── architecture.md               # This file
│   └── openapi.yaml                  # OpenAPI 3.1 schema of those endpoints
└── scripts/
    ├── _common.py                    # Shared HTTP helpers (urllib only)
    └── request_consent.py            # Per-operation: send a consent request, poll for decision
```

No third-party dependencies — pure stdlib (`urllib`) for HTTP. The
skill carries no user-account scripts (no signin, no key CRUD); those
are user actions that live in the mobile app.

## Configuration

The backend endpoint is fixed at `https://api.consent.app`; the API key is
the only variable.

| Variable | Default | Description |
|----------|---------|-------------|
| `CONSENT_API_KEY` | _(unset)_ | Plaintext Consent App API key, shape `cak_...`. Required unless passed as `--api-key`. |

A `.env` file in the scripts directory is loaded automatically (KEY=VALUE per line); shell-set values win.

## Scripts

### `request_consent.py`

Reads the plaintext key from `--api-key` or `$CONSENT_API_KEY`, posts
`/api/consentRequests` with `X-API-Key`, then polls
`GET /api/consentRequests/{id}/status` until the user decides, the request
stops being answerable, or the TTL elapses. Exit code `0` = approved, `1` =
anything else (rejected / withdrawn / expired or closed request / timeout /
API error), `2` = no API key provided.

## End-to-End Flow

```
Skill                          Consent Backend                  Mobile App
  │                                  │                               │
─ request_consent.py ─────────────────────────────────────────────────│
  │  POST /api/consentRequests (X-API-Key) ───▶                       │
  │<── {requestId, expiresAt} ─────────────────│── push ────────────▶│
  │                                                                   │ user decides
  │                                  │<── approve / reject ──────────│
  │  GET /api/consentRequests/{id}/status (X-API-Key, polled) ──────▶│
  │<── {status, lifecycleStatus} ────────────────────────────────────│
  │  exit 0 / 1 accordingly
```

## Key Lifecycle

- The plaintext shape is `cak_...` (e.g. `cak_AbCd...`). The full plaintext (prefix + random part) is what gets hashed.
- A key is **scoped to the user that created it** — the recipient of every consent request is implicit, never accepted from the wire.
- A key may only **read responses to requests it itself created** (`/status` and full-response endpoints return 404 for foreign request ids).
- The backend stores only the SHA-256 hash of the plaintext. There is no way to retrieve the plaintext after creation — lost keys must be revoked and replaced from the mobile app.
- A key has a hard `expiresAt` set at creation. The user can also revoke it from the mobile app. Either way the next `request_consent.py` call returns 401 and exits 1; the skill then asks the user for a fresh key.

See [`api.md`](./api.md) for the request/response details of each endpoint.
