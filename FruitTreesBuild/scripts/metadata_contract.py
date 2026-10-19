"""Blender-independent metadata validation and local-to-world math (Python 3.5+)."""
import math
import re

SCHEMA_VERSION = '1.0.0'
ASSET_SCHEMA_VERSION = '3.0.0'
MATURITY_STAGES = ('unknown', 'unripe', 'turning', 'ripe')
COORDINATE_SYSTEM = {
    'unit': 'm', 'handedness': 'right', 'up_axis': '+Z',
    'axes': {'x': '+X', 'y': '+Y', 'z': '+Z'},
    'origin': 'tree_root_base',
    'matrix_convention': 'row_major_4x4_column_vectors',
    'bounds_definition': 'axis_aligned_min_max_of_evaluated_geometry_in_named_frame',
    'center_definition': 'midpoint_of_local_axis_aligned_bounds',
}


def vector3(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError('Expected a 3D vector.')
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in value):
        raise ValueError('Coordinates must be finite numbers.')
    return value


def bounds_from_points(points):
    points = list(points)
    if not points:
        raise ValueError('Cannot describe empty geometry.')
    for point in points:
        vector3(point)
    return {'min': [min(point[i] for point in points) for i in range(3)],
            'max': [max(point[i] for point in points) for i in range(3)]}


def validate_bounds(bounds):
    lower, upper = vector3(bounds['min']), vector3(bounds['max'])
    if any(a > b for a, b in zip(lower, upper)):
        raise ValueError('Bounds min exceeds max.')


def bounds_center(bounds):
    validate_bounds(bounds)
    return [(a + b) / 2 for a, b in zip(bounds['min'], bounds['max'])]


def validate_transform(matrix):
    if not isinstance(matrix, (list, tuple)) or len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise ValueError('Expected a 4x4 affine matrix.')
    for row in matrix:
        vector3(row[:3])
        if isinstance(row[3], bool) or not isinstance(row[3], (int, float)) or not math.isfinite(row[3]):
            raise ValueError('Matrix entries must be finite numbers.')
    if any(abs(a - b) > 1e-8 for a, b in zip(matrix[3], [0, 0, 0, 1])):
        raise ValueError('Expected an affine homogeneous matrix.')
    a, b, c = [row[:3] for row in matrix[:3]]
    determinant = a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])
    if determinant <= 1e-12:
        raise ValueError('Instance transform must be non-singular and non-mirrored.')


def transform_point(matrix, point):
    validate_transform(matrix)
    vector3(point)
    return [sum(matrix[i][j] * point[j] for j in range(3)) + matrix[i][3] for i in range(3)]


def validate_unit_frame(matrix):
    """A root-local metre frame permits translation/rotation, not hidden scale."""
    validate_transform(matrix)
    columns = [[matrix[row][column] for row in range(3)] for column in range(3)]
    if any(abs(sum(a * b for a, b in zip(columns[i], columns[j])) - (1.0 if i == j else 0.0)) > 1e-5
           for i in range(3) for j in range(3)):
        raise ValueError('The asset root must have unit scale and no shear; apply scale before saving.')
    return matrix


def transform_bounds(matrix, bounds):
    """Conservative AABB of the transformed local box, not re-evaluated mesh."""
    validate_bounds(bounds)
    corners = [(x, y, z) for x in (bounds['min'][0], bounds['max'][0])
               for y in (bounds['min'][1], bounds['max'][1])
               for z in (bounds['min'][2], bounds['max'][2])]
    return bounds_from_points(transform_point(matrix, corner) for corner in corners)


def relative_file(value):
    if not isinstance(value, str) or not value or '\\' in value or value.startswith('/') or re.match(r'^[A-Za-z]:', value):
        raise ValueError('Use forward-slash relative metadata paths, not machine-specific absolute paths.')


