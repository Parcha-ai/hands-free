# Hands Free

Route AI coding-assistant approval and input prompts to a phone call through Vapi. Works with **Claude Code** and **OpenAI Codex**.

[![skills.sh](https://skills.sh/b/Parcha-ai/hands-free)](https://skills.sh/Parcha-ai/hands-free/hands-free)

## What It Does

- Say `activate hands free` to start, `deactivate hands free` to stop.
- The assistant's permission requests and end-of-turn questions ring your phone via Vapi.
- Approve with spoken `approve`/`deny` or keypad `1`/`2`. Free-form questions accept any spoken answer.

## Requirements

- Claude Code, or Codex with hooks enabled
- Node.js 18+ and Python 3.9+
- A Vapi private API key, phone number id, and a destination number in E.164 format (e.g. `+15555550123`)

## Install

```bash
npx @parcha/hands-free install            # auto-detects Claude Code vs Codex
# or pick one explicitly:
npx @parcha/hands-free install --harness=claude-code
npx @parcha/hands-free install --harness=codex
```

Auto-detection prefers `~/.claude` when present, otherwise `~/.codex`. Then fill in the env file the installer dropped:

```bash
# Claude Code:
$EDITOR ~/.claude/hands-free/.env
# Codex:
$EDITOR ~/.codex/hands-free/.env
```

Restart your assistant. Verify with:

```bash
npx @parcha/hands-free doctor
```

## How It Works

The installer drops a single Python hook script (`hands_free_hook.py`) under the harness's home directory and wires it into three hook events:

| Event | Claude Code | Codex | What it does |
|---|---|---|---|
| `UserPromptSubmit` | ✓ | ✓ | Detects `activate`/`deactivate hands free` and toggles state. |
| Permission gate | `PreToolUse` | `PermissionRequest` | When active, places an outbound Vapi call asking for `approve`/`deny`. |
| `Stop` | ✓ | ✓ | When the final assistant message looks like a question, calls you for a spoken answer and feeds the transcript back as the user's reply. |

The same hook script runs under both harnesses; it shapes its stdout decision payload based on `HANDS_FREE_HARNESS` (set by the installer in the hook command).

## File Layout After Install

```
<harness home>/                # ~/.claude or ~/.codex
├── hands-free/
│   ├── .env                   # your Vapi credentials (chmod 600)
│   ├── state.json             # active/inactive flag
│   └── scripts/hands_free_hook.py
├── skills/hands-free/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   └── scripts/hands_free_hook.py
├── settings.json              # Claude Code only — hooks block
├── hooks.json                 # Codex only
└── config.toml                # Codex only — adds [features] codex_hooks = true
```

## Notes

- API credentials live only in `<harness home>/hands-free/.env` (mode 600).
- The default voice is Vapi `Elliot`; override `VAPI_VOICE_ID` in the env file.
- Prompt text and spoken replies are sent to Vapi. Review your Vapi retention settings before using with sensitive code.
- The hook never reads or modifies anything outside its own subtree; existing entries in `settings.json` / `hooks.json` are preserved.

## Manual Install (without npx)

If you'd rather wire it up yourself, copy `scripts/hands_free_hook.py` to a location your assistant can run, and use one of the templates in `examples/`:

- `examples/claude-settings.json` — Claude Code hooks block
- `examples/hooks.json` — Codex hooks block
- `examples/config.toml` — Codex `codex_hooks = true` feature flag

## Publishing

```bash
npm test
npm publish --access public
```
