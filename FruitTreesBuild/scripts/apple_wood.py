"""Continuous apple wood: one trunk tube, flared branch tubes and checks.

The trunk is a single swept tube through the whole central leader, so branch
junctions cannot cut it into separate Skin islands. Branches start on the
parent surface with a short flared collar; the small base embedding is the only
intentional overlap. Branch-versus-trunk and branch-versus-branch capsule
checks report any deeper penetration.
"""
import bisect
import math

from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _chaikin(points, radii, iterations=1):
    points = [point.copy() for point in points]
    radii = list(radii)
    for _ in range(iterations):
        if len(points) < 3:
            break
        new_points = [points[0]]
        new_radii = [radii[0]]
        for index in range(len(points) - 1):
            first, second = points[index], points[index + 1]
            first_radius, second_radius = radii[index], radii[index + 1]
            new_points.append(first * 0.75 + second * 0.25)
            new_radii.append(first_radius * 0.75 + second_radius * 0.25)
            new_points.append(first * 0.25 + second * 0.75)
            new_radii.append(first_radius * 0.25 + second_radius * 0.75)
        new_points.append(points[-1])
        new_radii.append(radii[-1])
        points, radii = new_points, new_radii
    return points, radii


def _dedupe(points, radii):
    clean_points = [points[0]]
    clean_radii = [radii[0]]
    for point, radius in zip(points[1:], radii[1:]):
        if (point - clean_points[-1]).length > 1e-6:
            clean_points.append(point)
            clean_radii.append(radius)
    return clean_points, clean_radii


def _tangent(points, index):
    if index == 0:
        return (points[1] - points[0]).normalized()
    if index == len(points) - 1:
        return (points[-1] - points[-2]).normalized()
    incoming = (points[index] - points[index - 1]).normalized()
    outgoing = (points[index + 1] - points[index]).normalized()
    tangent = (incoming + outgoing).normalized()
    return tangent if tangent.length > 1e-8 else outgoing


def _sweep_path(points, radii, sides):
    """Parallel-transport a circular cross-section along one polyline."""
    points, radii = _dedupe(points, radii)
    if len(points) < 2:
        return [], [], []
    vertices, faces, smooth = [], [], []
    rings = []
    previous_tangent = None
    previous_side = None
    for index, point in enumerate(points):
        tangent = _tangent(points, index)
        if index == 0:
            tangent = Vector((0.0, 0.0, 1.0)) if abs(tangent.z) > 0.85 else tangent
        if previous_side is None:
            reference = Vector((0.0, 0.0, 1.0)) if abs(tangent.z) < 0.9 else Vector((0.0, 1.0, 0.0))
            side = tangent.cross(reference)
            if side.length < 1e-8:
                side = Vector((1.0, 0.0, 0.0))
            side.normalize()
        else:
            side = previous_tangent.rotation_difference(tangent) @ previous_side
            side = (side - tangent * side.dot(tangent))
            if side.length < 1e-8:
                side = tangent.cross(Vector((0.0, 1.0, 0.0)))
            side.normalize()
        other = tangent.cross(side).normalized()
        ring = []
        for step in range(sides):
            angle = 2.0 * math.pi * step / sides
            ring.append(len(vertices))
            vertices.append(tuple(point + radii[index] * (side * math.cos(angle) + other * math.sin(angle))))
        rings.append(ring)
        previous_tangent, previous_side = tangent, side
    faces.append(tuple(reversed(rings[0])))
    smooth.append(False)
    faces.append(tuple(rings[-1]))
    smooth.append(False)
    for first, second in zip(rings, rings[1:]):
        for step in range(sides):
            following = (step + 1) % sides
            faces.append((first[step], first[following], second[following], second[step]))
            smooth.append(True)
    return vertices, faces, smooth


def _closest_on_polyline(point, points, radii):
    best = (None, None, None)
    for index in range(len(points) - 1):
        first, second = points[index], points[index + 1]
        segment = second - first
        length_squared = segment.length_squared
        if length_squared < 1e-12:
            continue
        fraction = max(0.0, min(1.0, (point - first).dot(segment) / length_squared))
        closest = first + segment * fraction
        distance = (point - closest).length
        radius = radii[index] * (1.0 - fraction) + radii[index + 1] * fraction
        if best[0] is None or distance < best[0]:
            best = (distance, closest, radius)
    if best[0] is None:
        closest = points[0]
        return (point - closest).length, closest, radii[0]
    return best


def _path_children(parent):
    children = {}
    for node, ancestor in parent.items():
        if ancestor is not None:
            children.setdefault(ancestor, []).append(node)
    return children


