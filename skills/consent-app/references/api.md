# Consent App API Reference (Skill View)

This document covers only the endpoints used by the **consent-app skill**.

Base URL: `https://api.consent.app`.

A machine-readable OpenAPI 3.1 description of these same three endpoints lives beside this
file in [`openapi.yaml`](./openapi.yaml). It is generated from the backend handlers, so it
is the one to check a request or response shape against; this document is the prose that
explains the parts a schema cannot carry.

## Authentication

The skill uses a **user-managed API key** exclusively. The Consent App
user creates the key in the mobile app and provides the plaintext
(`cak_...`) to the agent runtime — the skill never signs the user in
and never calls `/api/keys`.

| Method | Header | Used by |
|--------|--------|---------|
| User API Key | `X-API-Key: cak_<key>` | `POST /api/consentRequests`, `GET /api/consentRequests/{id}/status`, `GET /api/consentRequests/{id}` |

The plaintext key has the shape `cak_...` (e.g. `cak_AbCd...`).

The backend stores only the SHA-256 hash of the full plaintext — the
plaintext is returned to
the user exactly once at creation time and never persisted. The key is
scoped to the user that created it: it can only create consent
requests addressed to that user, and only read responses to requests
the same key created.

Key creation, listing, re-labelling, and revocation are user actions
performed in the Consent App mobile app. They are out of scope for the
skill.

---

## `POST /api/consentRequests`

Create a consent request addressed to the API key's owning user.

**Auth:** `X-API-Key: cak_...`

**Request:**
```json
{
  "title": "Purchase: Nike Air Max",
  "shortDescription": "Purchase: Nike Air Max",
  "description": "Order 1× Nike Air Max 90, size 43, €149.99 from nike.com.",
  "ttlSec": 60,
  "content": { "steps": [ { "title": "Consent", "fields": [] } ] }
}
```

**Required:** `title` and `content`. `content` must hold at least one step
(`content.steps`, 1–20 of them); a step's `fields` may be absent or empty, and
that is what the skill sends — one field-less step, which renders just the
title/description with no form to fill.

**Optional but expected:** `shortDescription` is the plain-text line the mobile
inbox list shows, `description` the full text the user reads before deciding.

Text limits, counted in grapheme clusters: `title` ≤ 300, `shortDescription`
≤ 1000, `description` ≤ 10000. `description` is Markdown (headings, bold,
italic, underline, lists), but **links and images are refused with 400** — a
bare URL in prose is fine and renders inert.

`ttlSec` is the lifetime in seconds — positive, at most one year. `expiresAt`
(RFC3339, in the future, at most one year out) is the same lifetime spelled as an
instant; sending both is 400, as is a negative or out-of-range value — nothing is
clamped. Omitting both defaults to **300** (5 minutes), which is the agent-gate
shape; days to months is the other, for a consent distributed to people.

One more field is accepted and rarely wanted from an agent: `withdrawable`
(default `false`) lets the user revoke an approval afterwards, and is the only
way a request can ever read `withdrawn`.

Rejected with 400 on this endpoint: `ftSignature` and `ftIdentityDocument` fields.
The user produces both in the mobile app, but their answers are file references and this
API has no endpoint that downloads a file — asking for one would collect a signature or an
identity document from the user that you could never read back.

To collect structured answers, populate `content.steps[].fields[]`. A field
requires `type` and `label` (≤ 80 graphemes); `type` is one of `ftTextInput`,
`ftMultilineTextInput`, `ftNumberInput`, `ftChoice`, `ftCheckbox`, `ftDate`,
`ftEmail`, `ftName`, `ftAddress`, `ftPhoneNumber`. Optional
per field: `properties` (`"optional"` and/or `"revocable"` — a field is required
and non-revocable by default), `placeholder`, `maxLength`, `minValue`/`maxValue`,
`options` (required for `ftChoice`), and `vaultRef` — see *Vault* below.

The recipient is implicit — it is always the user that owns the calling API key, never accepted from the wire.

**Response (201):**
```json
{
  "requestId": "uuid",
  "createdAt": "2026-05-17T10:00:00Z",
  "expiresAt": "2026-05-17T10:01:00Z"
}
```

The deep link for the consent request is `https://consent.app/approve/<requestId>` (the mobile app receives a push notification regardless).

---

## Vault

The **vault** is the user's own store of structured personal data inside the
Consent App — one per user, filled and maintained by them. It holds records in
typed slots: `vsName`, `vsAddress`, `vsEmail`, `vsPhoneNumber`, `vsDateOfBirth`,
`vsIdentityDocument`, `vsSignature`. A slot can hold several records (a home and
a work address, say), one of them primary, and a record can carry a verification
status.

A field in your `content` may bind to a slot:

```json
{ "type": "ftAddress", "label": "Delivery address", "vaultRef": { "slot": "vsAddress" } }
```

The binding means the app offers the user's stored value when they open the
request, instead of making them type it, and writes an edited value back to the
vault. A field without `vaultRef` is always filled by hand. The slot must match
the field type (`vsAddress` with `ftAddress`, `vsEmail` with `ftEmail`, …);
`vsSignature` and `vsIdentityDocument` are unusable here, since the field types that
bind to them are rejected. `slot` is the only key a `vaultRef` takes.

For an agent the vault is write-nothing, read-nothing: there is no vault
endpoint on this surface, and a `vaultRef` only asks the app to prefill — the
user still decides what to submit. What comes back is the submitted answer,
marked `fromVault: true` with its `verificationStatus` when it came from there.