def validate_asset(data):
    """Validate appearance metadata; schema-2 historical extensions are NOT checked."""
    required = ('schema_version', 'asset_id', 'asset_version', 'model_file', 'asset_root',
                'category', 'biological_info', 'coordinate_system', 'bounds_local',
                'parts_summary', 'fruits', 'generation', 'provenance', 'quality', 'model_sha256')
    for field in required:
        if field not in data:
            raise ValueError('Missing asset field: ' + field)
    if data['schema_version'] not in (SCHEMA_VERSION, '1.1.0', '2.0.0', ASSET_SCHEMA_VERSION):
        raise ValueError('Unsupported asset schema.')
    for field in ('asset_id', 'asset_version'):
        if not isinstance(data[field], str) or not data[field]:
            raise ValueError('Empty asset identity.')
    relative_file(data['model_file'])
    if data['coordinate_system'] != COORDINATE_SYSTEM:
        raise ValueError('Unsupported asset coordinate convention.')
    validate_bounds(data['bounds_local'])
    if not re.match(r'^[0-9a-f]{64}$', data['model_sha256']):
        raise ValueError('Invalid model checksum.')
    counts = data['parts_summary']
    for field in ('fruit_count', 'leaf_count'):
        if isinstance(counts[field], bool) or not isinstance(counts[field], int) or counts[field] < 0:
            raise ValueError('Counts must be non-negative integers.')
    if counts['fruit_count'] != len(data['fruits']):
        raise ValueError('Fruit count does not match fruit records.')
    identifiers, objects, splines = set(), set(), set()
    for fruit in data['fruits']:
        fruit_id, object_ref = fruit['fruit_id'], fruit['object_ref']
        if (not isinstance(fruit_id, str) or not fruit_id.strip() or fruit_id in identifiers or
                not isinstance(object_ref, str) or not object_ref.strip() or object_ref in objects):
            raise ValueError('Duplicate or empty fruit identity.')
        identifiers.add(fruit_id)
        objects.add(object_ref)
        center = vector3(fruit['center_local_m'])
        validate_bounds(fruit['bounds_local'])
        if any(abs(a - b) > 1e-6 for a, b in zip(center, bounds_center(fruit['bounds_local']))):
            raise ValueError('Fruit center is not its local bounding-box midpoint.')
        if any(fruit['bounds_local']['min'][i] < data['bounds_local']['min'][i] - 1e-5 or
               fruit['bounds_local']['max'][i] > data['bounds_local']['max'][i] + 1e-5 for i in range(3)):
            raise ValueError('Fruit lies outside overall asset bounds.')
        if data['schema_version'] == '1.1.0' and 'attachment' not in fruit:
            raise ValueError('Schema 1.1 fruit is missing attachment landmarks.')
        if 'attachment' in fruit:
            attachment = fruit['attachment']
            for field in ('stem_base_local_m', 'stem_tip_local_m', 'branch_surface_local_m',
                          'branch_anchor_local_m', 'direction_to_branch_local'):
                vector3(attachment[field])
            if not attachment['profile_id'] or not attachment['connector_object_ref']:
                raise ValueError('Missing attachment identity.')
            index = attachment['connector_spline_index']
            if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index in splines:
                raise ValueError('Invalid or duplicated fruit connector index.')
            splines.add(index)
            direction = attachment['direction_to_branch_local']
            if abs(sum(value * value for value in direction) - 1) > 1e-4:
                raise ValueError('Attachment direction must be a unit vector.')
            difference = [a - b for a, b in zip(attachment['branch_anchor_local_m'], attachment['stem_tip_local_m'])]
            length = math.sqrt(sum(value * value for value in difference))
            if length <= 1e-6 or sum(a * b for a, b in zip(difference, direction)) / length < 0.999:
                raise ValueError('Attachment landmarks and connector direction disagree.')
    if data['schema_version'] in ('2.0.0', ASSET_SCHEMA_VERSION):
        if 'growth_stage' in data['biological_info']:
            raise ValueError('Tree growth stage is outside current core metadata.')
        if data.get('review', {}).get('status') not in ('user_declared_complete', 'automated_test_only'):
            raise ValueError('Missing explicit review provenance.')
        if isinstance(counts.get('visual_object_count'), bool) or not isinstance(counts.get('visual_object_count'), int) or counts['visual_object_count'] < len(data['fruits']):
            raise ValueError('Invalid visual-object count.')
        for fruit in data['fruits']:
            if (fruit.get('maturity_stage') not in MATURITY_STAGES or
                    not isinstance(fruit.get('fruit_variant_id'), str) or not fruit['fruit_variant_id'].strip()):
                raise ValueError('Missing fruit variant or unsupported maturity label.')
    if data['schema_version'] == ASSET_SCHEMA_VERSION:
        if 'collision' in data or 'collision_container' in data['asset_root'] or any('collision_enabled' in fruit for fruit in data['fruits']):
            raise ValueError('Schema 3 is appearance-only; historical collision fields must not be copied.')
        review = data['review']
        if review.get('source_model_sha256') != data['model_sha256'] or not review.get('recorded_at_utc'):
            raise ValueError('Review declaration must identify the current saved model and recording time.')
    return data


def fruit_world_records(asset, instance):
    """Derived query records, not duplicated authoritative environment state."""
    validate_asset(asset)
    matrix = instance['transform_asset_to_world']
    return [{'global_fruit_id': instance['instance_id'] + '/' + fruit['fruit_id'],
             'tree_instance_id': instance['instance_id'], 'fruit_id': fruit['fruit_id'],
             'center_world_m': transform_point(matrix, fruit['center_local_m'])}
            for fruit in asset['fruits']]


def validate_environment(data):
    for field in ('schema_version', 'environment_id', 'environment_version', 'scene_file',
                  'coordinate_system', 'bounds_world', 'asset_catalog', 'instances', 'terrain', 'layout', 'generation'):
        if field not in data:
            raise ValueError('Missing environment field: ' + field)
    if data['schema_version'] != SCHEMA_VERSION:
        raise ValueError('Unsupported environment schema.')
    if not data['environment_id'] or not data['environment_version']:
        raise ValueError('Empty environment identity.')
    if data['scene_file'] is not None:
        relative_file(data['scene_file'])
    system = dict(data['coordinate_system'])
    if not isinstance(system.get('origin'), str) or not system['origin']:
        raise ValueError('Environment origin must be explicitly defined.')
    system['origin'] = 'tree_root_base'
    if system != COORDINATE_SYSTEM:
        raise ValueError('Asset/world coordinate conventions must agree apart from origin.')
    validate_bounds(data['bounds_world'])
    catalog = data['asset_catalog']
    for reference in catalog.values():
        for field in ('asset_id', 'asset_version', 'metadata_file', 'model_sha256'):
            if not reference.get(field):
                raise ValueError('Incomplete asset catalog reference.')
        relative_file(reference['metadata_file'])
        if not re.match(r'^[0-9a-f]{64}$', reference['model_sha256']):
            raise ValueError('Invalid asset catalog checksum.')
    seen = set()
    for instance in data['instances']:
        identity = instance['instance_id']
        if not identity or identity in seen:
            raise ValueError('Duplicate or empty environment instance ID.')
        seen.add(identity)
        if instance['asset_ref'] not in catalog:
            raise ValueError('Unresolved asset reference.')
        validate_transform(instance['transform_asset_to_world'])
    return data