def _path_topology(points, parent):
    children = _path_children(parent)
    root = next(index for index, ancestor in parent.items() if ancestor is None)
    order = [root]
    for node in order:
        order.extend(children.get(node, ()))
    top_z = [point.z for point in points]
    for node in reversed(order[1:]):
        ancestor = parent[node]
        if top_z[node] > top_z[ancestor]:
            top_z[ancestor] = top_z[node]
    return children, root, order, top_z


def _heavy_child(children, top_z, node):
    kids = children.get(node, ())
    if not kids:
        return None
    return max(kids, key=lambda kid: (top_z[kid], kid))


def segment_sampler(segments, minimum_height, maximum_radius=0.035, include_trunk=True):
    """Weighted sampler over the actual trunk/branch tube centerlines."""
    candidates = []
    cumulative = []
    total = 0.0
    for segment in segments:
        if not include_trunk and segment.get('trunk'):
            continue
        first, second = segment['a'], segment['b']
        if min(first.z, second.z) < minimum_height:
            continue
        radius = (segment['ra'] + segment['rb']) * 0.5
        if radius > maximum_radius:
            continue
        weight = (second - first).length / (1.0 + radius / 0.008) ** 1.5
        if weight <= 0.0:
            continue
        total += weight
        candidates.append(segment)
        cumulative.append(total)
    if not candidates:
        raise RuntimeError('No suitable crown segments on the continuous wood; '
                           'reduce trunk height or clearance.')

    def sample(rng, with_branch=False):
        index = min(bisect.bisect_left(cumulative, rng.random() * total), len(candidates) - 1)
        segment = candidates[index]
        fraction = rng.uniform(0.08, 0.92)
        point = segment['a'].lerp(segment['b'], fraction)
        if with_branch:
            return {'point': point,
                    'radius': segment['ra'] * (1.0 - fraction) + segment['rb'] * fraction,
                    'tangent': (segment['b'] - segment['a']).normalized(),
                    'length': (segment['b'] - segment['a']).length,
                    'edge_id': segment['id'],
                    'fraction': fraction}
        return point
    return sample


def build_wood_paths(points, parent, radii, crown_offset, root):
    """Split the SCA tree into one continuous trunk and branch paths."""
    crown_points = points[crown_offset:]
    crown_radii = radii[crown_offset:]
    children, root, order, top_z = _path_topology(crown_points, parent)
    trunk_nodes = [root]
    node = root
    while True:
        heavy = _heavy_child(children, top_z, node)
        if heavy is None:
            break
        trunk_nodes.append(heavy)
        node = heavy
    trunk_set = set(trunk_nodes)
    branch_paths = []
    visited = set(trunk_nodes)

    def collect(start, parent_node):
        nodes = []
        node = start
        while node not in visited:
            visited.add(node)
            nodes.append(node)
            kids = [kid for kid in children.get(node, ()) if kid not in visited]
            if not kids:
                break
            heavy = max(kids, key=lambda kid: (top_z[kid], kid))
            for side in kids:
                if side != heavy:
                    collect(side, node)
            node = heavy
        if nodes:
            branch_paths.append({'parent_node': parent_node, 'nodes': nodes})

    for node in trunk_nodes:
        for child in children.get(node, ()):
            if child not in visited:
                collect(child, node)

    # Trunk path: base chain plus the leading crown path. The crown root is
    # coincident with the last base point, so it is omitted.
    trunk_points = [points[index].copy() for index in range(crown_offset)]
    trunk_radii = [radii[index] for index in range(crown_offset)]
    for node in trunk_nodes[1:]:
        trunk_points.append(crown_points[node].copy())
        trunk_radii.append(crown_radii[node])
    trunk_points, trunk_radii = _chaikin(trunk_points, trunk_radii, 2)
    trunk_points, trunk_radii = _dedupe(trunk_points, trunk_radii)

    paths = []
    path_index = {'trunk': 0}
    for node in trunk_nodes:
        path_index[node] = 0
    for path_number, branch in enumerate(branch_paths, start=1):
        raw_points = [crown_points[node].copy() for node in branch['nodes']]
        raw_radii = [crown_radii[node] for node in branch['nodes']]
        if len(raw_points) == 1:
            branch_points = raw_points
            branch_radii = raw_radii
        else:
            branch_points, branch_radii = _chaikin(raw_points, raw_radii, 1)
        paths.append({'points': branch_points, 'radii': branch_radii,
                      'parent_node': branch['parent_node'], 'index': path_number,
                      'nodes': branch['nodes']})
        for node in branch['nodes']:
            path_index[node] = path_number
    for path in paths:
        path['parent_path'] = path_index[path['parent_node']]
    return trunk_points, trunk_radii, paths


