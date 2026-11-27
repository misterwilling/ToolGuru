"""Write and remove ToolGuru's own tool libraries in Fusion's Local libraries.

Touches the Fusion API. It only ever writes or deletes the library it is
given by name; no other library is read or changed.
"""

from __future__ import annotations

import adsk.cam
import adsk.core


def _libraries() -> adsk.cam.ToolLibraries:
    return adsk.cam.CAMManager.get().libraryManager.toolLibraries


def _local_root(libraries: adsk.cam.ToolLibraries) -> adsk.core.URL:
    return libraries.urlByLocation(adsk.cam.LibraryLocations.LocalLibraryLocation)


def tool_count(name: str) -> int | None:
    """How many tools the Local library of this name holds; None when there
    is no such library."""
    libraries = _libraries()
    url = _local_root(libraries).join(name)
    if not libraries.doesPathExist(url):
        return None
    return libraries.toolLibraryAtURL(url).count


def delete_library(name: str) -> bool:
    """Remove the Local library of this name. False when there was none."""
    libraries = _libraries()
    url = _local_root(libraries).join(name)
    if not libraries.doesPathExist(url):
        return False
    return libraries.deleteAsset(url)


def write_library(name: str, tools_json: list[str]) -> int:
    """Write the tools (each a Tool.toJson() string) as the Local library of
    this name, in place of any library already there. Returns how many tools
    the written library holds."""
    library = adsk.cam.ToolLibrary.createEmpty()
    for tool_json in tools_json:
        library.add(adsk.cam.Tool.createFromJson(tool_json))
    libraries = _libraries()
    # Importing over an existing name would make a second library, "<name> 1".
    delete_library(name)
    url = libraries.importToolLibrary(library, _local_root(libraries), name)
    # Fusion creates the library empty; updating it is what puts the tools in.
    if not libraries.updateToolLibrary(url, library):
        raise RuntimeError(f'Fusion did not write the tools into "{name}".')
    return libraries.toolLibraryAtURL(url).count
