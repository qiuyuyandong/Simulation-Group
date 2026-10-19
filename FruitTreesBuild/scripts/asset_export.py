"""Candidate export and read-only metadata extraction after manual editing."""
import hashlib
import json
from pathlib import Path
import bpy
from blender_compat import LEGACY, evaluated_coordinates, transform, update_scene
from metadata_contract import (ASSET_SCHEMA_VERSION, COORDINATE_SYSTEM, MATURITY_STAGES,
                               bounds_from_points, bounds_center, validate_asset)
from asset_geometry import VISUAL_ROLES, group_objects, check_visual_structure, check_saved_scene

ROOT = Path(__file__).resolve().parent.parent


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def get_container():
    containers = bpy.data.groups if LEGACY else bpy.data.collections
    return containers.get('OrchardTree_Asset')


def geometry_bounds(objects, root):
    update_scene()
    inverse = root.matrix_world.inverted()
    cache, records = {}, {}
    for obj in objects:
        key = obj.data.as_pointer() if not obj.modifiers else ('modified', obj.as_pointer())
        if key not in cache:
            cache[key] = evaluated_coordinates(obj)
        matrix = transform(inverse, obj.matrix_world)
        points = [list(transform(matrix, point)) for point in cache[key]]
        records[obj.name] = bounds_from_points(points)
    combined = bounds_from_points([record[edge] for record in records.values() for edge in ('min', 'max')])
    return combined, records


def read_generation_record(root, directory):
    if root.get('generation_record_json'):
        return json.loads(root['generation_record_json'])
    # Migration uses ONLY historic provenance, never old geometry or checks.
    old_path = Path(directory) / 'asset_metadata.json'
    if old_path.is_file():
        old = json.loads(old_path.read_text(encoding='utf-8-sig'))
        return {'generation': old['generation'], 'provenance': old['provenance'],
                'category': old['category'], 'biological_info': old['biological_info']}
    raise RuntimeError('Missing embedded generation record. Use an exported candidate or migrate alongside its old metadata.')


def export_asset(args, output, source_name, structure):
    """Write an editable candidate, deliberately WITHOUT asset_metadata.json."""
    model_path = output / 'asset.blend'
    if model_path.exists() or (output / 'asset_metadata.json').exists():
        raise RuntimeError('Refusing to overwrite an existing asset.')
    group, root = get_container(), bpy.data.objects['Tree']
    objects = sorted(group.objects, key=lambda obj: obj.name)
    if any(obj.type not in ('MESH', 'CURVE') or obj.get('asset_role') not in VISUAL_ROLES for obj in objects):
        raise RuntimeError('Unexpected candidate objects.')
    parameters = {name: getattr(args, name) for name in
                  ('generator', 'profile', 'fruit', 'seed', 'tree_height', 'trunk_height',
                   'trunk_diameter', 'crown_width', 'leaf_fruit_clearance',
                   'branch_uplift', 'branch_angle_min', 'height_taper', 'leaf_spacing',
                   'leaf_count', 'fruit_count', 'leaf_length', 'fruit_diameter',
                   'maturity_stage', 'fruit_variant_id')}
    sources = ['scripts/orchard_shape.py', 'scripts/apple_branching.py', 'scripts/apple_wood.py',
               'scripts/apple_crown.py', 'scripts/asset_export.py', 'scripts/fruit_attachment.py',
               'assets/fruit_attachment_profiles.json', 'assets/source_prototypes.blend']
    if args.generator == 'space':
        sources += ['vendor/spacetree/src/add_mesh_space_tree/scanew.py', 'scripts/modern_scene.py']
    else:
        sources += ['vendor/sapling/utils.py', 'vendor/iamps/sapling_tree_scene_gen.py',
                    'scripts/sapling_scene.py', 'scripts/citrus_geometry.py',
                    'leaf_texture/TexturesCom_Leaves0089_1_masked_S.png']
    source_files = [{'file': name, 'sha256': sha256(ROOT / name)} for name in sources]
    fingerprint = hashlib.sha256(json.dumps({'parameters': parameters, 'sources': source_files,
                                             'blender': bpy.app.version_string}, sort_keys=True).encode()).hexdigest()
    asset_id = '{}_tree_s{}_{}'.format(args.fruit, args.seed, fingerprint[:12])
    root['asset_id'] = group['asset_id'] = asset_id
    root['asset_version'] = group['asset_version'] = '1.0.0'
    for obj in objects:
        if obj.get('asset_role') == 'fruit':
            obj['fruit_id'] = obj['instance_id']
            obj['maturity_stage'] = args.maturity_stage
            obj['fruit_variant_id'] = args.fruit_variant_id
    record = {
        'category': args.fruit + '_tree',
        'biological_info': {'crop_label': args.fruit, 'species': None, 'cultivar': None,
                            'validation_status': 'uncalibrated'},
        'generation': {'backend': 'modern', 'blender_version': bpy.app.version_string,
                       'source_script': source_name, 'parameters': parameters,
                       'source_files': source_files, 'fingerprint_sha256': fingerprint,
                       'structure_design_and_checks': structure,
                       'record_basis': 'generation-time targets and checks, not the edited model state'},
        'provenance': {
            'framework_repository': 'https://github.com/tduboudi/IAMPS2019-Procedural-Fruit-Tree-Rendering-Framework',
            'framework_code_license': 'MIT',
            'branch_algorithm_repository': ('https://github.com/blender/blender-addons/tree/main/add_curve_sapling'
                                            if args.generator == 'sapling' else 'https://github.com/varkenvarken/spacetree'),
            'branch_addon_license': 'GPL-2.0-or-later (source header)',
            'third_party_asset_license_status': 'not_reviewed',
            'credits': {'leaves': ('Original Sapling example: leaf_texture/TexturesCom_Leaves0089_1_masked_S.png'
                                   if args.generator == 'sapling' else
                                   ['http://pngimg.com/download/3638', 'http://pngimg.com/download/3668']),
                        'bark': 'https://www.textures.com/download/3dscans0062/127610',
                        'fruit': ('https://free3d.com/3d-model/apples-42451.html' if args.fruit == 'apple' else
                                  'https://www.turbosquid.com/3d-models/free-3ds-model-orange-resolution-photorealistic/756550')},
            'credits_basis': 'Original repository records; code license does not determine third-party asset licenses.'}}
    root['generation_record_json'] = json.dumps(record, ensure_ascii=False, sort_keys=True)
    asset_scene = bpy.data.scenes.new('Asset')
    asset_scene.unit_settings.system = 'METRIC'
    asset_scene.unit_settings.scale_length = 1.
    asset_scene.render.engine = 'CYCLES'
    asset_scene.collection.children.link(group)
    asset_scene.view_layers[0].update()
    group.asset_mark()
    group.asset_data.description = 'Editable candidate. Review and save, then run generate_metadata.py.'
    bpy.data.libraries.write(str(model_path), {asset_scene, group}, path_remap='RELATIVE')
    bpy.data.scenes.remove(asset_scene)
    print('CANDIDATE_EXPORTED ' + str(model_path))
    return record


