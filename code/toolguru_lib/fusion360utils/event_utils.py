"""Event handler registration with automatic GC prevention.

Fusion silently drops event handlers that Python garbage-collects. This
module holds a reference to every handler we create so the GC can't
collect them. Two storage modes:

- Global (`_handlers`) — long-lived handlers (command registration,
  document events). Cleared in stop().
- Local (`local_handlers`) — command-scoped handlers (execute, preview,
  validate). Caller clears them in command_destroy.
"""

from __future__ import annotations

import adsk.core
import sys
import traceback

_handlers: list = []


def add_handler(event, callback, *, name=None, local_handlers=None):
    handler_name = name or callback.__name__
    handler_type = _get_handler_type(event)
    handler_cls = _define_handler(handler_type, callback, handler_name)
    handler = handler_cls()

    if local_handlers is not None:
        local_handlers.append(handler)
    else:
        _handlers.append(handler)

    event.add(handler)
    return handler


def clear_handlers() -> None:
    global _handlers
    _handlers = []


def _get_handler_type(event):
    module = sys.modules[event.__class__.__module__]
    add_method = getattr(type(event), 'add')
    annotations = getattr(add_method, '__annotations__', None) or {}
    if 'handler' in annotations:
        handler_type_name = annotations['handler']
        if isinstance(handler_type_name, str):
            return getattr(module, handler_type_name)
        return handler_type_name
    event_type_name = type(event).__name__
    return getattr(module, event_type_name + 'Handler')


def _define_handler(handler_type, callback, name):
    class Handler(handler_type):
        def __init__(self):
            super().__init__()

        def notify(self, args):
            try:
                callback(args)
            except:
                app = adsk.core.Application.get()
                if app:
                    app.userInterface.messageBox(
                        'Handler "{}" failed:\n{}'.format(name, traceback.format_exc()))

    Handler.__name__ = f'Handler_{name}'
    return Handler
