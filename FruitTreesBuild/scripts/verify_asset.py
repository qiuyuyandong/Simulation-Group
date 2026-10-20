"""Read-only saved appearance/metadata verification; no physics validation."""
import argparse
import json
import sys
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from asset_export import get_container, geometry_bounds, sha256, collect_metadata
from asset_geometry import group_objects, check_saved_scene
from metadata_contract import ASSET_SCHEMA_VERSION, validate_asset, bounds_center


def _same(actual, recorded, path='metadata'):
    if isinstance(actual, dict):
        if not isinstance(recorded, dict) or set(actual) != set(recorded):
            raise RuntimeError('Field mismatch: ' + path)
        for key in actual:
            _same(actual[key], recorded[key], path + '.' + key)
    elif isinstance(actual, list):
        if not isinstance(recorded, list) or len(actual) != len(recorded):
            raise RuntimeError('Length mismatch: ' + path)
        for i, (a, b) in enumerate(zip(actual, recorded)):
            _same(a, b, path + '[' + str(i) + ']')
    elif isinstance(actual, (int, float)) and not isinstance(actual, bool):
        if isinstance(recorded, bool) or not isinstance(recorded, (int, float)) or abs(actual - recorded) > 1e-5:
            raise RuntimeError('Numeric mismatch: ' + path)
    elif actual != recorded:
        raise RuntimeError('Value mismatch: ' + path)


def verify_loaded_asset(data, model_path):
    validate_asset(data)
    model_path = Path(model_path).resolve()
    if model_path.name != data['model_file'] or sha256(model_path) != data['model_sha256']:
        raise RuntimeError('Model checksum/name changed. Save asset.blend and run generate_metadata.py again.')
    group = get_container()
    if group is None:
        raise RuntimeError('Missing asset collection.')
    root = bpy.data.objects[data['asset_root']['object']]
    objects = check_saved_scene(group, root)
    if root['asset_id'] != data['asset_id'] or root['asset_version'] != data['asset_version']:
        raise RuntimeError('Model/metadata asset identity mismatch.')
    if group['asset_id'] != data['asset_id'] or group['asset_version'] != data['asset_version']:
        raise RuntimeError('Collection/metadata asset identity mismatch.')
    if data['schema_version'] == ASSET_SCHEMA_VERSION:
        _same(collect_metadata(model_path, data['review']), data)
    else:
        # Historical schema 2: only appearance is checked. Do not certify its
        # old physics extension after that implementation has been removed.
        bounds, records = geometry_bounds(objects, root)
        _same(bounds, data['bounds_local'], 'bounds_local')
        fruits = {obj['fruit_id']: obj for obj in objects if obj.get('asset_role') == 'fruit'}
        if set(fruits) != {fruit['fruit_id'] for fruit in data['fruits']}:
            raise RuntimeError('Fruit identities changed.')
        if len(objects) != data['parts_summary']['visual_object_count'] or sum(obj.get('asset_role') == 'leaf' for obj in objects) != data['parts_summary']['leaf_count']:
            raise RuntimeError('Appearance counts changed.')
        for fruit in data['fruits']:
            obj = fruits[fruit['fruit_id']]
            if obj.name != fruit['object_ref'] or obj.get('maturity_stage') != fruit['maturity_stage'] or obj.get('fruit_variant_id') != fruit['fruit_variant_id']:
                raise RuntimeError('Fruit object/variant/maturity mapping changed.')
            _same(records[obj.name], fruit['bounds_local'], 'fruit bounds ' + obj.name)
            _same(bounds_center(records[obj.name]), fruit['center_local_m'], 'fruit center ' + obj.name)
    return {'result': 'passed', 'scope': 'saved_appearance_and_core_metadata_only',
            'asset_id': data['asset_id'], 'model_sha256': data['model_sha256'],
            'visual_object_count': len(objects), 'fruit_count': data['parts_summary']['fruit_count'],
            'leaf_count': data['parts_summary']['leaf_count'],
            'ignored_historical_nonvisual_objects': len(group_objects(group)) - len(objects),
            'saved_geometry_and_fruit_mapping_verified': True,
            'full_mesh_intersections': 'not_checked', 'physics_validation': 'not_performed',
            'review_status': data['review']['status']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata')
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    args = parser.parse_args(argv)
    model = Path(bpy.data.filepath).resolve()
    metadata = Path(args.metadata).resolve() if args.metadata else model.parent / 'asset_metadata.json'
    data = json.loads(metadata.read_text(encoding='utf-8-sig'))
    if data.get('schema_version') in ('1.0.0', '1.1.0'):
        if metadata != model.parent / 'asset_metadata.json':
            raise RuntimeError('Legacy verification expects metadata beside its model.')
        legacy = Path(__file__).with_name('verify_asset_legacy.py')
        exec(compile(legacy.read_text(encoding='utf-8'), str(legacy), 'exec'), {'__file__': str(legacy)})
        print('VALIDATION_SCOPE legacy appearance; no physics validation')
        return
    report = verify_loaded_asset(data, model)
    print('ASSET_CHECK ' + json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
