"""Entry point: wires the global hotkeys, the overlay window and the Assistant together."""
import sys
import threading

from pynput import keyboard

import bedrock
from assistant import Assistant
from capture import capture_screen, capture_selection
from config import HOTKEYS, MOVE_STEP, SESSION_LOG
from hotkeys import HotkeyMatcher
from session_log import SessionLog
from window import OverlayWindow

_MOVES = {
    "move_up": (0, -MOVE_STEP),
    "move_down": (0, MOVE_STEP),
    "move_left": (-MOVE_STEP, 0),
    "move_right": (MOVE_STEP, 0),
}


def main():
    print("🔌 Testing Bedrock connection...")
    try:
        bedrock.test_connection()
        print("✅ Bedrock connection successful")
    except Exception as e:
        print(f"❌ {e}")
        print("\n⚠️  Fix your AWS credentials and try again (see README).")
        sys.exit(1)

    app = OverlayWindow()
    assistant = Assistant(ui=app, log=SessionLog(SESSION_LOG))
    app.on_followup = assistant.followup
    app.set_prompt_mode(assistant.mode)

    # ── Actions (pynput thread → must not touch Tk directly) ──────────────

    def screenshot():
        if not assistant.reserve():
            return

        def grab():
            try:
                app.set_status("📸 Capturing screen...")
                img = capture_screen()
            except Exception as e:
                app.set_status(f"❌ Capture failed: {e}")
                assistant.release()
                return
            assistant.ask_image(img, reserved=True)

        threading.Thread(target=grab, daemon=True).start()

    def selection():
        if not assistant.reserve():
            return

        def on_main_thread():
            app.set_status("🎯 Click and drag to select region...")
            img = capture_selection(app.root)
            if img is None:
                app.set_status("❌ Selection cancelled")
                assistant.release()
                return
            assistant.ask_image(img, reserved=True)

        app.root.after(0, on_main_thread)

    def clipboard():
        if not assistant.reserve():
            return

        def on_main_thread():  # Tk clipboard must be read on the main thread
            try:
                text = app.root.clipboard_get()
            except Exception:
                text = ""
            if not text.strip():
                app.set_status("⚠️ Clipboard is empty, copy some text first")
                assistant.release()
                return
            assistant.ask_text(text, reserved=True)

        app.root.after(0, on_main_thread)

    def cursor():
        app.toggle_cursor()
        app.set_status(f"🖱️ Cursor {'hidden' if app._cursor_hidden else 'visible'}")

    actions = {
        "toggle": app.toggle,
        "cycle_prompt": assistant.cycle_mode,
        "cursor": cursor,
        "next_hint": assistant.next_hint,
        "selection": selection,
        "screenshot": screenshot,
        "clipboard": clipboard,
    }
    for name, (dx, dy) in _MOVES.items():
        actions[name] = lambda dx=dx, dy=dy: app.move(dx, dy)

    # ── Global hotkey listener (works even when other apps are focused) ────

    matcher = None

    def on_press(key):
        name = matcher.press(key)
        if name:
            actions[name]()

    def on_release(key):
        matcher.release(key)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    combos = {name: keyboard.HotKey.parse(spec) for name, spec in HOTKEYS.items()}
    matcher = HotkeyMatcher(combos, canonical=listener.canonical)
    listener.start()

    print("🤖 Cyrano running.")
    print("   Ctrl+Shift+Space  → capture full screen")
    print("   Ctrl+Shift+S      → selection screenshot")
    print("   Ctrl+Shift+Enter  → send clipboard text")
    print("   Ctrl+Shift+H      → next hint (Coach mode)")
    print("   Ctrl+Shift+P      → cycle prompt mode")
    print("   Ctrl+Shift+C      → toggle cursor")
    print("   Ctrl+\\            → toggle window visibility")
    print("   Ctrl+Arrow        → move window")
    print("   Close the overlay window (✕) to quit.")

    try:
        app.root.mainloop()
    finally:
        listener.stop()
        assistant.close()


if __name__ == "__main__":
    main()
