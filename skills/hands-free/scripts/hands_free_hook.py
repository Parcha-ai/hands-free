#!/usr/bin/env python3
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request


CODEX_HOME = pathlib.Path(os.environ.get("CODEX_HOME", pathlib.Path.home() / ".codex")).expanduser()
BASE_DIR = CODEX_HOME / "hands-free"
ENV_PATH = BASE_DIR / ".env"
STATE_PATH = BASE_DIR / "state.json"
API_BASE = "https://api.vapi.ai"
HANDS_FREE_RE = re.compile(r"\bhands[-\s]?free\b")


def load_env():
    env = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    env.update({key: value for key, value in os.environ.items() if key.startswith("VAPI_") or key.startswith("HANDS_FREE_")})
    return env


def load_state():
    if not STATE_PATH.exists():
        return {"active": False}
    try:
        return json.loads(STATE_PATH.read_text())
    except json.JSONDecodeError:
        return {"active": False}


def save_state(state):
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
    os.chmod(STATE_PATH, 0o600)


def stdout_json(payload):
    print(json.dumps(payload))


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def mentions_hands_free(text):
    return bool(HANDS_FREE_RE.search(text))


def has_command(text, verbs):
    if not mentions_hands_free(text):
        return False
    return any(re.search(rf"\b{verb}\b", text) for verb in verbs)


def read_hook_input():
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def vapi_request(method, path, api_key, payload=None, timeout=30):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "codex-hands-free/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read().decode("utf-8")
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Vapi HTTP {error.code}: {detail[:500]}") from error


def build_assistant(message, purpose):
    env = load_env()
    if purpose == "approval":
        first_message = (
            "Your code assistant needs approval. "
            f"{message} "
            "Say approve or deny, or press 1 or 2."
        )
        system_message = (
            "You are a phone bridge for a code assistant's approval prompts. Capture exactly one approval decision. "
            "If the user says approve, yes, one, or presses 1, acknowledge approval and say exactly: ending call now. "
            "If the user says deny, no, two, or presses 2, acknowledge denial and say exactly: ending call now. "
            "Do not discuss the coding task."
        )
        max_duration = 75
    else:
        first_message = (
            f"Your code assistant needs input. {message}"
        )
        system_message = (
            "You are a phone bridge for a code assistant. Capture the user's answer to the code assistant's question. "
            "Do not answer the question yourself. Do not ask unrelated follow-up questions. "
            "When the user gives an answer, acknowledge briefly and say exactly: ending call now."
        )
        max_duration = 150

    return {
        "name": "Hands Free Code Assistant Bridge",
        "firstMessage": first_message[:1800],
        "firstMessageMode": "assistant-speaks-first",
        "model": {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "temperature": 0,
            "maxTokens": 120,
            "messages": [{"role": "system", "content": system_message}],
        },
        "voice": {
            "provider": "vapi",
            "voiceId": env.get("VAPI_VOICE_ID", "Elliot"),
            "speed": 1,
        },
        "backgroundSound": "off",
        "maxDurationSeconds": max_duration,
        "endCallPhrases": ["ending call now"],
        "artifactPlan": {
            "recordingEnabled": False,
            "loggingEnabled": False,
            "transcriptPlan": {
                "enabled": True,
                "assistantName": "Code assistant",
                "userName": "User",
            },
        },
        "keypadInputPlan": {
            "enabled": True,
            "timeoutSeconds": 2,
            "delimiters": ["#"],
        },
    }


def call_for_input(message, purpose, raw_call=False):
    env = load_env()
    api_key = env.get("VAPI_API_KEY")
    phone_number_id = env.get("VAPI_PHONE_NUMBER_ID")
    hands_free_phone_number = env.get("HANDS_FREE_PHONE_NUMBER")
    if not api_key or not phone_number_id or not hands_free_phone_number:
        raise RuntimeError("Missing VAPI_API_KEY, VAPI_PHONE_NUMBER_ID, or HANDS_FREE_PHONE_NUMBER")

    payload = {
        "name": f"Hands free {purpose}",
        "phoneNumberId": phone_number_id,
        "customer": {"number": hands_free_phone_number, "name": "Hands free user"},
        "assistant": build_assistant(message, purpose),
    }
    created = vapi_request("POST", "/call", api_key, payload, timeout=30)
    call_id = created.get("id")
    if not call_id:
        raise RuntimeError("Vapi did not return a call id")

    deadline = time.monotonic() + 190
    call = created
    while time.monotonic() < deadline:
        time.sleep(3)
        call = vapi_request("GET", f"/call/{call_id}", api_key, timeout=20)
        if call.get("status") == "ended" or call.get("endedAt"):
            return call if raw_call else extract_answer(call)
    raise RuntimeError(f"Timed out waiting for Vapi call {call_id}")


def extract_user_answer(call, allow_unattributed=False):
    artifact = call.get("artifact") or {}
    messages = artifact.get("messages") or call.get("messages") or []
    user_parts = []
    for item in messages:
        role = normalize(str(item.get("role") or item.get("speaker") or item.get("type")))
        content = item.get("message") or item.get("content") or item.get("transcript") or item.get("text")
        if content and any(token in role for token in ("user", "customer", "caller")):
            user_parts.append(str(content).strip())
    if user_parts:
        return " ".join(user_parts).strip()

    transcript = artifact.get("transcript") or call.get("transcript") or ""
    user_lines = []
    for line in transcript.splitlines():
        if re.match(r"^\s*(user|customer|caller)\s*:", line, re.I):
            user_lines.append(re.sub(r"^\s*(user|customer|caller)\s*:\s*", "", line, flags=re.I).strip())
    if user_lines:
        return " ".join(user_lines).strip()
    if allow_unattributed:
        return transcript.strip()
    return ""


