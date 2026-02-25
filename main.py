import sys
import threading
from pynput import keyboard
from config import (
    HOTKEY, CLIPBOARD_HOTKEY, TOGGLE_HOTKEY, SELECTION_HOTKEY, 
    CYCLE_PROMPT_HOTKEY, CURSOR_HOTKEY, MOVE_MODIFIER, MOVE_STEP, PROMPTS, PROMPT_NAMES, TEXT_PROMPTS
)
from capture import capture_screen, capture_selection
from bedrock import ask_claude, ask_claude_text, ask_claude_followup, test_connection
from window import OverlayWindow

# Verify Bedrock connection before starting
print("🔌 Testing Bedrock connection...")
try:
    test_connection()
    print("✅ Bedrock connection successful")
except Exception as e:
    print(f"❌ {e}")
    print("\n⚠️  Fix your AWS credentials and try again.")
    sys.exit(1)

# Create overlay window
app = OverlayWindow()

# Track which keys are currently pressed (guarded by lock for thread safety)
_key_lock = threading.Lock()
_pressed_keys = set()
_capturing = False

# Current prompt mode index
_prompt_idx = 0

def _get_done_status():
    mode = PROMPT_NAMES[_prompt_idx]
    return f"[{mode}] Ctrl+Shift+Space=screenshot  Ctrl+\\\\=toggle"

# Conversation history for follow-ups (list of Bedrock message dicts)
_conversation = []


def _stream_to_overlay(token: str):
    """Accumulate a token and forward it to the overlay UI."""
    _response_parts.append(token)
    app.stream_token(token)


_response_parts = []


def on_capture():
    """Runs in background thread. Capture -> API -> stream to overlay."""
    global _response_parts
    _response_parts = []
    _conversation.clear()
    app.clear()
    app.set_status("📸 Capturing screen...")
    try:
        img_b64 = capture_screen()
        app.set_status("🤔 Asking Claude...")
        prompt = PROMPTS[PROMPT_NAMES[_prompt_idx]]
        for token in ask_claude(img_b64, prompt=prompt):
            _stream_to_overlay(token)
        full_reply = "".join(_response_parts)
        _conversation.append({"role": "user", "content": [{"text": "Solve this problem."}]})
        _conversation.append({"role": "assistant", "content": [{"text": full_reply}]})
        app.set_status(f"✅ Done  |  {_get_done_status()}")
    except Exception as e:
        app.stream_token(f"\n❌ Error: {e}\n")
        app.set_status("❌ Error — check terminal for details")
    finally:
        with _key_lock:
            global _capturing
            _capturing = False


def _on_clipboard_text(text: str):
    """Runs in background thread. Clipboard text -> API -> stream to overlay."""
    global _response_parts
    _response_parts = []
    _conversation.clear()
    app.clear()
    app.set_status("🤔 Asking Claude...")
    try:
        prompt = TEXT_PROMPTS[PROMPT_NAMES[_prompt_idx]]
        for token in ask_claude_text(text, prompt=prompt):
            _stream_to_overlay(token)
        full_reply = "".join(_response_parts)
        _conversation.append({"role": "user", "content": [{"text": text}]})
        _conversation.append({"role": "assistant", "content": [{"text": full_reply}]})
        app.set_status(f"✅ Done  |  {_get_done_status()}")
    except Exception as e:
        app.stream_token(f"\n❌ Error: {e}\n")
        app.set_status("❌ Error — check terminal for details")
    finally:
        with _key_lock:
            global _capturing
            _capturing = False


def _launch_clipboard():
    """Called on main thread via root.after(). Reads clipboard then dispatches worker."""
    global _capturing
    try:
        text = app.root.clipboard_get()
    except Exception:
        text = ""
    if not text.strip():
        app.set_status("⚠️ Clipboard is empty — copy some text first")
        with _key_lock:
            _capturing = False
        return
    threading.Thread(target=_on_clipboard_text, args=(text,), daemon=True).start()


def _on_followup(text: str):
    """Called from UI thread when user submits a follow-up question."""
    global _capturing
    with _key_lock:
        if _capturing:
            return
        _capturing = True

    def _run():
        global _response_parts
        _response_parts = []
        app.stream_token("\n\n─── Follow-up ───\n\n")
        app.set_status("🤔 Asking Claude...")
        try:
            _conversation.append({"role": "user", "content": [{"text": text}]})
            for token in ask_claude_followup(_conversation):
                _stream_to_overlay(token)
            full_reply = "".join(_response_parts)
            _conversation.append({"role": "assistant", "content": [{"text": full_reply}]})
            app.set_status(f"✅ Done  |  {_get_done_status()}")
        except Exception as e:
            app.stream_token(f"\n❌ Error: {e}\n")
            app.set_status("❌ Error — check terminal for details")
        finally:
            with _key_lock:
                global _capturing
                _capturing = False

    threading.Thread(target=_run, daemon=True).start()


