"""Logging and error helpers.

Never use print() — Fusion's embedded Python doesn't surface it anywhere
useful. Use log() instead; it writes to Fusion's Text Commands palette
(View → Text Commands).
"""

from __future__ import annotations

import adsk.core
import traceback

try:
    from toolguru_lib.config_utils import load_config
    DEBUG = load_config().get('debug', False)
except:
    DEBUG = False


def log(message: object,
        level: int = adsk.core.LogLevels.InfoLogLevel,
        force_console: bool = False) -> None:
    app = adsk.core.Application.get()
    if not app:
        return
    if level == adsk.core.LogLevels.ErrorLogLevel:
        app.log(str(message), level, adsk.core.LogTypes.FileLogType)
    if DEBUG or force_console:
        app.log(str(message), level, adsk.core.LogTypes.ConsoleLogType)


def handle_error(name: str, show_message_box: bool = False) -> None:
    log(f'===== Error in {name} =====',
        adsk.core.LogLevels.ErrorLogLevel, force_console=True)
    log(traceback.format_exc(),
        adsk.core.LogLevels.ErrorLogLevel, force_console=True)
    if show_message_box:
        app = adsk.core.Application.get()
        if app:
            app.userInterface.messageBox(
                f'Error in {name}:\n{traceback.format_exc()}')
