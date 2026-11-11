"""Shared test fixtures for Fusion integration tests.

Creates temporary Fusion documents with component hierarchies for testing.
Adapt create_test_document() to build the hierarchy your add-in expects.
"""

import adsk.core
import adsk.fusion


def create_test_document():
    """Create a new Fusion document with a test component hierarchy.

    Returns (doc, design, fixtures) where fixtures is a dict of named
    occurrences. Adapt the hierarchy below to match your add-in's expected
    component structure.

    Call close_test_document(doc) when done.
    """
    app = adsk.core.Application.get()
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent

    # Example: create container occurrences with child components.
    # Replace with your add-in's expected hierarchy.
    example_children = ['Child A', 'Child B', 'Child C']
    example_occ = _create_container(root, 'TestContainer', example_children)

    return doc, design, {
        'example_occ': example_occ,
    }


def close_test_document(doc):
    """Close a test document without saving."""
    try:
        doc.close(False)
    except:
        pass


def close_all_test_documents():
    """Close all unsaved/untitled documents left behind by failed tests."""
    app = adsk.core.Application.get()
    # Iterate in reverse since closing changes the collection
    for i in range(app.documents.count - 1, -1, -1):
        try:
            doc = app.documents.item(i)
            if not doc.isSaved or doc.name.startswith('Untitled'):
                doc.close(False)
        except:
            pass


def _create_container(root, container_name, child_names):
    """Create a container occurrence with named child components, each with a JointOrigin."""
    transform = adsk.core.Matrix3D.create()
    container_occ = root.occurrences.addNewComponent(transform)
    container_occ.component.name = container_name

    for child_name in child_names:
        child_occ = container_occ.component.occurrences.addNewComponent(transform)
        child_occ.component.name = child_name
        _add_joint_origin(child_occ.component, child_name)

    return container_occ


def _add_joint_origin(component, name):
    """Add a JointOrigin at the component origin."""
    geo = adsk.fusion.JointGeometry.createByPoint(component.originConstructionPoint)
    jo_input = component.jointOrgins.createInput(geo)
    jo = component.jointOrgins.add(jo_input)
    jo.name = name
    return jo


def create_body_with_face(design):
    """Create a simple box body and return one of its planar faces.

    Useful for tests that need a real BRepFace.
    Returns (body, face) or (None, None) on failure.
    """
    root = design.rootComponent
    sketch = root.sketches.add(root.xYConstructionPlane)
    lines = sketch.sketchCurves.sketchLines
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(0, 0, 0),
        adsk.core.Point3D.create(1, 1, 0),
    )
    profile = sketch.profiles.item(0)

    ext_input = root.features.extrudeFeatures.createInput(
        profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(1.0))
    extrude = root.features.extrudeFeatures.add(ext_input)

    body = extrude.bodies.item(0)
    face = body.faces.item(0)
    return body, face
