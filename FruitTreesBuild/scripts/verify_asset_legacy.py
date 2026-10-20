"""Read-only validation in a fresh Blender process, against the saved asset."""
import hashlib
import json
import sys
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from asset_export import get_container, geometry_bounds, sha256
from metadata_contract import validate_asset, bounds_center
from fruit_attachment import attachment_metadata, verify_connections

output = Path(bpy.data.filepath).parent
data = validate_asset(json.loads((output / 'asset_metadata.json').read_text(encoding='utf-8')))
if sha256(output / data['model_file']) != data['model_sha256']:
    raise RuntimeError('Saved model checksum mismatch; metadata must be re-exported after edits.')
if Path(bpy.data.filepath).name != data['model_file']:
    raise RuntimeError('Load asset.blend, not scene.blend, for asset validation.')
group = get_container()
if group is None:
    raise RuntimeError('Missing asset container.')
objects = list(group.objects)
if set(bpy.context.scene.objects) != set(objects):
    raise RuntimeError('Active asset scene contains wrong or missing objects.')
root = bpy.data.objects[data['asset_root']['object']]
if root.get('asset_id') != data['asset_id'] or root.get('asset_version') != data['asset_version']:
    raise RuntimeError('Model/metadata asset identity mismatch.')
if {obj.name for obj in bpy.data.objects} != {obj.name for obj in objects}:
    raise RuntimeError('Clean asset contains non-asset objects or unused source prototypes.')
if len(bpy.data.scenes) != 1 or bpy.context.scene.camera or bpy.context.scene.world:
    raise RuntimeError('Asset must contain only its standalone scene, without camera/world.')
if any(obj.type not in ('MESH', 'CURVE') for obj in objects):
    raise RuntimeError('Unexpected object type in asset.')
if any(obj != root and obj.parent != root for obj in objects):
    raise RuntimeError('Asset hierarchy is not intact.')
if any(obj.hide_render for obj in objects):
    raise RuntimeError('Hidden asset parts.')
if any(image.source == 'FILE' and not image.packed_file for image in bpy.data.images):
    raise RuntimeError('External texture dependency.')
if any(node.bl_idname == 'NodeUndefined' for material in bpy.data.materials
       if material.node_tree for node in material.node_tree.nodes):
    raise RuntimeError('Unresolved material nodes.')
bounds, records = geometry_bounds(objects, root)


def assert_bounds(actual, recorded):
    for edge in ('min', 'max'):
        if any(abs(a - b) > 1e-5 for a, b in zip(actual[edge], recorded[edge])):
            raise RuntimeError('Evaluated bounds disagree with metadata.')


assert_bounds(bounds, data['bounds_local'])
fruits = {obj['fruit_id']: obj for obj in objects if obj.get('asset_role') == 'fruit'}
leaves = [obj for obj in objects if obj.get('asset_role') == 'leaf']
if len(objects) != data['parts_summary']['object_count'] or len(leaves) != data['parts_summary']['leaf_count']:
    raise RuntimeError('Part counts mismatch.')
if set(fruits) != {fruit['fruit_id'] for fruit in data['fruits']}:
    raise RuntimeError('Fruit identity mismatch.')
for fruit in data['fruits']:
    obj = fruits[fruit['fruit_id']]
    if obj.name != fruit['object_ref']:
        raise RuntimeError('Fruit object mapping mismatch.')
    assert_bounds(records[obj.name], fruit['bounds_local'])
    if any(abs(a - b) > 1e-5 for a, b in zip(bounds_center(records[obj.name]), fruit['center_local_m'])):
        raise RuntimeError('Fruit center mismatch.')
    if 'attachment' in fruit:
        actual = attachment_metadata(obj, root)
        recorded = fruit['attachment']
        for field in ('profile_id', 'connector_object_ref', 'connector_spline_index'):
            if actual[field] != recorded[field]:
                raise RuntimeError('Fruit attachment identity mismatch.')
        for field in ('stem_base_local_m', 'stem_tip_local_m', 'branch_surface_local_m',
                      'branch_anchor_local_m', 'direction_to_branch_local'):
            if any(abs(a - b) > 1e-5 for a, b in zip(actual[field], recorded[field])):
                raise RuntimeError('Fruit attachment coordinates mismatch.')
if any(not obj.data.uv_layers for obj in leaves + list(fruits.values())):
    raise RuntimeError('Missing leaf/fruit UVs.')
wood_hash = hashlib.sha256(json.dumps([list(vertex.co) for vertex in root.data.vertices],
                                    separators=(',', ':')).encode('utf-8')).hexdigest()
attachment_checks = verify_connections(objects, root) if data['schema_version'] == '1.1.0' else None
report = {'result': 'passed', 'blender': bpy.app.version_string, 'asset_id': data['asset_id'],
          'objects': len(objects), 'leaf_count': len(leaves), 'fruit_count': len(fruits),
          'packed_images': sum(bool(image.packed_file) for image in bpy.data.images),
          'bounds_local': bounds, 'tree_centerline_sha256': wood_hash,
          'no_cameras_ground_or_source_objects': True,
          'fruit_coordinates_checked_against_saved_geometry': True}
report['fruit_attachment_checks'] = attachment_checks
print('ASSET_CHECK ' + json.dumps(report, sort_keys=True))
