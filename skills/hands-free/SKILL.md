---
name: hands-free
description: Phone-based input bridge for AI coding assistants. Use when the user says "activate hands free", "activate hands-free", "activate handsfree", "deactivate hands free", "hands free", or asks the assistant to route future approval/input prompts to a phone call instead of waiting in chat. Works with Claude Code and Codex.
---

# Hands Free

## Behavior

When the user activates hands-free mode, the underlying hook (installed at `<harness home>/hands-free/scripts/hands_free_hook.py`) handles all phone routing. The harness — Claude Code or Codex — is passed to the hook via the `HANDS_FREE_HARNESS` env var by the installer, so the same script produces the right decision shape for each.

The hook reacts to three events:

- `UserPromptSubmit`: recognizes `activate`/`deactivate` paired with `hands free`, `hands-free`, or `handsfree`.
- Permission gate (`PreToolUse` on Claude Code, `PermissionRequest` on Codex): calls the configured phone number for an approve/deny decision.
- `Stop`: when the assistant's final message looks like a question or request for user input, calls the configured phone number and feeds the phone response back as continuation context.

## Agent Guidance

- Do not ask the user to paste the Vapi key, phone number id, or destination phone number again unless the hook reports a missing configuration value.
- Prefer concise, phone-friendly questions. One direct question at a time.
- For approvals, expect the hook to ask for `approve`/`deny` or keypad `1`/`2`.
- For free-form input, expect speech-to-text to be imperfect. Ask short follow-up questions if the returned answer is ambiguous.
- To turn the mode off, tell the user to say `deactivate hands free`; `deactivate hands-free` and `deactivate handsfree` also work.

## Text To Audio

The hook sends a transient Vapi assistant in each outbound call. The assistant's `firstMessage` is the question or approval prompt, and Vapi's voice provider converts that text to speech when the call connects. No local audio file is generated.

Vapi then transcribes the user's speech into `call.artifact.transcript`; the hook polls the call until it ends and extracts the user side of the transcript.