def _on_selection_capture():
    """Called on main thread. Opens selection UI, then sends to Claude."""
    global _capturing
    app.set_status("🎯 Click and drag to select region...")
    img_b64 = capture_selection(app.root)
    if img_b64 is None:
        app.set_status("❌ Selection cancelled")
        with _key_lock:
            _capturing = False
        return
    
    def _process():
        global _response_parts
        _response_parts = []
        _conversation.clear()
        app.clear()
        app.set_status("🤔 Asking Claude...")
        try:
            prompt = PROMPTS[PROMPT_NAMES[_prompt_idx]]
            for token in ask_claude(img_b64, prompt=prompt):
                _stream_to_overlay(token)
            full_reply = "".join(_response_parts)
            _conversation.append({"role": "user", "content": [{"text": "Solve this problem."}]})
            _conversation.append({"role": "assistant", "content": [{"text": full_reply}]})
            app.set_status(f"✅ Done  |  {_get_done_status()}")
        except Exception as e:
            app.stream_token(f"\n❌ Error: {e}\n")
            app.set_status("❌ Error — check terminal for details")
        finally:
            with _key_lock:
                global _capturing
                _capturing = False
    
    threading.Thread(target=_process, daemon=True).start()


def _cycle_prompt():
    """Cycle to the next prompt mode."""
    global _prompt_idx
    _prompt_idx = (_prompt_idx + 1) % len(PROMPT_NAMES)
    mode = PROMPT_NAMES[_prompt_idx]
    app.set_prompt_mode(mode)
    app.set_status(f"🔄 Switched to [{mode}] mode")


def _handle_arrow_movement(key):
    """Move window with arrow keys when modifier is held."""
    dx, dy = 0, 0
    if key == keyboard.Key.up:
        dy = -MOVE_STEP
    elif key == keyboard.Key.down:
        dy = MOVE_STEP
    elif key == keyboard.Key.left:
        dx = -MOVE_STEP
    elif key == keyboard.Key.right:
        dx = MOVE_STEP
    if dx or dy:
        app.move(dx, dy)


def on_press(key):
    global _capturing
    with _key_lock:
        _pressed_keys.add(key)
        
        # Check for arrow key movement (Ctrl+Arrow)
        if MOVE_MODIFIER in _pressed_keys:
            if key in (keyboard.Key.up, keyboard.Key.down, keyboard.Key.left, keyboard.Key.right):
                _handle_arrow_movement(key)
                return
        
        # Check toggle hotkey (Ctrl+\)
        if all(k in _pressed_keys for k in TOGGLE_HOTKEY):
            app.toggle()
            return
        
        # Check prompt cycle hotkey (Ctrl+Shift+P)
        if all(k in _pressed_keys for k in CYCLE_PROMPT_HOTKEY):
            _cycle_prompt()
            return
        
        # Check cursor toggle hotkey (Ctrl+Shift+C)
        if all(k in _pressed_keys for k in CURSOR_HOTKEY):
            app.toggle_cursor()
            status = "hidden" if app._cursor_hidden else "visible"
            app.set_status(f"🖱️ Cursor {status} (stealth mode)")
            return
        
        # Check selection screenshot hotkey (Ctrl+Shift+S)
        if all(k in _pressed_keys for k in SELECTION_HOTKEY):
            if _capturing:
                return
            _capturing = True
            app.root.after(0, _on_selection_capture)
            return
        
        # Check full screenshot hotkey
        screenshot_active = all(k in _pressed_keys for k in HOTKEY)
        clipboard_active = all(k in _pressed_keys for k in CLIPBOARD_HOTKEY)
        if _capturing:
            return
        if screenshot_active:
            _capturing = True
            target = on_capture
        elif clipboard_active:
            _capturing = True
            target = None  # clipboard uses root.after instead
        else:
            return

    if target:
        threading.Thread(target=target, daemon=True).start()
    else:
        app.root.after(0, _launch_clipboard)


def on_release(key):
    with _key_lock:
        _pressed_keys.discard(key)


# Start global hotkey listener (works even when other apps are focused)
app.on_followup = _on_followup

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

print("🤖 Interview Assistant running.")
print("   Ctrl+Shift+Space  → capture full screen")
print("   Ctrl+Shift+S      → selection screenshot")
print("   Ctrl+Shift+Enter  → send clipboard text")
print("   Ctrl+Shift+P      → cycle prompt mode")
print("   Ctrl+Shift+C      → toggle cursor (stealth)")
print("   Ctrl+\\            → toggle window visibility")
print("   Ctrl+Arrow        → move window")
print("   Drag corners/edges to resize window")
print("   Close the overlay window (✕) to quit.")

app.root.mainloop()


