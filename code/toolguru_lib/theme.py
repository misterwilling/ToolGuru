"""Which colours the palette should use, from Fusion's own theme setting."""

from __future__ import annotations

# Values of adsk.core.UserInterfaceThemes that are dark: DarkBlue and
# DarkGray. Checked against live Fusion by the integration tests.
DARK_THEMES = frozenset({2, 3})


def palette_theme(active_theme: int) -> str:
    """'dark' or 'light' for `GeneralPreferences.activeUserInterfaceTheme`,
    which is already resolved when Fusion follows the device's theme."""
    return 'dark' if active_theme in DARK_THEMES else 'light'
