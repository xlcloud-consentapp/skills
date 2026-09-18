---
name: consent-app
description: 'Request user consent/approval before critical operations via the Consent App. Use when: agent needs human approval, critical operation requires consent, destructive action needs confirmation, workflow gate, approval flow, consent check, human-in-the-loop, workflow automation with approval steps, sending emails or messages on behalf of user, shopping checkout confirmation, payment authorization, order placement, booking confirmation, subscription sign-up, account changes, data sharing consent, form submission approval, file sharing authorization, social media posting, calendar event creation, contact management actions.'
argument-hint: '"<title>" "<description>" [--ttl <seconds>] [--api-key cak_...]'
metadata:
  openclaw:
    primaryEnv: CONSENT_API_KEY
---

# Consent App

**Decision heuristic:** If the operation has real-world side effects on behalf of the user — sends, pays, books, posts, deletes, shares, signs up, or otherwise commits the user to something a third party will see or charge — call this skill **before** the side effect, never after.

Request user consent/approval through the Consent App before proceeding with critical or destructive operations. The user receives a consent request in their mobile app and can approve or reject it.

The skill talks to the Consent App backend using a **user-managed API key**: the Consent App user creates a key in the mobile app and gives the plaintext (`cak_...`) to the skill. The skill never signs the user in, never persists the key, and never performs any user-account action — it only creates consent requests and reads back the user's decision. The key can be revoked from the mobile app at any time.

## When to Use

- Before sending emails, messages, or notifications on behalf of the user
- Before completing a shopping checkout or placing an order
- Before authorizing payments or financial transactions
- Before booking confirmations (flights, hotels, appointments, reservations)
- Before signing up for subscriptions or services
- Before sharing data or files with third parties
- Before posting on social media or publishing content
- Before making account changes (profile updates, password resets, plan upgrades)
- Before submitting forms or applications
- As an approval gate in multi-step automated workflows (e.g. search → select → approve → purchase)
- Before destructive operations (delete, cancel, revoke)
- Whenever an AI agent acts on behalf of the user and the action has real-world consequences

## When NOT to Use

Do **not** invoke this skill for operations that are reversible, local, or have no third-party impact — false-positive consent prompts train the user to rubber-stamp them and erode the signal. Skip the consent gate for:

