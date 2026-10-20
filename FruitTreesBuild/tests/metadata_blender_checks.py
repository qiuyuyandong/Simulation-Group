"""Read-only regression checks on a NEW metadata-only test asset."""
import json
from pathlib import Path
import sys
import bpy
from mathutils import Matrix, Euler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from asset_export import get_container, collect_metadata, sha256
from asset_geometry import group_objects, visual_objects
from verify_asset import verify_loaded_asset, _same

model = Path(bpy.data.filepath).resolve()
data = json.loads((model.parent / 'asset_metadata.json').read_text(encoding='utf-8'))
if data.get('schema_version') != '3.0.0' or data['review']['status'] != 'automated_test_only':
    raise RuntimeError('Only run this regression on a new schema-3 automated sample.')
source_hash = sha256(model)
report = verify_loaded_asset(data, model)
group, root = get_container(), bpy.data.objects['Tree']
if len(visual_objects(group)) != len(group_objects(group)):
    raise RuntimeError('New generation unexpectedly contains nonvisual proxies.')
if any(obj.get('collider_id') or obj.get('collision_enabled') is not None for obj in group_objects(group)):
    raise RuntimeError('New generation unexpectedly contains old physics properties.')

original = root.matrix_world.copy()
root.matrix_world = Matrix.Translation((3., -2., .5)) @ Euler((.17, -.13, .61)).to_matrix().to_4x4() @ original
bpy.context.view_layer.update()
moved = collect_metadata(model, data['review'])
_same(data['bounds_local'], moved['bounds_local'], 'rigid placement / bounds')
_same(data['fruits'], moved['fruits'], 'rigid placement / fruit mapping')
root.matrix_world = original
bpy.context.view_layer.update()

fruits = [obj for obj in visual_objects(group) if obj.get('asset_role') == 'fruit']
old_id = fruits[1]['fruit_id']
fruits[1]['fruit_id'] = fruits[0]['fruit_id']
try:
    try:
        collect_metadata(model, data['review'])
    except RuntimeError:
        duplicate_rejected = True
    else:
        raise AssertionError('Duplicate fruit ID was accepted.')
finally:
    fruits[1]['fruit_id'] = old_id

import copy
bad = copy.deepcopy(data)
bad['model_sha256'] = bad['review']['source_model_sha256'] = '0' * 64
try:
    verify_loaded_asset(bad, model)
except RuntimeError:
    stale_rejected = True
else:
    raise AssertionError('Stale model checksum was accepted.')

# Applying the old Skin/Subsurf stack is now allowed: export reads evaluated
# appearance, not an assumed old branch skeleton. This edit is in memory only.
if root.modifiers:
    bpy.context.view_layer.objects.active = root
    root.select_set(True)
    for modifier in list(root.modifiers):
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    applied = collect_metadata(model, data['review'])
    _same(data['bounds_local'], applied['bounds_local'], 'applied appearance modifiers')

if sha256(model) != source_hash:
    raise RuntimeError('Read-only regression changed the saved model.')
report.update({'no_proxies_or_physics_properties': True, 'rigid_placement_preserves_local_records': True,
               'duplicate_id_rejected': duplicate_rejected, 'stale_checksum_rejected': stale_rejected,
               'applied_wood_modifiers_supported': True, 'saved_model_unchanged': True})
print('METADATA_REGRESSION ' + json.dumps(report, sort_keys=True))
