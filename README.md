# Cyrano

A macOS desktop study companion for coding-interview practice. Capture a problem from
your screen or clipboard with a hotkey, and Claude (via AWS Bedrock) streams help into a small
always-on-top window. The default **Coach** mode gives you a *hint ladder* instead of the answer,
so you do the thinking.

## Modes

Cycle with `Ctrl+Shift+P`.

| Mode | What you get |
|---|---|
| **Coach** (default) | Hint 1 of 5 only. Press `Ctrl+Shift+H` for the next rung: nudge → key insight → approach → complexity → solution. Type your own approach in the follow-up box and the coach critiques it like an interviewer. |
| Solve | Full write-up: problem, approach, complexity, code. Use it for reviewing after you've attempted a problem. |
| Debug | What the error means, root cause, fix. |
| System Design | Requirements, high-level design, components, trade-offs. |
| Behavioral | Practise structuring a STAR answer. |

## Hotkeys

| Keys | Action |
|---|---|
| `Ctrl+Shift+Space` | Capture the full screen |
| `Ctrl+Shift+S` | Drag to select a region |
| `Ctrl+Shift+Enter` | Send clipboard text |
| `Ctrl+Shift+H` | Next hint (Coach mode) |
| `Ctrl+Shift+P` | Cycle mode |
| `Ctrl+\` | Show / hide the window |
| `Ctrl+Arrow` | Move the window |

Edit them in `config.py` (`HOTKEYS`, pynput `HotKey` syntax).

## Setup

Requires macOS and Python 3.10+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**AWS:** you need Bedrock access to a Claude model in your account. Credentials come from the
standard AWS chain (env vars, `~/.aws/credentials`, SSO…). Optional overrides:

| Variable | Default |
|---|---|
| `CYRANO_AWS_PROFILE` | default credential chain |
| `CYRANO_AWS_REGION` | `us-east-1` |
| `CYRANO_BEDROCK_MODEL` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `CYRANO_MAX_TOKENS` | `2048` |
| `CYRANO_SESSION_LOG` | `~/.cyrano/sessions.jsonl` |

**macOS permissions:** the first run will prompt for *Accessibility* (global hotkeys, pynput)
and *Screen Recording* (screenshots, mss) for your terminal. Grant both in
System Settings → Privacy & Security, then restart the terminal.

```bash
python main.py
```

## Practice log

When you move on to a new problem (or quit), one line is appended to the session log:

```json
{"ts": "2026-09-24T13:32:19+00:00", "mode": "Coach", "source": "text", "hints_used": 3, "followups": 2, "seconds": 840}
```

After a few dozen problems, look for patterns, e.g. which topics keep needing hint 3+.

## Architecture

```
main.py         wiring: hotkey listener → actions → Assistant / window
hotkeys.py      HotkeyMatcher: pure combo matching on canonicalised keys
assistant.py    Assistant: modes, conversation, hint ladder, busy flag, logging
bedrock.py      lazy Bedrock client, streaming, message helpers
capture.py      full-screen and drag-select screenshots (mss)
window.py       Tkinter overlay window
session_log.py  JSONL practice log
config.py       hotkeys, window, AWS settings, prompts
```

Threads: pynput calls back on its own thread, requests run on worker threads, and every UI
update goes through `root.after(...)` so Tk is only touched from the main thread.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The tests need only `boto3` and `pytest`: the UI, LLM, clock and threading are injected, so
`Assistant` runs synchronously against fakes, and no AWS, Tk or keyboard is required.
