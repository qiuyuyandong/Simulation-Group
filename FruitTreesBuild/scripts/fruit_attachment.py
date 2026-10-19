"""Calibrated mesh landmarks and branch-surface attachment, Blender 2.79/5.2.

The bundled apple's long stem is the negative-Z lambert2 component, not the
small positive-Z calyx. Orange uses the positive-Y Stub component. The mesh
and UVs stay unchanged; instances are oriented and translated about landmarks.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from blender_compat import LEGACY, transform, evaluated_surface, update_scene

ROOT = Path(__file__).resolve().parent.parent


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=2)
def profile_for(kind):
    data = json.loads((ROOT / 'assets/fruit_attachment_profiles.json').read_text(encoding='utf-8'))
    profile = data['profiles'][kind]
    source = ROOT / (profile['source_obj'] if LEGACY else 'assets/source_prototypes.blend')
    expected = profile['source_obj_sha256'] if LEGACY else data['source_prototype_sha256']
    if file_sha256(source) != expected:
        raise RuntimeError('Fruit prototype changed; recalibrate its attachment profile before generating.')
    return profile


def mean_point(points):
    return sum(points, Vector((0, 0, 0))) / len(points)


def material_faces(mesh, name):
    indices = [i for i, material in enumerate(mesh.materials)
               if material and material.name.split('.')[0] == name]
    if len(indices) != 1:
        raise RuntimeError('Missing/ambiguous fruit landmark material: ' + name)
    return [face for face in mesh.polygons if face.material_index == indices[0]]


def face_components(faces):
    adjacency = {}
    for face in faces:
        for index in face.vertices:
            adjacency.setdefault(index, set()).update(face.vertices)
    unseen = set(adjacency)
    result = []
    while unseen:
        first = min(unseen)
        unseen.remove(first)
        queue = [first]
        for current in queue:
            for neighbor in sorted(adjacency[current]):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
        result.append(sorted(queue))
    return result


def principal_axis(points, outward):
    center = mean_point(points)
    deltas = [point - center for point in points]
    covariance = [[sum(point[i] * point[j] for point in deltas) for j in range(3)] for i in range(3)]
    axis = outward.normalized()
    for iteration in range(32):
        updated = Vector(tuple(sum(covariance[i][j] * axis[j] for j in range(3)) for i in range(3)))
        if updated.length < 1e-12:
            raise RuntimeError('Degenerate stem geometry.')
        axis = updated.normalized()
    return axis if axis.dot(outward) >= 0 else -axis


def calibrate_mesh(mesh, kind):
    profile = profile_for(kind)
    if len(mesh.vertices) != profile['vertex_count'] or len(mesh.polygons) != profile['polygon_count']:
        raise RuntimeError('Fruit topology differs from the calibrated prototype.')
    body_faces = material_faces(mesh, profile['body_material'])
    body_indices = sorted({index for face in body_faces for index in face.vertices})
    body_points = [mesh.vertices[index].co for index in body_indices]
    body_center = Vector(tuple((min(point[i] for point in body_points) + max(point[i] for point in body_points)) / 2 for i in range(3)))
    stem_faces = material_faces(mesh, profile['stem_material'])
    candidates = []
    for component in face_components(stem_faces):
        points = [mesh.vertices[index].co for index in component]
        center = mean_point(points)
        side = profile['component_side_axis']
        if len(component) == profile['stem_component_vertex_count'] and (center[side] - body_center[side]) * profile['component_side_sign'] > 0:
            candidates.append(component)
    if len(candidates) != 1:
        raise RuntimeError('Could not uniquely identify the true stem; do not use the calyx as an attachment.')
    component = candidates[0]
    points = [mesh.vertices[index].co for index in component]
    center = mean_point(points)
    outward = center - body_center
    axis = principal_axis(points, outward) if profile['axis_method'] == 'stem_principal_axis' else outward.normalized()
    projections = [(point - center).dot(axis) for point in points]
    low, high = min(projections), max(projections)
    span = high - low
    if span < 1e-6:
        raise RuntimeError('No usable attachment feature extent.')
    base = mean_point([point for point, value in zip(points, projections) if value <= low + span * 0.08])
    tip_center = mean_point([point for point, value in zip(points, projections) if value >= high - span * 0.08])
    selected = set(component)
    polygons = [list(face.vertices) for face in stem_faces if all(index in selected for index in face.vertices)]
    feature = BVHTree.FromPolygons([vertex.co for vertex in mesh.vertices], polygons)
    tip, normal, face, distance = feature.ray_cast(tip_center + axis * span, -axis, span * 2)
    if tip is None or (tip - center).dot(axis) < high - span * 0.18:
        raise RuntimeError('Cannot locate the distal stem surface; attachment would be unreliable.')
    fruit_up = (base - body_center).normalized()
    if fruit_up.dot(axis) <= 0:
        raise RuntimeError('Inconsistent fruit stem/body axis.')
    return {'profile': profile, 'base': base, 'tip': tip, 'body_center': body_center,
            'outward_axis': axis, 'fruit_up_axis': fruit_up}


def wood_surface_bvh(root):
    update_scene()
    vertices, polygons = evaluated_surface(root)
    vertices = [transform(root.matrix_world, point) for point in vertices]
    return BVHTree.FromPolygons(vertices, polygons)


def place_at_branch(branch, rotation, scale, landmarks, wood):
    matrix = rotation.to_matrix()
    direction = transform(matrix, landmarks['outward_axis']).normalized()
    if direction.z <= 0.1:
        return None
    maximum = max(0.012, branch['radius'] * 5 + 0.006)
    surface, normal, face, distance = wood.ray_cast(branch['point'], -direction, maximum)
    if surface is None:
        return None
    # Snap the ray hit onto the nearest actual triangle. Custom tube meshes can
    # differ by a few microns between ray_cast and find_nearest; the recorded
    # anchor must be exactly on the saved wood surface for later verification.
    nearest, nearest_normal, nearest_face, nearest_distance = wood.find_nearest(surface)
    if nearest is not None and nearest_distance < 1e-4:
        surface = nearest
    profile = landmarks['profile']
    anchor = surface + direction * profile['wood_embed_m']
    endpoint = anchor - direction * profile['connector_length_m']
    # A skeleton point can lie outside a smoothed junction. Reject placements
    # where the reverse ray reaches another face first or misses the wood.
    contact, contact_normal, contact_face, contact_distance = wood.ray_cast(
        endpoint, direction, profile['connector_length_m'] + 1e-4)
    if contact is None or (contact - surface).length > 1e-4:
        return None
    location = endpoint - transform(matrix, landmarks['tip']) * scale
    center = location + transform(matrix, landmarks['body_center']) * scale
    if center.z >= surface.z:
        return None
    return {'location': location, 'surface': surface, 'anchor': anchor,
            'endpoint': endpoint, 'direction': direction}


def record_attachment(obj, landmarks, placement, spline_index, kind):
    obj['fruit_kind'] = kind
    obj['attachment_profile'] = landmarks['profile']['id']
    obj['stem_base_object'] = list(landmarks['base'])
    obj['stem_tip_object'] = list(landmarks['tip'])
    obj['fruit_up_axis_object'] = list(landmarks['fruit_up_axis'])
    obj['stem_outward_axis_object'] = list(landmarks['outward_axis'])
    inverse = obj.parent.matrix_world.inverted()
    obj['branch_surface_asset'] = list(transform(inverse, placement['surface']))
    obj['branch_anchor_asset'] = list(transform(inverse, placement['anchor']))
    obj['connection_spline_index'] = spline_index


def attachment_metadata(obj, root):
    matrix = transform(root.matrix_world.inverted(), obj.matrix_world)
    direction = transform(matrix.to_3x3(), Vector(obj['stem_outward_axis_object'])).normalized()
    return {'profile_id': obj['attachment_profile'],
            'stem_base_local_m': list(transform(matrix, Vector(obj['stem_base_object']))),
            'stem_tip_local_m': list(transform(matrix, Vector(obj['stem_tip_object']))),
            'branch_surface_local_m': list(obj['branch_surface_asset']),
            'branch_anchor_local_m': list(obj['branch_anchor_asset']),
            'direction_to_branch_local': list(direction),
            'connector_object_ref': 'Fruit_Stems',
            'connector_spline_index': int(obj['connection_spline_index'])}


def verify_connections(objects, root):
    fruits = [obj for obj in objects if obj.get('asset_role') == 'fruit']
    report = {'checked_fruits': len(fruits), 'maximum_endpoint_error_m': 0.0,
              'maximum_branch_surface_error_m': 0.0, 'minimum_fruit_up_dot_world_z': None}
    if not fruits:
        return report
    stems = next((obj for obj in objects if obj.name == 'Fruit_Stems'), None)
    if stems is None or len(stems.data.splines) != len(fruits):
        raise RuntimeError('Missing or incorrect fruit connector curves.')
    wood = wood_surface_bvh(root)
    cache, seen = {}, set()
    for obj in fruits:
        key = (obj.data.as_pointer(), obj.get('fruit_kind'))
        if key not in cache:
            cache[key] = calibrate_mesh(obj.data, key[1])
        landmarks = cache[key]
        if obj.get('attachment_profile') != landmarks['profile']['id']:
            raise RuntimeError('Missing/wrong fruit attachment calibration.')
        for property_name, key_name in (('stem_base_object', 'base'), ('stem_tip_object', 'tip')):
            if (Vector(obj[property_name]) - landmarks[key_name]).length > 1e-5:
                raise RuntimeError('Stored stem landmark no longer matches fruit geometry.')
        up = transform(obj.matrix_world.to_3x3(), landmarks['fruit_up_axis']).normalized()
        if up.z < 0.95:
            raise RuntimeError('Fruit is upside down or exceeds the intended hanging tilt: ' + obj.name)
        report['minimum_fruit_up_dot_world_z'] = up.z if report['minimum_fruit_up_dot_world_z'] is None else min(report['minimum_fruit_up_dot_world_z'], up.z)
        index = int(obj['connection_spline_index'])
        if index in seen or not 0 <= index < len(stems.data.splines):
            raise RuntimeError('Invalid fruit-to-connector identity.')
        seen.add(index)
        spline = stems.data.splines[index]
        if len(spline.points) != 2:
            raise RuntimeError('Unexpected connector representation.')
        start, end = [transform(stems.matrix_world, Vector(point.co[:3])) for point in spline.points]
        expected_end = transform(obj.matrix_world, landmarks['tip'])
        expected_start = transform(root.matrix_world, Vector(obj['branch_anchor_asset']))
        error = max((end - expected_end).length, (start - expected_start).length)
        report['maximum_endpoint_error_m'] = max(report['maximum_endpoint_error_m'], error)
        if error > 1e-5:
            raise RuntimeError('Connector is not attached to the real stem tip: ' + obj.name)
        delta = start - end
        direction = transform(obj.matrix_world.to_3x3(), landmarks['outward_axis']).normalized()
        if delta.length < 1e-6 or delta.normalized().dot(direction) < 0.999:
            raise RuntimeError('Connector direction is inconsistent with stem orientation.')
        if abs(delta.length - landmarks['profile']['connector_length_m']) > 1e-5:
            raise RuntimeError('Unexpected fruit connector length.')
        surface = transform(root.matrix_world, Vector(obj['branch_surface_asset']))
        nearest, normal, face, distance = wood.find_nearest(surface)
        if nearest is None or distance > 5e-5:
            raise RuntimeError('Recorded branch anchor is not on the actual wood surface.')
        report['maximum_branch_surface_error_m'] = max(report['maximum_branch_surface_error_m'], distance)
        hit, normal, face, distance = wood.ray_cast(end, direction, delta.length + 1e-4)
        if hit is None or (hit - surface).length > 1e-4:
            raise RuntimeError('Fruit connector does not reach the actual branch surface: ' + obj.name)
    return report