def build_apple_wood(points, parent, radii, crown_offset, root, args):
    trunk_points, trunk_radii, paths = build_wood_paths(points, parent, radii,
                                                       crown_offset, root)
    path_lookup = {0: (trunk_points, trunk_radii)}
    for path in paths:
        path_lookup[path['index']] = (path['points'], path['radii'])

    # Prepend a surface contact + flared collar to every branch. The first
    # ring is deliberately inside the parent by a sub-millimetre amount so the
    # cap cannot show; the next ring is the real branch start.
    for path in reversed(paths):
        parent_points, parent_radii = path_lookup[path['parent_path']]
        branch_start = path['points'][0]
        distance, parent_point, parent_radius = _closest_on_polyline(
            branch_start, parent_points, parent_radii)
        direction = branch_start - parent_point
        if direction.length < 1e-7:
            direction = (path['points'][1] - path['points'][0]) if len(path['points']) > 1 else Vector((0.0, 0.0, 1.0))
        direction.normalize()
        embed = min(0.0015, parent_radius * 0.15)
        surface = parent_point + direction * max(parent_radius - embed, parent_radius * 0.5)
        base_radius = max(path['radii'][0] * 1.22, 0.0015)
        path['surface'] = surface
        path['surface_radius'] = base_radius
        path['parent_surface_distance'] = distance
        path['points'] = [surface] + path['points']
        path['radii'] = [base_radius] + path['radii']
        path_lookup[path['index']] = (path['points'], path['radii'])

    # Capsule checks: skip the first segment (intended surface embedding).
    # A branch can cross the leader between two vertices, so repair whole
    # segments by inserting a pushed-out point at the deepest violation.
    margin = 0.0005
    repaired = 0
    maximum_shift = 0.0
    for _ in range(5):
        changed = False
        for path in paths:
            old_points = path['points']
            old_radii = path['radii']
            new_points = [old_points[0]]
            new_radii = [old_radii[0]]
            for index in range(1, len(old_points) - 1):
                first, second = old_points[index], old_points[index + 1]
                first_radius, second_radius = old_radii[index], old_radii[index + 1]
                worst = None
                for fraction in (0.25, 0.5, 0.75):
                    sample = first.lerp(second, fraction)
                    distance, trunk_point, trunk_radius = _closest_on_polyline(
                        sample, trunk_points, trunk_radii)
                    branch_radius = first_radius * (1.0 - fraction) + second_radius * fraction
                    required = trunk_radius + branch_radius + margin
                    if distance < required:
                        violation = required - distance
                        if worst is None or violation > worst[0]:
                            worst = (violation, sample, required, trunk_point)
                if worst is not None:
                    _, sample, required, trunk_point = worst
                    direction = sample - trunk_point
                    if direction.length < 1e-8:
                        direction = second - first
                    if direction.length > 1e-8:
                        inserted = trunk_point + direction.normalized() * required
                        maximum_shift = max(maximum_shift, (inserted - sample).length)
                        new_points.append(inserted)
                        new_radii.append((first_radius + second_radius) * 0.5)
                        repaired += 1
                        changed = True
                new_points.append(second)
                new_radii.append(second_radius)
            path['points'] = new_points
            path['radii'] = new_radii
        if not changed:
            break
    trunk_hits = []
    for path in paths:
        cumulative = 0.0
        for index in range(1, len(path['points']) - 1):
            first, second = path['points'][index], path['points'][index + 1]
            cumulative += (second - first).length
            if cumulative < max(0.012, path['surface_radius'] * 2.0):
                continue
            for fraction in (0.25, 0.5, 0.75):
                sample = first.lerp(second, fraction)
                distance, _, trunk_radius = _closest_on_polyline(
                    sample, trunk_points, trunk_radii)
                branch_radius = path['radii'][index] * (1.0 - fraction) + path['radii'][index + 1] * fraction
                if distance < trunk_radius + branch_radius + margin:
                    trunk_hits.append({'branch': path['index'], 'point_index': index,
                                       'clearance_m': round(distance - trunk_radius - branch_radius, 6)})
                    break
    branch_hits = []
    for first in range(len(paths)):
        for second in range(first + 1, len(paths)):
            if paths[first]['parent_path'] == paths[second]['index'] or \
                    paths[second]['parent_path'] == paths[first]['index']:
                continue
            for index in range(2, len(paths[first]['points'])):
                distance, _, other_radius = _closest_on_polyline(
                    paths[first]['points'][index], paths[second]['points'], paths[second]['radii'])
                if distance < other_radius + paths[first]['radii'][index] + margin:
                    branch_hits.append({'first': paths[first]['index'],
                                        'second': paths[second]['index'],
                                        'point_index': index})
                    break

    vertices, faces, smooth = [], [], []
    trunk_verts, trunk_faces, trunk_smooth = _sweep_path(trunk_points, trunk_radii, 16)
    trunk_bvh = BVHTree.FromPolygons([Vector(vertex) for vertex in trunk_verts],
                                     [list(face) for face in trunk_faces])
    offset = len(vertices)
    vertices.extend(trunk_verts)
    faces.extend(tuple(index + offset for index in face) for face in trunk_faces)
    smooth.extend(trunk_smooth)
    mesh_trunk_hits = []
    for path in paths:
        path_verts, path_faces, path_smooth = _sweep_path(path['points'], path['radii'], 8)
        # Exclude the first two rings (intentional surface embedding) from the
        # exact triangle overlap check.
        test_faces = [face for face in path_faces if min(face) >= 16]
        if test_faces and trunk_bvh is not None:
            branch_bvh = BVHTree.FromPolygons([Vector(vertex) for vertex in path_verts],
                                              [list(face) for face in test_faces])
            overlaps = trunk_bvh.overlap(branch_bvh)
            if overlaps:
                mesh_trunk_hits.append({'branch': path['index'],
                                        'face_pairs': len(overlaps),
                                        'first_pair': list(overlaps[0])})
        offset = len(vertices)
        vertices.extend(path_verts)
        faces.extend(tuple(index + offset for index in face) for face in path_faces)
        smooth.extend(path_smooth)

    import bpy
    mesh = bpy.data.meshes.new('Apple_Wood')
    # Triangulate explicitly so ray_cast and find_nearest use the same surface
    # triangles (non-planar tube quads can otherwise differ by a few microns).
    triangles, triangle_smooth = [], []
    for face, is_smooth in zip(faces, smooth):
        if len(face) == 3:
            triangles.append(face)
            triangle_smooth.append(is_smooth)
        elif len(face) == 4:
            triangles.append((face[0], face[1], face[2]))
            triangles.append((face[0], face[2], face[3]))
            triangle_smooth.extend((is_smooth, is_smooth))
        else:
            for index in range(1, len(face) - 1):
                triangles.append((face[0], face[index], face[index + 1]))
                triangle_smooth.append(is_smooth)
    mesh.from_pydata(vertices, [], triangles)
    mesh.update()
    for polygon, is_smooth in zip(mesh.polygons, triangle_smooth):
        polygon.use_smooth = is_smooth
    mesh.validate()
    if not mesh.polygons:
        raise RuntimeError('Apple wood mesh generation produced no faces.')
    segments = []
    segment_id = 0
    for path_number, (path_points, path_radii) in enumerate(
            [(trunk_points, trunk_radii)] + [(path['points'], path['radii']) for path in paths]):
        # The first branch segment is the intentional surface embed/collar;
        # leaves and fruits should sample the visible branch beyond it.
        start = 0 if path_number == 0 else 1
        for index in range(start, len(path_points) - 1):
            first, second = path_points[index], path_points[index + 1]
            if (second - first).length < 1e-6:
                continue
            segments.append({'a': first.copy(), 'b': second.copy(),
                             'ra': path_radii[index], 'rb': path_radii[index + 1],
                             'id': segment_id, 'trunk': path_number == 0})
            segment_id += 1
    report = {
        'wood_geometry_method': 'continuous_trunk_parallel_transport_tubes_v1',
        'trunk_centerline_vertex_count': len(trunk_points),
        'trunk_tube_sides': 16,
        'branch_path_count': len(paths),
        'branch_tube_sides': 8,
        'branch_base_flare_count': len(paths),
        'branch_trunk_intersection_count': len(trunk_hits),
        'branch_trunk_mesh_intersection_count': len(mesh_trunk_hits),
        'branch_branch_intersection_count': len(branch_hits),
        'branch_base_embed_m': 0.0015,
        'branch_trunk_repair_count': repaired,
        'branch_trunk_max_repair_shift_m': round(maximum_shift, 6),
        'branch_trunk_intersection_samples': trunk_hits[:20],
        'branch_trunk_mesh_intersection_samples': mesh_trunk_hits[:20],
        'branch_branch_intersection_samples': branch_hits[:20],
        'wood_mesh_vertices': len(vertices),
        'wood_mesh_faces': len(faces),
        'wood_sampling_segment_count': len(segments),
    }
    if trunk_hits:
        raise RuntimeError('Branch/trunk capsule penetration remains: {} hits. '
                           'Reduce branch reach or move the branch base outward.'.format(len(trunk_hits)))
    if mesh_trunk_hits:
        raise RuntimeError('Branch/trunk triangle penetration remains: {} branches. '
                           'Samples: {}'.format(len(mesh_trunk_hits), mesh_trunk_hits[:5]))
    return mesh, report, segments