def collect_metadata(model_path, review):
    """Extract from the FINAL saved model; no generation-count assumptions."""
    group = get_container()
    if group is None:
        raise RuntimeError('Missing asset collection.')
    root = bpy.data.objects.get('Tree')
    if root is None:
        raise RuntimeError('Missing tree root.')
    objects = check_saved_scene(group, root)
    bounds, object_bounds = geometry_bounds(objects, root)
    record = read_generation_record(root, Path(model_path).parent)
    fruits = [{'fruit_id': obj['fruit_id'], 'object_ref': obj.name,
               'center_local_m': bounds_center(object_bounds[obj.name]),
               'bounds_local': object_bounds[obj.name],
               'fruit_variant_id': obj.get('fruit_variant_id', record['category'].replace('_tree', '') + '_unspecified'),
               'maturity_stage': obj.get('maturity_stage', 'unknown')}
              for obj in objects if obj.get('asset_role') == 'fruit']
    biology = dict(record.get('biological_info', {}))
    biology.pop('growth_stage', None)
    generation = record['generation']
    data = {'schema_version': ASSET_SCHEMA_VERSION, 'asset_id': root['asset_id'],
            'asset_version': root['asset_version'], 'model_file': 'asset.blend', 'model_sha256': sha256(model_path),
            'asset_root': {'object': root.name, 'container': group.name, 'container_type': 'COLLECTION',
                           'scene': bpy.context.scene.name},
            'category': record['category'], 'biological_info': biology,
            'coordinate_system': dict(COORDINATE_SYSTEM), 'bounds_local': bounds,
            'parts_summary': {'leaf_count': sum(obj.get('asset_role') == 'leaf' for obj in objects),
                              'fruit_count': len(fruits), 'visual_object_count': len(objects),
                              'roles': list(VISUAL_ROLES), 'role_property': 'asset_role',
                              'per_leaf_records_exported': False},
            'fruits': fruits,
            'generation': {'generator': generation['parameters']['generator'],
                           'seed': generation['parameters']['seed'],
                           'blender_version': generation['blender_version'],
                           'fingerprint_sha256': generation['fingerprint_sha256'],
                           'full_record': 'Embedded Tree.generation_record_json and optional metadata.json; not a loading dependency.'},
            'provenance': record['provenance'],
            'review': review,
            'quality': {'status': 'static_visual_asset',
                        'checks': {'visual_counts_and_coordinates_read_from_saved_geometry': True,
                                   'fruit_identity_mapping_verified': True},
                        'ignored_historical_nonvisual_object_count': len(group_objects(group)) - len(objects),
                        'limitations': ['Species/cultivar and maturity labels are not empirically calibrated.',
                                        'Human review is a declaration, not an automated proof of absence of mesh intersections.',
                                        'Fruit centers are bounding-box midpoints, not grasp points.',
                                        'Bounds are axis-aligned envelopes, not detailed surface contours.',
                                        'Detailed connection diagnostics and full mesh-intersection checks are not performed.',
                                        'No collision geometry is generated or validated by this workflow.',
                                        'Historical nonvisual objects, if present, are ignored and left unchanged.']}}
    validate_asset(data)
    return data