def extract_answer(call):
    return extract_user_answer(call, allow_unattributed=True)


def approval_decision(answer):
    text = normalize(answer)
    if re.search(r"\b(deny|denied|decline|reject|rejected|no|two|2)\b", text):
        return "deny"
    if re.search(r"\b(approve|approved|allow|allowed|yes|yep|yeah|one|1)\b", text):
        return "allow"
    return None


def extract_last_agent_message(transcript_path):
    if not transcript_path:
        return ""
    path = pathlib.Path(transcript_path)
    if not path.exists():
        return ""
    last_message = ""
    for line in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload") or {}
        if event.get("type") == "event_msg" and payload.get("type") in ("agent_message", "task_complete"):
            last_message = payload.get("message") or payload.get("last_agent_message") or last_message
        if event.get("type") == "response_item":
            item = payload
            if item.get("type") == "message" and item.get("role") == "assistant":
                content = item.get("content") or []
                texts = [part.get("text", "") for part in content if isinstance(part, dict)]
                if texts:
                    last_message = "\n".join(texts)
    return last_message.strip()


def looks_like_input_request(message):
    text = normalize(message)
    if not text:
        return False
    request_patterns = [
        r"\?",
        r"\b(would you like|do you want|should i|can you confirm|please confirm)\b",
        r"\b(which|what|who|where|when|how) .+\b",
        r"\b(provide|send|share|choose|select|pick|confirm|approve|deny)\b",
        r"\b(i need|need you to|waiting for|let me know)\b",
    ]
    completion_patterns = [
        r"\b(done|completed|finished|implemented|verified|stored it|set up)\b",
    ]
    if any(re.search(pattern, text) for pattern in request_patterns):
        return True
    if any(re.search(pattern, text) for pattern in completion_patterns):
        return False
    return False


def handle_user_prompt_submit(hook_input, state):
    prompt = normalize(hook_input.get("prompt", ""))
    if has_command(prompt, ("deactivate", "disable", "stop")) or (re.search(r"\bturn off\b", prompt) and mentions_hands_free(prompt)):
        save_state({"active": False, "deactivated_at": time.time()})
        stdout_json({"continue": True, "systemMessage": "Hands-free mode deactivated."})
        return
    if has_command(prompt, ("activate", "enable", "start")) or (re.search(r"\bturn on\b", prompt) and mentions_hands_free(prompt)):
        save_state({"active": True, "activated_at": time.time()})
        stdout_json({
            "continue": True,
            "systemMessage": "Hands-free mode activated. Future approval and input requests will be routed by phone.",
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": (
                    "Hands-free mode is active. Avoid asking for input in chat when possible; "
                    "final questions will be routed through the hands-free phone hook."
                ),
            },
        })
        return
    if state.get("active"):
        stdout_json({
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "Hands-free mode is active; route approval and input requests through the configured phone hook.",
            },
        })


def handle_permission_request(hook_input, state):
    if not state.get("active"):
        return
    tool_name = hook_input.get("tool_name", "tool")
    description = hook_input.get("tool_input", {}).get("description")
    command = hook_input.get("tool_input", {}).get("command")
    message = description or command or f"Codex wants approval to use {tool_name}."
    try:
        call = call_for_input(message, "approval", raw_call=True)
        answer = extract_user_answer(call, allow_unattributed=False)
        decision = approval_decision(answer)
    except Exception as error:
        stdout_json({"systemMessage": f"Hands-free phone approval failed: {error}"})
        return
    if decision in ("allow", "deny"):
        stdout_json({
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {
                    "behavior": decision,
                    "message": f"Hands-free phone response: {decision}",
                },
            }
        })
        return
    stdout_json({"systemMessage": "Hands-free phone approval was ambiguous; falling back to normal Codex approval."})


def handle_stop(hook_input, state):
    if not state.get("active") or hook_input.get("stop_hook_active"):
        return
    last_message = hook_input.get("last_assistant_message") or extract_last_agent_message(hook_input.get("transcript_path"))
    if not looks_like_input_request(last_message):
        return
    try:
        answer = call_for_input(last_message, "input")
    except Exception as error:
        stdout_json({"systemMessage": f"Hands-free phone input failed: {error}"})
        return
    if not answer:
        stdout_json({"systemMessage": "Hands-free phone input returned no transcript; leaving the chat question visible."})
        return
    stdout_json({
        "decision": "block",
        "reason": (
            "Hands-free mode received this phone response from the user. "
            f"Treat it as the user's reply and continue: {answer}"
        ),
    })


def main():
    hook_input = read_hook_input()
    state = load_state()
    event_name = hook_input.get("hook_event_name") or hook_input.get("hookEventName")
    if event_name == "UserPromptSubmit":
        handle_user_prompt_submit(hook_input, state)
    elif event_name == "PermissionRequest":
        handle_permission_request(hook_input, state)
    elif event_name == "Stop":
        handle_stop(hook_input, state)


if __name__ == "__main__":
    main()
