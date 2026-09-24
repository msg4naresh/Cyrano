"""Hotkey matching, kept free of pynput so it can be unit-tested.

Why canonicalise? pynput reports the *character* a key produced, not the
physical key. With Shift held, the S key arrives as 'S'; released after Shift
it arrives as 's'. Comparing raw events means combos silently fail to match,
and keys get "stuck" in the pressed set because the release never matches the
press. Passing every event through `canonical` (lower-casing letters, merging
left/right modifiers) makes press, release and combo definition agree.
"""


class HotkeyMatcher:
    def __init__(self, combos: dict, canonical=lambda k: k):
        """
        Args:
            combos: {name: iterable of keys}. Order matters: when several combos
                match the same key press, the first one wins.
            canonical: function normalising a raw key event.
        """
        self._combos = [(name, frozenset(canonical(k) for k in keys)) for name, keys in combos.items()]
        self._canonical = canonical
        self._pressed = set()

    def press(self, key):
        """Record a key press. Returns the name of the combo it completes, or None."""
        key = self._canonical(key)
        self._pressed.add(key)
        for name, keys in self._combos:
            if key in keys and keys <= self._pressed:
                return name
        return None

    def release(self, key):
        self._pressed.discard(self._canonical(key))

    @property
    def pressed(self) -> frozenset:
        return frozenset(self._pressed)
