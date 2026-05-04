# Codex Hands Free

Route Codex approval and input prompts to a phone call through Vapi.

[![skills.sh](https://skills.sh/b/Parcha-ai/hands-free)](https://skills.sh/Parcha-ai/hands-free)

## What It Does

- Activates when the user says `activate hands free`, `activate hands-free`, or `activate handsfree`.
- Deactivates when the user says `deactivate hands free`, `deactivate hands-free`, or `deactivate handsfree`.
- Calls the configured phone number for Codex permission requests.
- Calls the configured phone number when Codex ends with a question or input request.
- Uses Vapi text-to-speech for the prompt and Vapi transcription for the phone response.

## Requirements

- Codex with hooks enabled.
- Node.js 18+ for the npm installer, or Bash for the direct installer.
- Python 3.9+.
- A Vapi private API key.
- A Vapi phone number id.
- A destination phone number in E.164 format, such as `+15555550123`.

## Install

### npm

```bash
npx @parcha-ai/hands-free install
$EDITOR ~/.codex/hands-free/.env
```

Restart Codex after installing hooks.

Check setup without printing secrets:

```bash
npx @parcha-ai/hands-free doctor
```

### GitHub

```bash
git clone https://github.com/Parcha-ai/hands-free.git
cd hands-free
./install.sh
$EDITOR ~/.codex/hands-free/.env
```

Restart Codex after installing hooks.

### skills.sh

```bash
npx skills add Parcha-ai/hands-free --skill hands-free -a codex -g
```

The `skills.sh` path installs the skill instructions. Run the npm or GitHub installer as well when you want phone hooks wired into `~/.codex/hooks.json`.

### Codex Plugin

This repository is structured as a Codex plugin via `.codex-plugin/plugin.json` and includes `.agents/plugins/marketplace.json` for marketplace testing:

```bash
codex plugin marketplace add Parcha-ai/hands-free
```

Codex plugin hook loading is still changing, so the npm/GitHub installer remains the reliable hook setup path.

## Usage

```text
activate hands free
```

Equivalent forms such as `activate hands-free` and `activate handsfree` also work.

```text
deactivate hands free
```

Equivalent forms such as `deactivate hands-free` and `deactivate handsfree` also work.

## Notes

- The hook never stores API credentials in the skill directory.
- Approval calls accept spoken `approve`/`deny` or keypad `1`/`2`.
- Free-form phone replies depend on speech-to-text quality, so short answers work best.
- The default voice is Vapi `Elliot`; override `VAPI_VOICE_ID` in `~/.codex/hands-free/.env`.
- Prompt text and spoken replies are sent to Vapi for the call and transcript. Review your Vapi retention and artifact settings before using this with sensitive code or secrets.

## Publishing

Before publishing a release:

```bash
npm test
npm pack --dry-run
```

Publish the npm package with:

```bash
npm publish --access public
```
