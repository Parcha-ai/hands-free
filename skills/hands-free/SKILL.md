---
name: hands-free
description: Phone-based input bridge for Codex hands-free mode. Use when the user says "activate hands free", "activate hands-free", "activate handsfree", "deactivate hands free", "hands free", or asks Codex to route future approval/input prompts to a phone call instead of waiting in chat.
---

# Hands Free

## Behavior

When the user activates hands-free mode, rely on the user-level Codex hooks in `~/.codex/hands-free/scripts/hands_free_hook.py` for the actual phone routing.

The hook handles:

- `UserPromptSubmit`: recognizes `activate`/`deactivate` with `hands free`, `hands-free`, or `handsfree`.
- `PermissionRequest`: calls the configured phone number for approve/deny decisions.
- `Stop`: when the assistant's final message looks like a question or request for user input, calls the configured phone number and feeds the phone response back into Codex as continuation context.

## Agent Guidance

- Do not ask the user to paste the Vapi key, phone number id, or destination phone number again unless the hook reports a missing configuration value.
- Prefer concise, phone-friendly questions. Use one direct question at a time.
- For approvals, expect the hook to ask for `approve`/`deny` or keypad `1`/`2`.
- For free-form input, expect speech-to-text to be imperfect. Ask short follow-up questions if the returned answer is ambiguous.
- To turn the mode off, tell the user to say `deactivate hands free`; `deactivate hands-free` and `deactivate handsfree` also work.

## Text To Audio

The hook sends a transient Vapi assistant in each outbound call. The assistant's `firstMessage` is the Codex question or approval prompt, and Vapi's voice provider converts that text to speech when the call connects. No local audio file is generated.

Vapi then transcribes the user's speech into `call.artifact.transcript`; the hook polls the call until it ends and extracts the user side of the transcript.
