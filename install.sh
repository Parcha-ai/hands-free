#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
HOOK_SOURCE="$ROOT_DIR/skills/hands-free/scripts/hands_free_hook.py"

HARNESS="${HANDS_FREE_HARNESS:-auto}"
for arg in "$@"; do
  case "$arg" in
    --harness=*)
      HARNESS="${arg#--harness=}"
      ;;
    --claude-code)
      HARNESS="claude-code"
      ;;
    --codex)
      HARNESS="codex"
      ;;
  esac
done

# Auto-detect: prefer Claude Code if ~/.claude exists, else codex, else claude default.
if [[ "$HARNESS" == "auto" ]]; then
  if [[ -d "$HOME/.claude" ]]; then
    HARNESS="claude-code"
  elif [[ -d "$HOME/.codex" ]]; then
    HARNESS="codex"
  else
    HARNESS="claude-code"
  fi
fi

case "$HARNESS" in
  claude-code)
    HARNESS_HOME="${CLAUDE_HOME:-$HOME/.claude}"
    ;;
  codex)
    HARNESS_HOME="${CODEX_HOME:-$HOME/.codex}"
    ;;
  *)
    echo "Unknown harness: $HARNESS (expected claude-code or codex)" >&2
    exit 1
    ;;
esac

HANDS_FREE_HOME="$HARNESS_HOME/hands-free"
SKILL_HOME="$HARNESS_HOME/skills/hands-free"

install -d -m 700 "$HANDS_FREE_HOME/scripts" "$SKILL_HOME/agents" "$SKILL_HOME/scripts"
install -m 700 "$HOOK_SOURCE" "$HANDS_FREE_HOME/scripts/hands_free_hook.py"
install -m 644 "$ROOT_DIR/skills/hands-free/SKILL.md" "$SKILL_HOME/SKILL.md"
install -m 644 "$ROOT_DIR/skills/hands-free/agents/openai.yaml" "$SKILL_HOME/agents/openai.yaml"
install -m 700 "$HOOK_SOURCE" "$SKILL_HOME/scripts/hands_free_hook.py"

if [[ ! -f "$HANDS_FREE_HOME/.env" ]]; then
  install -m 600 "$ROOT_DIR/.env.example" "$HANDS_FREE_HOME/.env"
fi

# Wire hooks into the harness-specific settings file.
"$PYTHON_BIN" - "$HARNESS" "$HARNESS_HOME" "$PYTHON_BIN" <<'PY'
import json
import pathlib
import shlex
import sys

harness = sys.argv[1]
harness_home = pathlib.Path(sys.argv[2]).expanduser()
python_bin = sys.argv[3]
hook_path = harness_home / "hands-free" / "scripts" / "hands_free_hook.py"
command = (
    f"HANDS_FREE_HARNESS={shlex.quote(harness)} "
    f"{shlex.quote(python_bin)} {shlex.quote(str(hook_path))}"
)

if harness == "claude-code":
    settings_path = harness_home / "settings.json"
    permission_event = "PreToolUse"
    permission_status = "Hands-free phone approval"
else:
    settings_path = harness_home / "hooks.json"
    permission_event = "PermissionRequest"
    permission_status = "Calling for hands-free approval"

desired = {
    "UserPromptSubmit": [{
        "hooks": [{"type": "command", "command": command, "timeout": 10}]
    }],
    permission_event: [{
        "matcher": ".*",
        "hooks": [{
            "type": "command",
            "command": command,
            "statusMessage": permission_status,
            "timeout": 220,
        }],
    }],
    "Stop": [{
        "hooks": [{
            "type": "command",
            "command": command,
            "statusMessage": "Checking hands-free phone input",
            "timeout": 240,
        }],
    }],
}

if settings_path.exists():
    data = json.loads(settings_path.read_text())
else:
    data = {}

hooks = data.setdefault("hooks", {})
for event_name, entries in desired.items():
    existing_entries = hooks.setdefault(event_name, [])
    filtered_entries = []
    for entry in existing_entries:
        entry_hooks = entry.get("hooks", []) if isinstance(entry, dict) else []
        if any("hands-free/scripts/hands_free_hook.py" in str(hook.get("command", "")) for hook in entry_hooks if isinstance(hook, dict)):
            continue
        filtered_entries.append(entry)
    hooks[event_name] = filtered_entries + entries

settings_path.write_text(json.dumps(data, indent=2) + "\n")
settings_path.chmod(0o600)
PY

# Codex needs codex_hooks=true in config.toml. Claude Code does not.
if [[ "$HARNESS" == "codex" ]]; then
"$PYTHON_BIN" - "$HARNESS_HOME" <<'PY'
import pathlib
import sys

config_path = pathlib.Path(sys.argv[1]).expanduser() / "config.toml"
text = config_path.read_text() if config_path.exists() else ""
if "[features]" not in text:
    text = text.rstrip() + "\n\n[features]\ncodex_hooks = true\n"
else:
    lines = text.splitlines()
    in_features = False
    saw_codex_hooks = False
    output = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_features and not saw_codex_hooks:
                output.append("codex_hooks = true")
                saw_codex_hooks = True
            in_features = stripped == "[features]"
        if in_features and stripped.startswith("codex_hooks"):
            output.append("codex_hooks = true")
            saw_codex_hooks = True
            continue
        output.append(line)
    if in_features and not saw_codex_hooks:
        output.append("codex_hooks = true")
    text = "\n".join(output) + "\n"
config_path.write_text(text)
config_path.chmod(0o600)
PY
fi

echo "Installed hands-free skill and hooks for $HARNESS (under $HARNESS_HOME)."
echo "Edit $HANDS_FREE_HOME/.env, then restart your assistant."
