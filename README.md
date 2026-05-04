# Codex Hands Free

Route Codex approval and input prompts to a phone call through Vapi.

[![skills.sh](https://skills.sh/b/Parcha-ai/hands-free)](https://skills.sh/Parcha-ai/hands-free)

## What It Does

- Say `activate hands free` to start, `deactivate hands free` to stop.
- Codex permission requests and input prompts ring your phone via Vapi.
- Approve with spoken `approve`/`deny` or keypad `1`/`2`.

## Requirements

- Codex with hooks enabled
- Node.js 18+ and Python 3.9+
- A Vapi private API key, phone number id, and a destination number in E.164 format (e.g. `+15555550123`)

## Install

```bash
npx @parcha/hands-free install
$EDITOR ~/.codex/hands-free/.env
```

Restart Codex. Verify setup with:

```bash
npx @parcha/hands-free doctor
```

## Notes

- API credentials live only in `~/.codex/hands-free/.env`.
- The default voice is Vapi `Elliot`; override `VAPI_VOICE_ID` in the env file.
- Prompt text and spoken replies are sent to Vapi. Review your Vapi retention settings before using with sensitive code.

## Publishing

```bash
npm test
npm publish --access public
```
