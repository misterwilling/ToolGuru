"""Mock adsk modules for testing outside Fusion 360.

Call setup_adsk_modules() at module level BEFORE importing any code that
depends on adsk. This injects mock modules into sys.modules so that
`import adsk.core` etc. resolve to our mocks.

Extend the mock classes below as your add-in uses more of the Fusion API.
The pattern: create a class that mimics the Fusion type's interface (only
the methods/properties your code actually calls), then register it in
setup_adsk_modules().
"""

import sys
from unittest.mock import Mock


# ── Geometry mocks ─────────────────────────────────────────────────

class MockPoint3D:
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

    @classmethod
    def create(cls, x, y, z):
        return cls(x, y, z)

    def distanceTo(self, other):
        return ((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2) ** 0.5

    def __repr__(self):
        return f'MockPoint3D({self.x}, {self.y}, {self.z})'


class MockPoint2D:
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    @classmethod
    def create(cls, x, y):
        return cls(x, y)


class MockVector3D:
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

    @classmethod
    def create(cls, x, y, z):
        return cls(x, y, z)

    def crossProduct(self, other):
        return MockVector3D(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def dotProduct(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    def normalize(self):
        length = (self.x**2 + self.y**2 + self.z**2) ** 0.5
        if length > 1e-10:
            self.x /= length
            self.y /= length
            self.z /= length

    @property
    def length(self):
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5

    def copy(self):
        return MockVector3D(self.x, self.y, self.z)


class MockMatrix3D:
    def __init__(self):
        self._cells = [[1 if i == j else 0 for j in range(4)] for i in range(4)]

    @classmethod
    def create(cls):
        return cls()

    @property
    def translation(self):
        v = Mock()
        v.x = self._cells[0][3]
        v.y = self._cells[1][3]
        v.z = self._cells[2][3]
        return v

    @translation.setter
    def translation(self, vec):
        self._cells[0][3] = vec.x
        self._cells[1][3] = vec.y
        self._cells[2][3] = vec.z

    def getCell(self, row, col):
        return self._cells[row][col]

    def setToRotation(self, angle, axis, origin):
        pass

    def copy(self):
        m = MockMatrix3D()
        m._cells = [row[:] for row in self._cells]
        return m


class MockColor:
    @classmethod
    def create(cls, r, g, b, a):
        c = cls()
        c.red = r
        c.green = g
        c.blue = b
        c.alpha = a
        return c


# ── Collection mocks ──────────────────────────────────────────────

class MockCollection:
    """Generic counted collection matching Fusion's item(i)/count pattern."""
    def __init__(self, items=None):
        self._items = list(items or [])

    @property
    def count(self):
        return len(self._items)

    def item(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def __iter__(self):
        return iter(self._items)

    def add(self, item):
        self._items.append(item)


class MockObjectCollection:
    """Mock for adsk.core.ObjectCollection."""
    def __init__(self):
        self._items = []

    @classmethod
    def create(cls):
        return cls()

    def add(self, item):
        self._items.append(item)


# ── Attribute mocks ──────────────────────────────────────────────

class MockAttribute:
    """Mock for a single Fusion attribute."""
    def __init__(self, group, name, value):
        self.groupName = group
        self.name = name
        self.value = value


class MockAttributes:
    """Mock for entity.attributes collection."""
    def __init__(self):
        self._attrs = {}  # keyed by (group, name)

    def add(self, group, name, value):
        self._attrs[(group, name)] = MockAttribute(group, name, value)

    def itemByName(self, group, name):
        return self._attrs.get((group, name))


# ── Joint mocks ──────────────────────────────────────────────────

class MockJointOrigin:
    def __init__(self, name=''):
        self.name = name
        self.entityToken = f'token_jo_{name}'

    def createForAssemblyContext(self, occ):
        return self


class MockJointOrigins(MockCollection):
    pass


class MockJoint:
    _counter = 0

    def __init__(self, geo_or_origin_one=None, geo_or_origin_two=None):
        MockJoint._counter += 1
        self.name = ''
        self.isLightBulbOn = True
        self.entityToken = f'token_joint_{MockJoint._counter}'
        self.attributes = MockAttributes()
        self.geometryOrOriginOne = geo_or_origin_one
        self.geometryOrOriginTwo = geo_or_origin_two


class MockJointInput:
    def __init__(self):
        self.isFlipped = False
        self.angle = None

    def setAsRigidJointMotion(self):
        pass

    def setAsPlanarJointMotion(self, direction):
        pass


class MockJoints:
    def __init__(self):
        self._items = []

    @property
    def count(self):
        return len(self._items)

    def item(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def createInput(self, origin1, origin2):
        return MockJointInput()

    def add(self, joint_input):
        j = MockJoint()
        self._items.append(j)
        return j


# ── Component / Occurrence mocks ──────────────────────────────────

class MockComponent:
    def __init__(self, name=''):
        self.name = name
        # Fusion API uses "jointOrgins" (misspelled). Provide both.
        self.jointOrgins = MockJointOrigins()
        self.jointOrigins = self.jointOrgins  # alias
        self.joints = MockJoints()
        self.occurrences = MockCollection()
        self.allOccurrences = MockCollection()
        self.bRepBodies = MockCollection()
        self.xYConstructionPlane = Mock()
        self.xZConstructionPlane = Mock()
        self.yConstructionAxis = Mock()


class MockOccurrence:
    def __init__(self, name='', comp_name=None):
        self.name = name
        self.component = MockComponent(comp_name or name.split(':')[0])
        self.childOccurrences = MockCollection()
        self.entityToken = f'token_occ_{name}'
        self.assemblyContext = None
        self.attributes = MockAttributes()
        self.transform = MockMatrix3D()

    def add_child(self, child):
        """Helper for building test hierarchies."""
        self.childOccurrences._items.append(child)
        child.assemblyContext = self
        return child

    def add_joint_origin(self, jo_name):
        """Helper: add a joint origin to this occurrence's component."""
        jo = MockJointOrigin(jo_name)
        self.component.jointOrgins._items.append(jo)
        return jo


class MockDesign:
    def __init__(self):
        self.rootComponent = MockComponent('Root')
        self.rootComponent.joints = MockJoints()
        self._token_map = {}
        self.appearances = Mock()
        self.appearances.itemByName = Mock(return_value=None)

    def findEntityByToken(self, token):
        return self._token_map.get(token, [])

    def register_token(self, token, entity):
        """Helper: register an entity so findEntityByToken works."""
        self._token_map[token] = [entity]


# ── BRep geometry mocks ──────────────────────────────────────────

class MockBoundingBox2D:
    """Mock for adsk.core.BoundingBox2D (face parametric range)."""
    def __init__(self, min_x=0, min_y=0, max_x=1, max_y=1):
        self.minPoint = MockPoint2D(min_x, min_y)
        self.maxPoint = MockPoint2D(max_x, max_y)


class MockFaceEvaluator:
    """Mock for BRepFace.evaluator with parametric evaluation methods."""
    def __init__(self, centroid=None, normal=None, u_deriv=None, v_deriv=None):
        self._centroid = centroid or MockPoint3D(0, 0, 0)
        self._normal = normal or MockVector3D(0, 0, 1)
        self._u_deriv = u_deriv or MockVector3D(1, 0, 0)
        self._v_deriv = v_deriv or MockVector3D(0, 1, 0)
        self.parametricRange = MockBoundingBox2D()

    def getPointAtParameter(self, param):
        return (True, self._centroid)

    def getNormalAtParameter(self, param):
        return (True, self._normal)

    def getFirstDerivatives(self, params):
        return (True, [self._u_deriv.copy()], [self._v_deriv.copy()])


class MockBRepBody:
    """Mock for adsk.fusion.BRepBody."""
    pass


class MockBRepFace:
    """Mock for adsk.fusion.BRepFace with evaluator support."""
    def __init__(self, normal=None, centroid=None, u_deriv=None, v_deriv=None):
        self.evaluator = MockFaceEvaluator(
            centroid=centroid, normal=normal,
            u_deriv=u_deriv, v_deriv=v_deriv,
        )
        self.assemblyContext = None
        self.body = None
        self.name = ''
        self.entityToken = 'token_face'


class MockEdgeEvaluator:
    """Mock for BRepEdge.evaluator."""
    def __init__(self, midpoint=None):
        self._midpoint = midpoint or MockPoint3D(0, 0, 0)

    def getParameterExtents(self):
        return (True, 0.0, 1.0)

    def getPointAtParameter(self, param):
        return (True, self._midpoint)


class MockBRepEdge:
    """Mock for adsk.fusion.BRepEdge with evaluator support."""
    def __init__(self, midpoint=None):
        self.evaluator = MockEdgeEvaluator(midpoint=midpoint)
        self.assemblyContext = None
        self.entityToken = 'token_edge'


class MockSketchPoint:
    """Mock for adsk.fusion.SketchPoint — isinstance checks work."""
    def __init__(self, world_x=0, world_y=0, world_z=0):
        self.worldGeometry = MockPoint3D(world_x, world_y, world_z)


class MockConstructionPoint:
    """Mock for adsk.fusion.ConstructionPoint — isinstance checks work."""
    def __init__(self, x=0, y=0, z=0):
        self.geometry = MockPoint3D(x, y, z)


# ── Module setup ──────────────────────────────────────────────────

def setup_adsk_modules():
    """Install mock adsk modules into sys.modules.

    Call at module level before importing any code that depends on adsk.
    Returns (mock_adsk, mock_adsk_core, mock_adsk_fusion) for test access.
    """
    mock_adsk_core = Mock()
    mock_adsk_core.Matrix3D = MockMatrix3D
    mock_adsk_core.Vector3D = MockVector3D
    mock_adsk_core.Point3D = MockPoint3D
    mock_adsk_core.Point2D = MockPoint2D
    mock_adsk_core.Color = MockColor
    mock_adsk_core.ObjectCollection = MockObjectCollection
    mock_adsk_core.ValueInput = Mock()
    mock_adsk_core.ValueInput.createByReal = Mock(side_effect=lambda v: v)
    mock_adsk_core.ValueInput.createByString = Mock(side_effect=lambda s: s)
    mock_adsk_core.Application.get.return_value = Mock()
    mock_adsk_core.Application.get.return_value.userInterface = Mock()
    mock_adsk_core.LogLevels = Mock()
    mock_adsk_core.LogLevels.InfoLogLevel = 0
    mock_adsk_core.LogLevels.ErrorLogLevel = 2
    mock_adsk_core.LogTypes = Mock()
    mock_adsk_core.LogTypes.FileLogType = 0
    mock_adsk_core.LogTypes.ConsoleLogType = 1

    mock_adsk_fusion = Mock()
    mock_adsk_fusion.Design = MockDesign
    mock_adsk_fusion.Occurrence = MockOccurrence
    mock_adsk_fusion.Component = MockComponent
    mock_adsk_fusion.BRepBody = MockBRepBody
    mock_adsk_fusion.BRepFace = MockBRepFace
    mock_adsk_fusion.BRepEdge = MockBRepEdge
    mock_adsk_fusion.SketchPoint = MockSketchPoint
    mock_adsk_fusion.ConstructionPoint = MockConstructionPoint
    mock_adsk_fusion.FeatureOperations = Mock()
    mock_adsk_fusion.FeatureOperations.NewBodyFeatureOperation = 0
    mock_adsk_fusion.JointOrigin = MockJointOrigin
    mock_adsk_fusion.JointDirections = Mock()
    mock_adsk_fusion.JointDirections.ZAxisJointDirection = 0
    mock_adsk_fusion.JointGeometry = Mock()

    mock_adsk = Mock()
    mock_adsk.core = mock_adsk_core
    mock_adsk.fusion = mock_adsk_fusion

    sys.modules['adsk'] = mock_adsk
    sys.modules['adsk.core'] = mock_adsk_core
    sys.modules['adsk.fusion'] = mock_adsk_fusion

    return mock_adsk, mock_adsk_core, mock_adsk_fusion
