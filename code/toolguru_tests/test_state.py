"""Sample unit test for the pure-Python state module.

State has no adsk imports, so it needs no mocks. Use this file as the
template when you extract more pure logic from entry.py.
"""

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_commands.commandPalette.state import AppState


class TestAppState:
    def test_serialize_empty(self):
        state = AppState()
        assert state.serialize() == {'selections': {}, 'mode': 'default'}

    def test_set_and_clear_selection(self):
        state = AppState()
        state.set_selection('primary', 'token-abc')
        assert state.serialize()['selections'] == {'primary': 'token-abc'}

        state.clear_selection('primary')
        assert state.serialize()['selections'] == {}

    def test_clear_unknown_slot_is_idempotent(self):
        state = AppState()
        state.clear_selection('never-set')  # must not raise
        assert state.serialize()['selections'] == {}

    def test_serialize_is_a_copy(self):
        state = AppState()
        state.set_selection('a', 'tok-1')
        snapshot = state.serialize()
        state.set_selection('a', 'tok-2')
        assert snapshot['selections'] == {'a': 'tok-1'}, \
            'serialize() must return a snapshot, not a live reference'
