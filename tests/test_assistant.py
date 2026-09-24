import pytest

import bedrock
from assistant import Assistant
from config import MAX_HINT_LEVEL, PROMPT_NAMES


class FakeUI:
    def __init__(self):
        self.text = ""
        self.statuses = []
        self.mode = None

    def stream_token(self, t):
        self.text += t

    def set_status(self, s):
        self.statuses.append(s)

    def clear(self):
        self.text = ""

    def set_prompt_mode(self, m):
        self.mode = m


class FakeLLM:
    """Mimics the bedrock module: same message helpers, scripted replies."""
    image_message = staticmethod(bedrock.image_message)
    text_message = staticmethod(bedrock.text_message)

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def stream(self, prompt, messages, on_token):
        self.calls.append((prompt, list(messages)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        on_token(reply)
        return reply


class FakeLog:
    def __init__(self):
        self.entries = []

    def record(self, **f):
        self.entries.append(f)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make(replies, mode="Coach"):
    ui, llm, log, clock = FakeUI(), FakeLLM(replies), FakeLog(), Clock()
    a = Assistant(ui, llm=llm, log=log, spawn=lambda fn: fn(), clock=clock)
    a.mode_idx = PROMPT_NAMES.index(mode)
    return a, ui, llm, log, clock


def test_new_problem_streams_and_records_conversation():
    a, ui, llm, _, _ = make(["Hint 1/5 ..."])
    assert a.ask_text("two sum")
    assert ui.text == "Hint 1/5 ..."
    assert [m["role"] for m in a.conversation] == ["user", "assistant"]
    assert a.hint_level == 1
    assert not a.busy
    assert "next hint" in ui.statuses[-1]


def test_hint_ladder_climbs_and_stops_at_max():
    a, ui, llm, _, _ = make(["h1"] + [f"h{i}" for i in range(2, MAX_HINT_LEVEL + 1)])
    a.ask_text("problem")
    for expected in range(2, MAX_HINT_LEVEL + 1):
        assert a.next_hint()
        assert a.hint_level == expected
        assert f"hint level {expected}" in llm.calls[-1][1][-1]["content"][0]["text"]
    assert not a.next_hint()
    assert "All hints" in ui.statuses[-1]


def test_next_hint_requires_coach_problem():
    a, ui, _, _, _ = make(["answer"], mode="Solve")
    a.ask_text("problem")
    assert not a.next_hint()


def test_followup_sends_whole_conversation():
    a, _, llm, _, _ = make(["first", "second"])
    a.ask_text("problem")
    a.followup("why?")
    prompt, messages = llm.calls[-1]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert len(a.conversation) == 4


def test_failed_followup_does_not_corrupt_conversation():
    a, ui, _, _, _ = make(["first", RuntimeError("boom"), "third"])
    a.ask_text("problem")
    a.followup("q1")                       # fails
    assert len(a.conversation) == 2        # no dangling user turn
    assert "boom" in ui.text
    assert not a.busy
    a.followup("q2")
    assert len(a.conversation) == 4


def test_busy_blocks_concurrent_requests():
    a, _, llm, _, _ = make(["x"])
    assert a.reserve()
    assert not a.ask_text("problem")
    assert llm.calls == []
    a.release()
    assert a.ask_text("problem")


def test_finished_problem_is_logged_with_hints_and_time():
    a, _, _, log, clock = make(["h1", "h2", "next problem"])
    a.ask_text("p1")
    a.next_hint()
    clock.t = 90
    a.ask_text("p2")                      # starting a new problem closes the old one
    assert log.entries == [{"mode": "Coach", "source": "text", "hints_used": 2, "followups": 0, "seconds": 90}]
    a.close()
    assert len(log.entries) == 2


def test_cycle_mode_wraps_around():
    a, ui, _, _, _ = make([])
    a.mode_idx = len(PROMPT_NAMES) - 1
    a.cycle_mode()
    assert a.mode == PROMPT_NAMES[0]
    assert ui.mode == PROMPT_NAMES[0]