- Read-only operations (search, list, fetch, summarize, render).
- Local-only file edits in the agent's working directory (code changes, drafts, scratch files) — version control is the safety net there.
- Internal dev/test loops (running the test suite, starting a local server, reproducing a bug).
- Idempotent or trivially reversible actions (toggling a local feature flag, clearing a local cache).
- Intermediate steps inside a workflow whose **final** step is already gated (don't ask twice).
- Questions or clarifications back to the user — those are conversational, not consent-worthy.
- Operations the user has just explicitly instructed in the current turn ("send this email now" — the instruction is the consent; gating it again is noise). Still gate if the user instructed a *class* of actions and the agent is choosing instances ("book me a flight" → gate the specific booking).

When in doubt: if undoing the operation requires contacting a third party, calling support, or refunding money — gate it. If undoing it is one `git checkout` or one button-click away — don't.

## Prerequisites

- A Consent App user (mobile app installed, signed in).
- The user has created an API key in the mobile app and has provided the plaintext (`cak_...`) to the agent runtime (e.g. via `CONSENT_API_KEY` env var, a secret manager, or `--api-key` on the command line).
- Python 3.9+. No pip dependencies — stdlib only.

## Configuration

The skill always talks to the Consent App at `https://api.consent.app`. The only thing to configure is the user's API key, set as an environment variable (or in a `.env` file in the scripts directory):

| Variable | Default | Description |
|----------|---------|-------------|
| `CONSENT_API_KEY` | _(unset)_ | Plaintext Consent App API key, shape `cak_...`. **Required** unless passed as `--api-key`. |

## Procedure: Request Consent

Whenever a critical operation needs approval, run [request_consent.py](./scripts/request_consent.py):

```bash
python ./scripts/request_consent.py "<TITLE>" "<DESCRIPTION>" [--ttl 300] [--api-key cak_...]
```

- `<TITLE>` — short headline (e.g. `"Purchase: Nike Air Max"`)
- `<DESCRIPTION>` — exactly what will happen if approved; the user sees this verbatim
- `--ttl` — seconds the consent request stays open and the script waits (default 300, which is the backend maximum; the backend silently falls back to 60 if you pass an out-of-range value)
- `--api-key` — plaintext API key; defaults to `$CONSENT_API_KEY`

The script:

1. Calls `POST /api/consentRequests` with `X-API-Key: <plaintext>`, sending the title/description plus a minimal single-step `content`.
2. Polls `GET /api/consentRequests/{requestId}/status` (also with `X-API-Key`) until the user decides, the request stops being answerable, or the TTL elapses.
3. Exits **0** on `approved`, **1** on any other outcome (`rejected`, `withdrawn`, an expired or closed request, timeout, API error), **2** if no API key was provided.

The plaintext key is the only credential the skill uses.

> **After invocation, tell the user:**
> "A consent request has been sent to your Consent App. Please approve or reject it to continue."

### Act on the Decision

- **Exit 0 (`approved`)** → Proceed with the critical operation.
- **Exit 1 (`rejected`/`withdrawn`/expired or closed request/timeout/API error)** → **STOP**. Do NOT proceed. Inform the user that the operation was halted. One API error is worth distinguishing for the user:
  - `401 Unauthorized` → key was revoked or expired; ask for a fresh key.
- **Exit 2 (no API key)** → Ask the user for their Consent App API key and re-run.

## Key Management (Out of Scope)

Creating, listing, re-labelling, and revoking API keys are **user actions** performed in the Consent App mobile app — not from this skill.

If the user revokes the key, the next `request_consent.py` call returns 401 and exits 1; ask the user for a new key.

## Example Flows

### Sending an Email

1. Agent composes the email based on user instructions.
2. `python ./scripts/request_consent.py "Send email to client" "Send proposal email to anna@example.com with attached PDF (3 pages)."`
3. Exit 0 → agent sends the email.
   Exit 1 → email is discarded, agent informs user.

### Shopping Checkout

1. Agent searches and selects the product.
2. `python ./scripts/request_consent.py "Purchase: Nike Air Max" "Order 1× Nike Air Max 90, size 43, white/black, €149.99 from nike.com. Shipping to saved address, payment via saved credit card."`
3. Exit 0 → agent completes the checkout.

### Multi-Step Workflow with Approval Gates

Automated travel booking:

1. Agent searches flights/hotels.
2. `python ./scripts/request_consent.py "Book flight to Barcelona" "Lufthansa LH1234, 15 Apr 08:30 → 19 Apr 18:00, €289 economy."` → 0 ⇒ book flight.
3. `python ./scripts/request_consent.py "Book hotel in Barcelona" "Hotel Arts Barcelona, 4 nights, double room, €180/night (€720 total)."` → 0 ⇒ book hotel.

## Important Rules

- **NEVER skip the consent check** for operations marked as critical.
- **NEVER proceed after rejection or timeout** — non-approval means full stop.
- **ALWAYS write a precise description** — the user sees it verbatim and approves on that basis.
- **NEVER reuse a request_id across operations** — each critical operation needs its own consent request.
- **NEVER ask the user for their Consent App password.** The skill only ever needs the API key (`cak_...`) the user pasted from the mobile app.
- **NEVER persist the API key** beyond the agent's normal secret-storage mechanism (env var, secret manager). Do not write it to disk from this skill.

## API Reference

See [API Documentation](./references/api.md) for the `/api/consentRequests` endpoints used by the skill, [openapi.yaml](./references/openapi.yaml) for the generated OpenAPI 3.1 schema of those endpoints, and [architecture.md](./references/architecture.md) for the request flow diagram.
