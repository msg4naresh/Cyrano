"""Request orchestration: the state machine behind the hotkeys.

Every request follows the same skeleton:

    reserve → (reset or append header) → status → call Claude → store turns → done → release

so it lives in one place (`_run`) and the public methods only differ in the
message they send and the prompt they use. Dependencies (UI, LLM, log,
threading) are injected so the whole flow can be tested without Tk, AWS or a
keyboard.
"""
import threading
import time

import bedrock
from config import (
    PROMPTS, TEXT_PROMPTS, FOLLOWUP_PROMPTS, PROMPT_NAMES, MAX_HINT_LEVEL, next_hint_request,
)


def _spawn_thread(fn):
    threading.Thread(target=fn, daemon=True).start()


class Assistant:
    def __init__(self, ui, llm=bedrock, log=None, spawn=_spawn_thread, clock=time.monotonic):
        self.ui = ui
        self.llm = llm
        self.log = log
        self.spawn = spawn
        self.clock = clock

        self.mode_idx = 0
        self.conversation = []    # Bedrock messages for the current problem
        self.hint_level = 0       # Coach mode: highest hint shown so far
        self._problem = None      # {"mode", "source", "started", "followups"} while a problem is open
        self._lock = threading.Lock()
        self._busy = False

    # ── Busy flag ──────────────────────────────────────────────────────────

    def reserve(self) -> bool:
        """Claim the assistant for one request. False if a request is already running."""
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            return True

    def release(self):
        with self._lock:
            self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    # ── Modes ──────────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return PROMPT_NAMES[self.mode_idx]

    def cycle_mode(self):
        self.mode_idx = (self.mode_idx + 1) % len(PROMPT_NAMES)
        self.ui.set_prompt_mode(self.mode)
        self.ui.set_status(f"🔄 Switched to [{self.mode}] mode")

    def done_status(self) -> str:
        status = f"✅ Done  |  [{self._problem['mode'] if self._problem else self.mode}]"
        if self._problem and self._problem["mode"] == "Coach":
            if self.hint_level < MAX_HINT_LEVEL:
                status += f"  hint {self.hint_level}/{MAX_HINT_LEVEL}, Ctrl+Shift+H = next hint"
            else:
                status += "  all hints shown"
        return status

    # ── Public requests ────────────────────────────────────────────────────

    def ask_image(self, image_b64: str, reserved: bool = False) -> bool:
        """Start a new problem from a screenshot."""
        return self._new_problem(self.llm.image_message(image_b64), PROMPTS[self.mode], "screenshot", reserved)

    def ask_text(self, text: str, reserved: bool = False) -> bool:
        """Start a new problem from pasted text."""
        return self._new_problem(self.llm.text_message(text), TEXT_PROMPTS[self.mode], "text", reserved)

    def followup(self, text: str) -> bool:
        """Ask a follow-up (or explain your approach, in Coach mode) about the current problem."""
        if not self._problem:
            self.ui.set_status("⚠️ Capture a problem first")
            return False
        mode = self._problem["mode"]

        def on_success():
            self._problem["followups"] += 1

        return self._run(
            message=self.llm.text_message(text),
            prompt=FOLLOWUP_PROMPTS[mode],
            header="\n\n─── Follow-up ───\n\n",
            on_success=on_success,
        )

    def next_hint(self) -> bool:
        """Coach mode: reveal the next rung of the hint ladder."""
        if not self._problem or self._problem["mode"] != "Coach":
            self.ui.set_status("⚠️ Next hint works on a problem started in Coach mode")
            return False
        if self.hint_level >= MAX_HINT_LEVEL:
            self.ui.set_status("✅ All hints already shown")
            return False
        level = self.hint_level + 1

        def on_success():
            self.hint_level = level

        return self._run(
            message=self.llm.text_message(next_hint_request(level)),
            prompt=FOLLOWUP_PROMPTS["Coach"],
            header=f"\n\n─── Hint {level}/{MAX_HINT_LEVEL} ───\n\n",
            on_success=on_success,
        )

    def close(self):
        """Log the open problem (call on shutdown)."""
        self._finish_problem()

    # ── Internals ──────────────────────────────────────────────────────────

    def _new_problem(self, message, prompt, source, reserved) -> bool:
        mode = self.mode

        def on_start():
            self._finish_problem()
            self.conversation.clear()
            self.hint_level = 1 if mode == "Coach" else 0
            self._problem = {"mode": mode, "source": source, "started": self.clock(), "followups": 0}
            self.ui.clear()

        return self._run(message=message, prompt=prompt, on_start=on_start, reserved=reserved)

    def _run(self, message, prompt, header=None, on_start=None, on_success=None, reserved=False) -> bool:
        if not reserved and not self.reserve():
            return False

        def work():
            try:
                if on_start:
                    on_start()
                if header:
                    self.ui.stream_token(header)
                self.ui.set_status("🤔 Asking Claude...")
                reply = self.llm.stream(prompt, self.conversation + [message], self.ui.stream_token)
                # Only commit the turn once it succeeded, so a failed request never
                # leaves two user messages in a row (which Bedrock rejects).
                self.conversation.extend([message, self.llm.text_message(reply, role="assistant")])
                if on_success:
                    on_success()
                self.ui.set_status(self.done_status())
            except Exception as e:
                self.ui.stream_token(f"\n❌ Error: {e}\n")
                self.ui.set_status("❌ Error, check terminal for details")
            finally:
                self.release()

        self.spawn(work)
        return True

    def _finish_problem(self):
        if not self._problem:
            return
        if self.log:
            p = self._problem
            self.log.record(
                mode=p["mode"],
                source=p["source"],
                hints_used=self.hint_level if p["mode"] == "Coach" else None,
                followups=p["followups"],
                seconds=round(self.clock() - p["started"]),
            )
        self._problem = None
