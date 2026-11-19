# skills
Skill that gates critical or irreversible actions (payments, bookings, emails, sign-ups, checkouts) behind human approval via the Consent App. The agent creates a consent request with a user-provided API key (created at https://consent.app/portal/api-keys, scope "Create requests"); the user approves or rejects it in the Consent App mobile app — a human-in-the-loop safeguard for autonomous agents.

| What | Where |
|---|---|
| The skill | [`skills/consent-app/`](skills/consent-app/) — start with [`SKILL.md`](skills/consent-app/SKILL.md) |
| Installing it (Claude Code, Cowork, Agent SDK, OpenClaw) | [`INSTALL.md`](INSTALL.md) |
| API reference | [`references/api.md`](skills/consent-app/references/api.md), OpenAPI 3.1 in [`references/openapi.yaml`](skills/consent-app/references/openapi.yaml) |

`references/openapi.yaml` is a snapshot of `https://api.consent.app/api/openapi.yaml`. Refresh it with `tools/refresh_openapi.sh`; `--check` reports whether it is out of date.
