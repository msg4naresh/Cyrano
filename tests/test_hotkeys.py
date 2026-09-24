from hotkeys import HotkeyMatcher

# Plain strings stand in for pynput keys; str.lower plays the role of
# Listener.canonical (which lower-cases letters and merges modifiers).
COMBOS = {
    "selection": ["ctrl", "shift", "s"],
    "screenshot": ["ctrl", "shift", "space"],
    "toggle": ["ctrl", "\\"],
}


def make():
    return HotkeyMatcher(COMBOS, canonical=str.lower)


def test_combo_fires_on_final_key():
    m = make()
    assert m.press("ctrl") is None
    assert m.press("shift") is None
    assert m.press("space") == "screenshot"


def test_shifted_letter_matches_lowercase_combo():
    m = make()
    m.press("ctrl")
    m.press("shift")
    assert m.press("S") == "selection"   # Shift makes pynput report 'S'


def test_release_with_different_case_does_not_leave_stuck_key():
    m = make()
    m.press("ctrl"); m.press("shift"); m.press("S")
    m.release("shift")
    m.release("s")                        # Shift already up, so release reports 's'
    m.release("ctrl")
    assert m.pressed == frozenset()


def test_without_canonical_the_old_bug_reappears():
    m = HotkeyMatcher(COMBOS)             # identity canonical, like the old code
    m.press("ctrl"); m.press("shift")
    assert m.press("S") is None
    m.release("s")
    assert "S" in m.pressed               # stuck forever


def test_key_not_in_combo_does_not_fire():
    m = make()
    m.press("ctrl"); m.press("\\")
    assert m.press("x") is None           # toggle is satisfied but x is not part of it


def test_first_matching_combo_wins():
    m = HotkeyMatcher({"a": ["ctrl", "k"], "b": ["ctrl", "k"]})
    m.press("ctrl")
    assert m.press("k") == "a"
