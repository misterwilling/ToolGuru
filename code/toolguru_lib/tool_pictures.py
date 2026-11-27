"""Fusion's own picture of each tool type.

Fusion's tool library ships one picture per tool type inside its install
folder. They are shown straight from there and never copied: they are
Autodesk's files, and the file names carry a build stamp that changes with
every Fusion update.
"""

from __future__ import annotations

from pathlib import Path

# Tool type -> the start of its picture's file name, as Fusion's tool library
# maps them. Form mills and probes have no picture file.
PICTURE_NAMES = {
    'flat end mill': 'ToolEndMill',
    'ball end mill': 'ToolBallMill',
    'bull nose end mill': 'ToolBullMill',
    'chamfer mill': 'ToolEngraveChamferMill',
    'face mill': 'ToolFaceMill',
    'slot mill': 'ToolSlotMill',
    'radius mill': 'ToolRadiusMill',
    'dovetail mill': 'ToolDoveTail',
    'tapered mill': 'ToolTaperMill',
    'lollipop mill': 'ToolLollipopMill',
    'drill': 'ToolDrill',
    'center drill': 'ToolCenterDrill',
    'spot drill': 'ToolSpotDrill',
    'counter bore': 'ToolCounterBore',
    'counter sink': 'ToolCounterSink',
    'reamer': 'ToolReamer',
    'boring bar': 'ToolBoringBar',
    'tap right hand': 'ToolTap',
    'tap left hand': 'ToolTapLeft',
    'thread mill': 'ToolThreadMill',
    'holder': 'ToolHolder',
}

_PICTURE_FOLDER = ('Applications', 'CAM360', 'tool-library', 'static', 'png')


def find_pictures(install_dir: Path) -> dict[str, str]:
    """The `file://` address of each tool type's picture under Fusion's
    install folder. A type whose picture is not there is left out, so a
    Fusion update that moves them costs the pictures and nothing else."""
    folder = install_dir.joinpath(*_PICTURE_FOLDER)
    pictures: dict[str, str] = {}
    for tool_type, name in PICTURE_NAMES.items():
        matches = sorted(folder.glob(f'{name}-*.png'))
        if matches:
            pictures[tool_type] = matches[0].as_uri()
    return pictures
