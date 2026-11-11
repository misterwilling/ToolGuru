import adsk.core
import importlib
import traceback
import sys
import os

_code_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'code')

# IMPORTANT: every top-level package under `code/` MUST be prefixed with
# `toolguru_`. Once `_code_dir` is on `sys.path` it sits alongside
# every other installed add-in's `code/` dir; a bare-named package
# (`commands`, `tests`, `fusion_tests`, …) will silently bind to whichever
# add-in was loaded first. The failure mode is invisible — code runs,
# tests "pass", but state and hashes refer to a different add-in's source
# tree. The scaffolder enforces the prefix; do not introduce a bare-name
# package by hand. See ARCHITECTURE.md "Why prefix the test packages too?".
_ENTRY_MODULE = 'toolguru_entry_point'
_COMMANDS_MODULE = 'toolguru_commands'


def run(context):
    try:
        if _code_dir not in sys.path:
            sys.path.insert(0, _code_dir)
        _reload_modules()
        ep = __import__(_ENTRY_MODULE)
        ep.run(context)
    except:
        adsk.core.Application.get().userInterface.messageBox(
            'Add-in start failed:\n{}'.format(traceback.format_exc()))


def stop(context):
    try:
        ep = __import__(_ENTRY_MODULE)
        ep.stop(context)
    except:
        adsk.core.Application.get().userInterface.messageBox(
            'Add-in stop failed:\n{}'.format(traceback.format_exc()))
    _purge_modules()


def _purge_modules():
    to_remove = [k for k in sys.modules
                 if k == _ENTRY_MODULE
                 or k == _COMMANDS_MODULE
                 or k.startswith(_COMMANDS_MODULE + '.')
                 or k == 'toolguru_lib'
                 or k.startswith('toolguru_lib.')]
    for k in to_remove:
        del sys.modules[k]


def _reload_modules():
    for name in [_COMMANDS_MODULE, _ENTRY_MODULE]:
        if name in sys.modules:
            try:
                importlib.reload(sys.modules[name])
            except:
                del sys.modules[name]
