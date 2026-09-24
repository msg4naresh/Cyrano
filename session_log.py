"""Append-only practice log (one JSON object per line).

Each finished problem records its mode, how many hints were needed and how
long it took, so you can later spot patterns like "always needs hint 3 on DP".
"""
import json
import os
from datetime import datetime, timezone


class SessionLog:
    def __init__(self, path: str):
        self.path = path

    def record(self, **fields):
        entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields}
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as e:
            print(f"⚠️  Could not write session log: {e}")

    def read(self) -> list:
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
