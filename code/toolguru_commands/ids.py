"""Single source of truth for every globally-unique UI identifier.

Every toolbar tab, panel, command definition, palette, and custom event ID
in this add-in is defined here once and imported everywhere else. Keeping
them in one place prevents two files from disagreeing about the same ID
(which silently breaks `start()`/`stop()` symmetry).
"""

ADDIN_NAME = 'ToolGuru'
COMPANY_NAME = 'CapitalCNC'

# Workspace where the toolbar tab is registered. See ARCHITECTURE.md in the
# bootstrap for the workspace-ID table. Do not change without rerunning
# scaffold or explicitly reassigning all tab/panel placements.
WORKSPACE_ID = 'CAMEnvironment'

# Toolbar tab + panel. IDs are uniquely prefixed so they can't collide with
# another add-in's tab. TAB_NAME is what users see on the ribbon.
TAB_ID = f'{COMPANY_NAME}_{ADDIN_NAME}_tab'
TAB_NAME = ADDIN_NAME
PANEL_ID = f'{COMPANY_NAME}_{ADDIN_NAME}_panel'
PANEL_NAME = 'Tools'

# Palette command.
CMD_ID = f'{COMPANY_NAME}_{ADDIN_NAME}_commandPalette'
CMD_NAME = ADDIN_NAME
CMD_DESC = 'Collects tools from CAM programs, tallies usage and finds duplicates to build a standard tool library.'

PALETTE_ID = f'{COMPANY_NAME}_{ADDIN_NAME}_palette'
PALETTE_NAME = ADDIN_NAME
PALETTE_WIDTH = 420
PALETTE_HEIGHT = 640

# Custom event for geometry picking (selectEntity can't run inside the HTML
# event handler — see ARCHITECTURE.md "Geometry Picking from Palettes").
PICK_EVENT_ID = f'{COMPANY_NAME}_{ADDIN_NAME}_pickEvent'

# Attribute group used when tagging Fusion entities with add-in metadata.
ATTR_GROUP = ADDIN_NAME
