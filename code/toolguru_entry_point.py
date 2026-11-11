from toolguru_lib.fusion360utils import event_utils as futil
from toolguru_lib.fusion360utils import general_utils as gutil
from toolguru_commands import start as commands_start, stop as commands_stop


def run(context):
    gutil.log('ToolGuru starting...', force_console=True)
    commands_start()


def stop(context):
    futil.clear_handlers()
    commands_stop()
    gutil.log('ToolGuru stopped.', force_console=True)
