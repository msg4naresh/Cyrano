from pynput import keyboard

# Hotkey to trigger screen capture
HOTKEY = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.Key.space}

# Hotkey to send clipboard text to Claude
CLIPBOARD_HOTKEY = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.Key.enter}

# Hotkey to toggle window visibility (Ctrl+\)
TOGGLE_HOTKEY = {keyboard.Key.ctrl, keyboard.KeyCode.from_char('\\')}

# Hotkey for selection screenshot (Ctrl+Shift+S)
SELECTION_HOTKEY = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char('s')}

# Hotkey to cycle prompt modes (Ctrl+Shift+P)
CYCLE_PROMPT_HOTKEY = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char('p')}

# Hotkey to toggle cursor visibility (Ctrl+Shift+C)
CURSOR_HOTKEY = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char('c')}

# Arrow key movement settings
MOVE_MODIFIER = keyboard.Key.ctrl
MOVE_STEP = 20  # pixels per keypress

# Overlay window settings
WINDOW_WIDTH  = 650
WINDOW_HEIGHT = 500
WINDOW_X      = 50     # pixels from left edge of screen
WINDOW_Y      = 50     # pixels from top of screen
WINDOW_ALPHA  = 0.92   # transparency: 0.0 = invisible, 1.0 = fully opaque

# AWS Bedrock settings
AWS_REGION = "us-east-1"
AWS_PROFILE = "saml"
BEDROCK_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Shared response format
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

_BASE = "You are helping me solve a coding interview problem.\n{source} respond in EXACTLY this format with NO deviation:" + _RESPONSE_FORMAT

# Multiple prompt modes
PROMPTS = {
    "Interview": _BASE.format(source="Analyze the screenshot and"),
    "Debug": "You are an expert debugger. Analyze the code/error and explain:\n1. What the error means\n2. Root cause\n3. How to fix it\nBe concise and actionable.",
    "System Design": "You are a system design expert. For the given problem:\n1. Clarify requirements\n2. High-level design\n3. Key components\n4. Trade-offs\nUse clear diagrams (ASCII if needed).",
    "Behavioral": "Help answer this behavioral interview question using the STAR method:\n- Situation: Set the context\n- Task: What was required\n- Action: What you did\n- Result: The outcome\nKeep it concise and impactful.",
}
PROMPT_NAMES = list(PROMPTS.keys())

# Default prompt (for backward compatibility)
PROMPT = PROMPTS["Interview"]

# Text-specific prompts for each mode
TEXT_PROMPTS = {
    "Interview": _BASE.format(source="Analyze the text below and"),
    "Debug": PROMPTS["Debug"],
    "System Design": PROMPTS["System Design"],
    "Behavioral": PROMPTS["Behavioral"],
}
TEXT_PROMPT = TEXT_PROMPTS["Interview"]

# Lighter prompt for follow-up questions (no format constraint)
FOLLOWUP_PROMPT = "Continue helping with the coding interview problem. The user has a follow-up question. Give a clear, concise answer."
