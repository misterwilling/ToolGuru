"""Pure Python state for the palette command.

No `adsk` imports here — this module is importable under pytest without
mocking, which makes it the testable surface for every decision that
doesn't strictly need the Fusion API.

Store entity tokens (strings), never entity objects. Tokens survive
across event handlers; entity objects go stale.
"""

from __future__ import annotations


class AppState:
    def __init__(self) -> None:
        self.selections: dict[str, str] = {}  # slot name -> entity token
        self.mode: str = 'default'

    def serialize(self) -> dict:
        return {
            'selections': dict(self.selections),
            'mode': self.mode,
        }

    def set_selection(self, slot: str, token: str) -> None:
        self.selections[slot] = token

    def clear_selection(self, slot: str) -> None:
        self.selections.pop(slot, None)


state = AppState()
