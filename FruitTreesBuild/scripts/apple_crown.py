"""Apple crown placement: surface-attached leaves and overlap avoidance.

The checks here are deliberately conservative geometry proxies, not a physics
simulation. Leaves are cards with a capsule proxy; fruits use their actual
body vertices. Placement rejects a candidate instead of silently dropping an
instance, so a failed capacity stops the build with a clear message.
"""
import math

from mathutils import Matrix, Quaternion, Vector

from citrus_geometry import FruitClearance, verify_leaf_fruit_clearance


def mesh_dimensions(mesh):
    xs = [vertex.co.x for vertex in mesh.vertices]
    ys = [vertex.co.y for vertex in mesh.vertices]
    zs = [vertex.co.z for vertex in mesh.vertices]
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def _clamp(value, low, high):
    return max(low, min(high, value))


def _segment_distance(first, second, third, fourth):
    """Closest distance between segments [first, second] and [third, fourth]."""
    d1 = second - first
    d2 = fourth - third
    r = first - third
    a = d1.dot(d1)
    e = d2.dot(d2)
    f = d2.dot(r)
    if a <= 1e-12 and e <= 1e-12:
        return (first - third).length
    if a <= 1e-12:
        s = 0.0
        t = _clamp(f / e, 0.0, 1.0)
    else:
        c = d1.dot(r)
        if e <= 1e-12:
            t = 0.0
            s = _clamp(-c / a, 0.0, 1.0)
        else:
            b = d1.dot(d2)
            denominator = a * e - b * b
            s = _clamp((b * f - c * e) / denominator, 0.0, 1.0) if abs(denominator) > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t = 0.0
                s = _clamp(-c / a, 0.0, 1.0)
            elif t > 1.0:
                t = 1.0
                s = _clamp((b - c) / a, 0.0, 1.0)
    return ((first + d1 * s) - (third + d2 * t)).length


class LeafCapsuleIndex:
    """Spatial hash of leaf midrib capsules."""

    def __init__(self, cell_size):
        self.cell_size = max(0.02, cell_size)
        self.cells = {}
        self.entries = {}
        self.next_id = 0

    def _range(self, lower, upper):
        size = self.cell_size
        start = [math.floor(lower[i] / size) for i in range(3)]
        end = [math.floor(upper[i] / size) for i in range(3)]
        for x in range(start[0], end[0] + 1):
            for y in range(start[1], end[1] + 1):
                for z in range(start[2], end[2] + 1):
                    yield x, y, z

    def add(self, base, tip, radius, name):
        identifier = self.next_id
        self.next_id += 1
        self.entries[identifier] = (base.copy(), tip.copy(), radius, name)
        lower = Vector(tuple(min(base[i], tip[i]) - radius for i in range(3)))
        upper = Vector(tuple(max(base[i], tip[i]) + radius for i in range(3)))
        for cell in self._range(lower, upper):
            self.cells.setdefault(cell, []).append(identifier)
        return identifier

    def conflicts(self, base, tip, radius, clearance, exclude=None):
        lower = Vector(tuple(min(base[i], tip[i]) - radius - clearance for i in range(3)))
        upper = Vector(tuple(max(base[i], tip[i]) + radius + clearance for i in range(3)))
        seen = set()
        for cell in self._range(lower, upper):
            for identifier in self.cells.get(cell, ()):
                if identifier == exclude or identifier in seen:
                    continue
                seen.add(identifier)
                other_base, other_tip, other_radius, _ = self.entries[identifier]
                if _segment_distance(base, tip, other_base, other_tip) < radius + other_radius + clearance - 1e-9:
                    return True
        return False

    def nearest(self, base, tip, exclude=None):
        best = None
        for identifier, (other_base, other_tip, _, _) in self.entries.items():
            if identifier == exclude:
                continue
            distance = _segment_distance(base, tip, other_base, other_tip)
            best = distance if best is None else min(best, distance)
        return best


def _leaf_direction(branch, rng):
    tangent = branch['tangent'].normalized()
    reference = Vector((0.0, 0.0, 1.0)) if abs(tangent.z) < 0.85 else Vector((0.0, 1.0, 0.0))
    side = tangent.cross(reference)
    if side.length < 1e-8:
        side = Vector((1.0, 0.0, 0.0))
    side.normalize()
    other = tangent.cross(side).normalized()
    angle = rng.uniform(0.0, 2.0 * math.pi)
    radial = side * math.cos(angle) + other * math.sin(angle)
    direction = (radial * 0.9 + Vector((0.0, 0.0, 0.55))
                 + tangent * rng.uniform(-0.2, 0.25)).normalized()
    if direction.z < 0.0:
        direction = (direction + Vector((0.0, 0.0, 0.8))).normalized()
    return direction


def _leaf_rotation(direction, tangent, rng):
    axis = (direction + Vector((0.0, 0.0, 0.35))
            + tangent * rng.uniform(-0.2, 0.2)).normalized()
    normal = Vector((0.0, 0.0, 1.0)) - axis * axis.z
    if normal.length < 0.15:
        normal = tangent.cross(axis)
    normal.normalize()
    normal = Quaternion(axis, rng.uniform(-0.65, 0.65)) @ normal
    normal.normalize()
    side = normal.cross(axis).normalized()
    normal = axis.cross(side).normalized()
    return Matrix((axis, side, normal)).transposed().to_euler()


