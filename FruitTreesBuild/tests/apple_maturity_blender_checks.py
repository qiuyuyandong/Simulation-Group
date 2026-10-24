"""Run with Blender on a newly generated mixed-apple automated-test asset."""
from collections import Counter
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from asset_export import collect_metadata, get_container, sha256
from fruit_maturity import APPLE_STAGES, maturity_stages
from fruit_attachment import verify_connections
from verify_asset import verify_loaded_asset

model = Path(bpy.data.filepath)
data = json.loads((model.parent / 'asset_metadata.json').read_text(encoding='utf-8'))
assert data['review']['status'] == 'automated_test_only'
verify_loaded_asset(data, model)
root, group = bpy.data.objects['Tree'], get_container()
parameters = json.loads(root['generation_record_json'])['generation']['parameters']
expected = parameters['maturity_counts']
assert expected and all(expected.values()), 'Use a sample containing all three stages.'
fruits = sorted((obj for obj in group.objects if obj.get('asset_role') == 'fruit'), key=lambda obj: obj.name)
assert Counter(obj['maturity_stage'] for obj in fruits) == expected
assert [obj['maturity_stage'] for obj in fruits] == maturity_stages(expected, len(fruits), 'unknown', parameters['seed'])
assert data['parts_summary']['fruit_count'] == len(fruits)
assert len({obj.data.as_pointer() for obj in fruits}) == 1
materials = {}
for obj in fruits:
    stage = obj['maturity_stage']
    factor, hue = APPLE_STAGES[stage]
    assert all(0.9 * factor - 1e-6 <= value <= 1.1 * factor + 1e-6 for value in obj.scale)
    assert obj['fruit_variant_id'] == 'apple_' + stage + '_v1'
    slot = next(slot for slot in obj.material_slots if slot.link == 'OBJECT')
    material = slot.material
    assert abs(material.node_tree.nodes['Apple_Maturity'].inputs['Hue'].default_value - hue) < 1e-6
    assert 'Normal Map' in material.node_tree.nodes
    assert material.pass_index == 3
    tint = material.node_tree.nodes['Apple_Maturity']
    assert 0 < tint.inputs['Saturation'].default_value < 1
    assert 0 < tint.inputs['Value'].default_value < 1
    if stage == 'turning':
        blush = material.node_tree.nodes['Apple_Blush']
        assert all(socket.is_linked for socket in blush.inputs)
        diffuse = next(node for node in material.node_tree.nodes if node.type == 'BSDF_DIFFUSE')
        assert diffuse.inputs['Color'].links[0].from_node == blush
        mask = blush.inputs[0].links[0].from_node
        variation = mask.inputs['Fac'].links[0].from_node
        assert variation.operation == 'MULTIPLY_ADD'
        assert variation.inputs[2].links[0].from_node.type == 'SEPXYZ'
    materials.setdefault(stage, set()).add(material.as_pointer())
    assert all('Apple_Maturity' not in source.node_tree.nodes for source in obj.data.materials)
assert len({next(iter(value)) for value in materials.values()}) == 3
assert all(len(value) == 1 for value in materials.values())
verify_connections(list(group.objects), root)
# Metadata must read edited objects, not repeat the generation-time targets.
edited_stage = 'unripe' if fruits[0]['maturity_stage'] == 'ripe' else 'ripe'
fruits[0]['maturity_stage'] = edited_stage
fruits[0]['fruit_variant_id'] = 'apple_' + edited_stage + '_v1'
assert collect_metadata(model, data['review'])['fruits'][0]['maturity_stage'] == edited_stage
bpy.data.objects.remove(fruits[-1], do_unlink=True)
assert collect_metadata(model, data['review'])['parts_summary']['fruit_count'] == len(fruits) - 1
assert sha256(model) == data['model_sha256']
print('APPLE_MATURITY_PASS ' + json.dumps(expected, sort_keys=True))
