# Installing the consent-app skill

The skill is a single portable folder, `skills/consent-app/` in this repo —
`SKILL.md` + `references/` + stdlib-only Python in `scripts/` (no pip
dependencies, no build step). The
same folder works across every runtime below; only the **install location**
and **where environment variables are set** differ.

## What any runtime needs

A runtime can host this skill if it can do three things:

1. **Discover** `SKILL.md` (load it as context / a tool description — the
   frontmatter `name` + `description` are the trigger).
2. **Execute** `python scripts/request_consent.py …` via a shell/bash tool.
3. **Inject** the env var into the script's environment.

## Configuration (all runtimes)

The backend endpoint is fixed at `https://api.consent.app` — nothing to
configure. The only variable is the user's key:

| Variable | Default | Description |
|----------|---------|-------------|
| `CONSENT_API_KEY` | _(unset)_ | Plaintext key `cak_...`. Required unless passed as `--api-key`. |

The user creates the key at https://consent.app/portal/api-keys with the scope
"Create requests" (see `SKILL.md`, *Getting an API Key*).

Never commit `CONSENT_API_KEY`; use the runtime's secret mechanism. A `.env`
in `scripts/` is git-ignored by the folder's own `.gitignore`.

---

## Claude Code

**Option A — drop-in (one project):** copy the folder into the project (or
`~/.claude/skills/` for user-wide):

```bash
git clone https://github.com/xlcloud-consentapp/skills consentapp-skills
cp -r consentapp-skills/skills/consent-app <your-project>/.claude/skills/consent-app
```

Set env in the project's `.claude/settings.json`:

```json
{ "env": { "CONSENT_API_KEY": "cak_…" } }
```

**Option B — plugin + marketplace (multiple projects, clean updates):** this
repo ships `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`
at its root, with the skill discovered from `skills/consent-app/`. Consumers:

```
/plugin marketplace add https://github.com/xlcloud-consentapp/skills
/plugin install consent-app@consent-app
```

---

## Claude Cowork

Identical to Claude Code — Cowork uses the same Agent Skills mechanism.

- **Install:** drop the folder in `~/.claude/skills/consent-app/` (picked up
  automatically), or install the plugin as above.
- **Env:** set `CONSENT_API_KEY` in the shell/desktop environment Cowork
  runs under.

---

## Claude Agent SDK

Load the skill directory as an SDK skill asset and run the script with the
env var set in the agent's process environment. Same folder, no changes.

---

## OpenClaw

OpenClaw uses the **same `SKILL.md` format** in its own skills registry. The
skill's frontmatter already declares `metadata.openclaw.primaryEnv:
CONSENT_API_KEY` so OpenClaw knows which env var is the key (other runtimes
ignore the extra metadata).

**Install — drop-in.** Copy the folder into one of OpenClaw's skill roots
(highest priority first):

| Location | Scope |
|----------|-------|
| `<workspace>/skills/consent-app/` | this workspace/agent only (highest priority) |
| `~/.openclaw/skills/consent-app/` | all local agents/workspaces |

```bash
cp -r skills/consent-app ~/.openclaw/skills/consent-app
```

**Env / secrets.** Configure operator-side in `~/.openclaw/openclaw.json`
under `skills.entries.<slug>`:

```json
{
  "skills": {
    "entries": {
      "consent-app": {
        "apiKey": { "source": "env", "provider": "default", "id": "CONSENT_API_KEY" }
      }
    }
  }
}
```

- `apiKey` is injected into the agent run (only if not already set in the process).
- **Per-agent keys:** scope visibility with `agents.defaults.skills` /
  `agents.list[].skills` (explicit lists *replace* defaults, they don't merge)
  and give each agent its own `skills.entries` values — e.g. a different
  `CONSENT_API_KEY` per agent.
- **⚠️ Sandbox caveat:** if the agent runs inside a Docker sandbox,
  `skills.entries.<slug>.apiKey` has **no effect** — pass the secret via
  `agents.defaults.sandbox.docker.env` instead.
- **⚠️ Non-Claude backends:** the `description`-based auto-trigger is an
  Anthropic convention. If OpenClaw runs the skill behind a non-Claude model
  (GPT/Gemini), reference the skill explicitly in the agent's `TOOLS.md` /
  `AGENTS.md` so it gets loaded.

### Future: publishing to ClawHub

ClawHub is OpenClaw's public skill registry (`clawhub skill publish …` →
`openclaw skills install consent-app`). The skill is not published there
yet; install it from this repo.