def place_apple_leaf(branch, rng, wood, leaf_mesh, dimensions, index,
                     fruit_clearance, leaf_spacing, stats):
    length, width, _ = dimensions
    point = branch['point']
    tangent = branch['tangent'].normalized()
    reach = max(0.02, branch['radius'] * 4.0 + 0.01)
    direction = _leaf_direction(branch, rng)
    outside = point + direction * reach
    surface, normal, face, distance = wood.ray_cast(outside, -direction, reach * 2.0)
    if surface is None or distance > reach * 1.35 or normal.dot(direction) < 0.05:
        stats['wood_rejections'] += 1
        return None
    base = surface - direction * 0.0015
    if wood.find_nearest(base)[3] > 0.0035:
        stats['wood_rejections'] += 1
        return None
    rotation = _leaf_rotation(direction, tangent, rng)
    scale = rng.uniform(0.8, 1.15)
    matrix = Matrix.Translation(base) @ rotation.to_matrix().to_4x4() @ Matrix.Scale(scale, 4)
    # Check the blade, not only its base. A branch crossing the card is rejected.
    samples = ((0.30, 0.0), (0.55, 0.0), (0.80, 0.0), (1.0, 0.0),
               (0.75, 0.35), (0.75, -0.35))
    for along, across in samples:
        local = Vector((length * along, width * across, 0.0))
        if wood.find_nearest(matrix @ local)[3] < 0.0025:
            stats['wood_rejections'] += 1
            return None
    tip = matrix @ Vector((length, 0.0, 0.0))
    proxy_radius = max(0.002, width * 0.12 * scale)
    if index.conflicts(base, tip, proxy_radius, leaf_spacing):
        stats['leaf_rejections'] += 1
        return None
    if fruit_clearance is not None and fruit_clearance.conflicts(leaf_mesh, matrix):
        stats['fruit_rejections'] += 1
        return None
    return {'location': base, 'rotation': rotation, 'scale': scale, 'mesh': leaf_mesh,
            'tip': tip, 'radius': proxy_radius}


def populate_apple_leaves(sample_leaf, rng, wood, leaf_meshes, dimensions,
                          fruit_clearance, args):
    index = LeafCapsuleIndex(max(0.08, args.leaf_length * 0.75))
    placements = []
    stats = {'attempts': 0, 'wood_rejections': 0, 'leaf_rejections': 0,
             'fruit_rejections': 0, 'maximum_attempts_per_leaf': 0}
    for leaf_number in range(args.leaf_count):
        for attempt in range(160):
            stats['attempts'] += 1
            stats['maximum_attempts_per_leaf'] = max(stats['maximum_attempts_per_leaf'], attempt + 1)
            branch = sample_leaf(rng, with_branch=True)
            mesh = rng.choice(leaf_meshes)
            placement = place_apple_leaf(branch, rng, wood, mesh, dimensions[mesh.name],
                                         index, fruit_clearance, args.leaf_spacing, stats)
            if placement is None:
                continue
            placement['proxy_id'] = index.add(placement['location'], placement['tip'],
                                              placement['radius'], mesh.name)
            placements.append(placement)
            break
        else:
            raise RuntimeError(
                'Leaf overlap capacity reached at leaf {} of {} after {} attempts '
                '({} wood, {} leaf, {} fruit rejections). Lower leafCount or leafSpacing, '
                'or increase branch density; no leaves were silently dropped.'.format(
                    leaf_number + 1, args.leaf_count, stats['attempts'],
                    stats['wood_rejections'], stats['leaf_rejections'],
                    stats['fruit_rejections']))
    stats['leaf_spacing_m'] = args.leaf_spacing
    stats['leaf_proxy_radius_fraction'] = 0.12
    return placements, stats, index


def fruit_clear_of_wood(center, radius, wood, clearance=0.002):
    if wood.find_nearest(center)[3] < radius * 0.9 + clearance:
        return False
    for axis in (Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0))):
        for sign in (-1.0, 1.0):
            if wood.find_nearest(center + axis * radius * 0.7 * sign)[3] < clearance:
                return False
    return True


def verify_apple_leaves(placements, index, wood, leaves, fruits, leaf_spacing,
                        fruit_clearance):
    maximum_base = 0.0
    conflicts = 0
    for placement in placements:
        base = placement['location']
        maximum_base = max(maximum_base, wood.find_nearest(base)[3])
        if index.conflicts(base, placement['tip'], placement['radius'], leaf_spacing,
                           exclude=placement['proxy_id']):
            conflicts += 1
    if conflicts:
        raise RuntimeError('Leaf capsules overlap after placement: ' + str(conflicts))
    fruit_check = verify_leaf_fruit_clearance(leaves, fruits, fruit_clearance)
    return {'checked_leaves': len(leaves),
            'maximum_base_surface_distance_m': maximum_base,
            'leaf_capsule_overlap_count': conflicts,
            'fruit_clearance': fruit_check,
            'method': 'leaf midrib capsules for leaf/leaf; six blade samples for leaf/wood; '
                      'actual fruit spheres for leaf/fruit',
            'scope': 'conservative geometry separation, not a full mesh-intersection proof'}
