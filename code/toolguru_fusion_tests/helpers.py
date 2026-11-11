"""Fixtures for the in-Fusion integration tests.

Every test document is a new, unsaved scratch document that is closed without
saving. The tools are made up; none comes from a real program.
"""

from __future__ import annotations

import json

import adsk.cam
import adsk.core
import adsk.fusion

END_MILL = {
    'type': 'flat end mill', 'unit': 'inches', 'BMC': 'carbide',
    'description': 'test half inch end mill',
    'geometry': {'DC': 0.5, 'NOF': 3, 'LCF': 1.25, 'shoulder-length': 1.25,
                 'OAL': 3.0, 'SFDM': 0.5, 'RE': 0, 'TA': 0, 'LB': 1.5},
    'post-process': {'number': 7},
}

DRILL = {
    'type': 'drill', 'unit': 'millimeters', 'BMC': 'hss',
    'description': 'test 5 mm drill',
    'geometry': {'DC': 5.0, 'NOF': 2, 'LCF': 40.0, 'shoulder-length': 40.0,
                 'OAL': 90.0, 'SFDM': 5.0, 'SIG': 118, 'LB': 50.0},
    'post-process': {'number': 12},
}

BALL_MILL = {
    'type': 'ball end mill', 'unit': 'millimeters', 'BMC': 'carbide',
    'description': 'test 6 mm ball mill',
    'geometry': {'DC': 6.0, 'NOF': 2, 'LCF': 12.0, 'shoulder-length': 12.0,
                 'OAL': 60.0, 'SFDM': 6.0, 'RE': 3.0, 'LB': 20.0},
    'post-process': {'number': 30},
}


def create_design_document() -> adsk.core.Document:
    """A new empty design document that has never been in Manufacturing."""
    app = adsk.core.Application.get()
    return app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)


def create_cam_document() -> tuple[adsk.core.Document, adsk.cam.CAM, adsk.cam.Setup]:
    """A new document with one body and one empty milling setup."""
    app = adsk.core.Application.get()
    doc = create_design_document()
    design = adsk.fusion.Design.cast(
        doc.products.itemByProductType('DesignProductType'))
    root = design.rootComponent
    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(0, 0, 0), adsk.core.Point3D.create(5, 5, 0))
    extrude_input = root.features.extrudeFeatures.createInput(
        sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(2.0))
    body = root.features.extrudeFeatures.add(extrude_input).bodies.item(0)

    # The CAM product only exists once the document has been in Manufacturing.
    app.userInterface.workspaces.itemById('CAMEnvironment').activate()
    cam = adsk.cam.CAM.cast(doc.products.itemByProductType('CAMProductType'))
    setup_input = cam.setups.createInput(adsk.cam.OperationTypes.MillingOperation)
    setup_input.models = [body]
    return doc, cam, cam.setups.add(setup_input)


def make_tool(definition: dict) -> adsk.cam.Tool:
    return adsk.cam.Tool.createFromJson(json.dumps(definition))


def add_operation(setup: adsk.cam.Setup, strategy: str,
                  definition: dict) -> adsk.cam.Operation:
    """Add an operation with no toolpath that uses the given tool."""
    operation_input = setup.operations.createInput(strategy)
    operation_input.tool = make_tool(definition)
    return setup.operations.add(operation_input)


def close_document(doc: adsk.core.Document) -> None:
    doc.close(False)
