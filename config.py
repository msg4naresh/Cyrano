import os

# ── Hotkeys ───────────────────────────────────────────────────────────────
# Written in pynput's HotKey syntax. main.py parses them with
# keyboard.HotKey.parse and matches them against *canonical* key events, so
# Shift+letter and left/right modifiers compare equal (see hotkeys.py).
HOTKEYS = {
    "move_up":      "<ctrl>+<up>",
    "move_down":    "<ctrl>+<down>",
    "move_left":    "<ctrl>+<left>",
    "move_right":   "<ctrl>+<right>",
    "toggle":       "<ctrl>+\\",
    "cycle_prompt": "<ctrl>+<shift>+p",
    "cursor":       "<ctrl>+<shift>+c",
    "next_hint":    "<ctrl>+<shift>+h",
    "selection":    "<ctrl>+<shift>+s",
    "screenshot":   "<ctrl>+<shift>+<space>",
    "clipboard":    "<ctrl>+<shift>+<enter>",
}

MOVE_STEP = 20  # pixels per keypress

# ── Overlay window ────────────────────────────────────────────────────────
WINDOW_WIDTH  = 650
WINDOW_HEIGHT = 500
WINDOW_X      = 50     # pixels from left edge of screen
WINDOW_Y      = 50     # pixels from top of screen
WINDOW_ALPHA  = 0.92   # transparency: 0.0 = invisible, 1.0 = fully opaque

# ── AWS Bedrock (override with environment variables) ─────────────────────
AWS_REGION = os.environ.get("CYRANO_AWS_REGION", "us-east-1")
AWS_PROFILE = os.environ.get("CYRANO_AWS_PROFILE") or None  # None = default credential chain
BEDROCK_MODEL = os.environ.get("CYRANO_BEDROCK_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
MAX_TOKENS = int(os.environ.get("CYRANO_MAX_TOKENS", "2048"))

# ── Practice log ──────────────────────────────────────────────────────────
SESSION_LOG = os.path.expanduser(os.environ.get("CYRANO_SESSION_LOG", "~/.cyrano/sessions.jsonl"))

# ── Prompts ───────────────────────────────────────────────────────────────
_RESPONSE_FORMAT = """
🧠 PROBLEM
(1-2 lines: plain english explanation of what is being asked)

💡 APPROACH
(Step by step thinking. No code yet. How to think about this problem.)

⏱️ COMPLEXITY
Time: O(?)
Space: O(?)

💻 SOLUTION
(Clean, well-commented Python code that solves the problem)
"""

_SOLVE = "You are helping me study a coding problem.\n{source} respond in EXACTLY this format with NO deviation:" + _RESPONSE_FORMAT

# Hint ladder: each level reveals a little more. The coach only moves up a
# level when asked ("next hint"), so the learner does the thinking.
HINT_LEVELS = [
    "Nudge: restate the problem and ask one guiding question. No techniques named.",
    "Key insight: name the core observation or pattern (e.g. 'two pointers', 'monotonic stack') and why it applies.",
    "Approach: outline the algorithm step by step in plain English. No code.",
    "Complexity: give time/space complexity and justify it, plus the edge cases to handle.",
    "Solution: clean, well-commented Python code, then a short walkthrough on a small example.",
]
MAX_HINT_LEVEL = len(HINT_LEVELS)

def _coach(task: str) -> str:
    ladder = "\n".join(f"  Level {i}. {h}" for i, h in enumerate(HINT_LEVELS, 1))
    return (
        "You are a patient coding-interview coach. Your goal is to build the learner's "
        "problem-solving skill, NOT to hand out answers.\n"
        f"{task}\n\nThe hint ladder:\n{ladder}\n\n"
        "Never reveal a higher level than requested. If the learner describes their own "
        "approach, act as a skeptical interviewer: point out bugs, missed edge cases and "
        "complexity issues, and ask probing questions instead of fixing it for them."
    )


_COACH_START = "{source} respond with ONLY hint level 1. Start your reply with 'Hint 1/%d'." % MAX_HINT_LEVEL

_DEBUG = "You are an expert debugger. Analyze the code/error and explain:\n1. What the error means\n2. Root cause\n3. How to fix it\nBe concise and actionable."
_SYSTEM_DESIGN = "You are a system design expert. For the given problem:\n1. Clarify requirements\n2. High-level design\n3. Key components\n4. Trade-offs\nUse clear diagrams (ASCII if needed)."
_BEHAVIORAL = "Help me practise this behavioral interview question using the STAR method:\n- Situation: Set the context\n- Task: What was required\n- Action: What you did\n- Result: The outcome\nKeep it concise and impactful."

# System prompt per mode, for image input and for text (clipboard) input.
PROMPTS = {
    "Coach": _coach(_COACH_START.format(source="Read the problem in the screenshot and")),
    "Solve": _SOLVE.format(source="Analyze the screenshot and"),
    "Debug": _DEBUG,
    "System Design": _SYSTEM_DESIGN,
    "Behavioral": _BEHAVIORAL,
}
TEXT_PROMPTS = {
    **PROMPTS,
    "Coach": _coach(_COACH_START.format(source="Read the problem in the text below and")),
    "Solve": _SOLVE.format(source="Analyze the text below and"),
}
PROMPT_NAMES = list(PROMPTS.keys())

# Follow-ups keep the coach in coaching mode; other modes use a lighter prompt.
_DEFAULT_FOLLOWUP = "Continue helping with the problem. The user has a follow-up question. Give a clear, concise answer."
FOLLOWUP_PROMPTS = {name: _DEFAULT_FOLLOWUP for name in PROMPT_NAMES}
FOLLOWUP_PROMPTS["Coach"] = _coach(
    "Continue coaching on the same problem. When asked for a hint, give ONLY the "
    "requested level and start with 'Hint N/%d'." % MAX_HINT_LEVEL
)


def next_hint_request(level: int) -> str:
    """User turn sent when the learner asks for the next rung of the ladder."""
    return f"Give me hint level {level} of {MAX_HINT_LEVEL} ({HINT_LEVELS[level - 1].split(':')[0]}). Only that level."