---

## `GET /api/consentRequests/{id}/status`

Poll this one endpoint for the outcome. It answers both questions a waiting caller
has: what the user decided, and whether the request can still be decided at all.

**Auth:** `X-API-Key: cak_...` (must be the same key that created the request)

**Response (200):**
```json
{ "status": "pending", "lifecycleStatus": "active" }
```

**`status`** is the decision: `pending`, `approved`, `rejected`, `withdrawn`. It stays
`pending` until the user acts in the mobile app, then mirrors what they chose.

**`lifecycleStatus`** is whether the request is still answerable: `active`, `expired`
(its `expiresAt` passed), or `closed` (the user closed it). It is present **only while
`status` is `pending`** — once a decision exists the request's lifecycle no longer
matters and the field is omitted.

So a polling caller stops on either signal:

- **`status` is no longer `pending`** — the user decided. Act on the decision.
- **`status` is `pending` and `lifecycleStatus` is `expired` or `closed`** — no decision
  is ever coming. Stop waiting and do **not** proceed; this is not consent.

**`withdrawn` only occurs when the request was created with `withdrawable: true`.**
Otherwise a decision is final and the status never changes again.

**Error responses** carry a JSON body on every failure:

```json
{ "error": "key_revoked", "message": "api key revoked" }
```

`error` is a stable code to branch on; `message` is prose for a human and may be reworded
at any time. Do not match on `message`.

- `401` — `key_revoked` or `key_expired` mean the key is finished and the user must issue
  a new one in the mobile app. `missing_api_key` or `invalid_api_key` mean the caller never
  sent a usable key, so asking the user for a fresh one will not help — fix the call.
- `404` — `not_found`: the request id is unknown **or** was created by a different API key.
  Keys can only see their own requests, and the two cases are deliberately
  indistinguishable.
- `400` (on `POST /api/consentRequests`) — `missing_required_field`,
  `invalid_request_body`, `invalid_content`, `field_type_not_supported` (a field asks for
  something this API cannot carry — the message names the type) or `unsupported_property`
  (the body carries a property this API does not take). The request was malformed; retrying
  it unchanged will fail the same way.

---

## `GET /api/consentRequests/{id}`

Same authorisation as `/status`, but also returns the full response document — use it
when you want the user's answers, not just the outcome.

**Response (200) while waiting:**
```json
{
  "status": "pending",
  "response": {
    "responseId": "uuid",
    "requestId": "uuid",
    "status": "pending",
    "lifecycleStatus": "active",
    "history": [ { "status": "pending", "timestamp": "2026-05-17T10:00:00Z" } ],
    "updatedAt": "2026-05-17T10:00:00Z"
  }
}
```

A pending shell is created alongside the request itself, so `response` is normally present
and undecided before the user has touched anything — it is what puts the request in their
mobile inbox. Creating it is best-effort, so `"response": null` is still possible; read it
as meaning exactly what a pending `status` means.

**Response (200) once mobile decided:**
```json
{
  "status": "approved",
  "response": {
    "responseId": "uuid",
    "requestId": "uuid",
    "requestUserId": "uid",
    "requestUserDisplayName": "shopping-bot",
    "requestApiKeyId": "abcd-1234",
    "requesterKind": "agent",
    "requestTitle": "Purchase: Nike Air Max",
    "requestExpiresAt": "2026-05-17T10:01:00Z",
    "responseUserId": "uid",
    "responseUserDisplayName": "Anna",
    "status": "approved",
    "history": [/* ScopedHistoryEntry, as above */],
    "updatedAt": "2026-05-17T10:00:05Z"
  }
}
```

`requestTitle` and `requestExpiresAt` are denormalized snapshots of
the linked consent request, copied at response-creation time so
clients can render without a per-row request fetch.

### Lifecycle status

`lifecycleStatus` is a second, independent axis from `status`. Where `status` records what
the *user decided*, `lifecycleStatus` records whether the *request is still answerable*:

| Value | Meaning |
|-------|---------|
| `active` | Still open; the user can still decide. |
| `expired` | `expiresAt` passed with no decision. Nothing can be answered any more. |
| `closed` | The user closed the request from the app before it expired. |

Two rules govern reading it:

- **It is only set while the response is pending.** Once the user decides, the field is
  omitted entirely — a resolved response has no lifecycle. Its absence on an `approved` or
  `rejected` response is normal and is not an error.
- **`closed` wins over `expired`.** A request closed before its deadline stays `closed`.

Both endpoints report it: `/status` returns it as a top-level `lifecycleStatus`, and this
endpoint nests it on the response document. A caller that only needs to know whether to keep
waiting can poll `/status` alone.

```json
{
  "status": "pending",
  "response": { "status": "pending", "lifecycleStatus": "expired" }
}
```

Treat `expired` and `closed` exactly as the skill treats a timeout — a non-decision. Neither
is consent, so the gated operation must not proceed.

The skill normally only needs `/status`. Use this endpoint when you also want
the user's answers, which live in `response.history[]` — each entry carries its
`status`, `timestamp` and `providedFields[]`.

A provided field addresses its field positionally, by `stepIndex` and
`fieldIndex` into the `content` you sent (fields have no ids), and carries a
`value` holding whichever of `text`, `number`, `bool` or `fields` (a component
map, e.g. the parts of an address) matches the field type — plus `fromVault` and
`verificationStatus` when the user filled it from their vault. The schema also
declares `objectRefs`, but it is never populated here: it holds file references,
and the only two field types that produce one are rejected at create.
