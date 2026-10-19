"""No Blender or extra packages needed."""
import copy
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from metadata_contract import (COORDINATE_SYSTEM, bounds_from_points, transform_point,
                               transform_bounds, validate_transform, validate_asset,
                               validate_environment)
from metadata_contract import fruit_world_records


def sample_asset():
    return {'schema_version': '1.0.0', 'asset_id': 'test_tree', 'asset_version': '1.0.0',
            'model_file': 'asset.blend', 'model_sha256': '0' * 64,
            'asset_root': {'object': 'Tree', 'container': 'OrchardTree_Asset'},
            'category': 'apple_tree', 'biological_info': {},
            'coordinate_system': dict(COORDINATE_SYSTEM),
            'bounds_local': {'min': [-1, -1, 0], 'max': [1, 1, 4]},
            'parts_summary': {'fruit_count': 1, 'leaf_count': 0},
            'fruits': [{'fruit_id': 'Fruit_0001', 'object_ref': 'Fruit_0001',
                        'center_local_m': [0.2, 0, 2],
                        'bounds_local': {'min': [0.1, -0.1, 1.9], 'max': [0.3, 0.1, 2.1]}}],
            'generation': {}, 'provenance': {}, 'quality': {}}


def sample_environment():
    coordinates = dict(COORDINATE_SYSTEM)
    coordinates['origin'] = 'environment_origin'
    return {'schema_version': '1.0.0', 'environment_id': 'test_world', 'environment_version': '1.0.0',
            'scene_file': None, 'coordinate_system': coordinates,
            'bounds_world': {'min': [-20, -20, 0], 'max': [20, 20, 10]},
            'asset_catalog': {'tree_asset': {'asset_id': 'test_tree', 'asset_version': '1.0.0',
                                            'metadata_file': '../tree/asset_metadata.json', 'model_sha256': '0' * 64}},
            'instances': [{'instance_id': 'tree_001', 'asset_ref': 'tree_asset',
                           'transform_asset_to_world': [[0, -1, 0, 10], [1, 0, 0, 5],
                                                        [0, 0, 1, 0], [0, 0, 0, 1]]}],
            'terrain': None, 'layout': {}, 'generation': {}}


class MetadataTests(unittest.TestCase):
    def attachment_asset(self):
        data = sample_asset()
        data['schema_version'] = '1.1.0'
        data['asset_version'] = '1.1.0'
        data['fruits'][0]['attachment'] = {
            'profile_id': 'fixture', 'stem_base_local_m': [0.2, 0, 2.09],
            'stem_tip_local_m': [0.2, 0, 2.1],
            'branch_surface_local_m': [0.2, 0, 2.1035],
            'branch_anchor_local_m': [0.2, 0, 2.104],
            'direction_to_branch_local': [0, 0, 1],
            'connector_object_ref': 'Fruit_Stems', 'connector_spline_index': 0}
        return data

    def test_attachment_schema_and_legacy_compatibility(self):
        validate_asset(self.attachment_asset())
        validate_asset(sample_asset())

    def test_new_schema_requires_attachment(self):
        data = sample_asset()
        data['schema_version'] = '1.1.0'
        with self.assertRaises(ValueError):
            validate_asset(data)

    def test_invalid_attachment_direction(self):
        for direction in ([0, 0, 2], [0, 0, -1], [0, 0, float('nan')]):
            data = self.attachment_asset()
            data['fruits'][0]['attachment']['direction_to_branch_local'] = direction
            with self.assertRaises(ValueError):
                validate_asset(data)

    def test_duplicate_attachment_spline(self):
        data = self.attachment_asset()
        fruit = copy.deepcopy(data['fruits'][0])
        fruit['fruit_id'] = 'Fruit_0002'
        fruit['object_ref'] = 'Fruit_0002'
        data['fruits'].append(fruit)
        data['parts_summary']['fruit_count'] = 2
        with self.assertRaises(ValueError):
            validate_asset(data)

    def test_disconnected_attachment_metadata(self):
        data = self.attachment_asset()
        data['fruits'][0]['attachment']['branch_anchor_local_m'] = [0.2, 0, 2.1]
        with self.assertRaises(ValueError):
            validate_asset(data)

    def test_valid_asset(self):
        validate_asset(sample_asset())

    def test_duplicate_fruit_ids(self):
        data = sample_asset()
        data['fruits'].append(copy.deepcopy(data['fruits'][0]))
        data['parts_summary']['fruit_count'] = 2
        with self.assertRaises(ValueError):
            validate_asset(data)

    def test_bad_center_and_count(self):
        for field in ('center', 'count'):
            data = sample_asset()
            if field == 'center':
                data['fruits'][0]['center_local_m'][0] = 0
            else:
                data['parts_summary']['fruit_count'] = 2
            with self.assertRaises(ValueError):
                validate_asset(data)

    def test_invalid_numeric_and_absolute_path(self):
        for value in (float('nan'), float('inf'), True):
            data = sample_asset()
            data['fruits'][0]['center_local_m'][0] = value
            with self.assertRaises(ValueError):
                validate_asset(data)
        for path in ('D:/asset.blend', '/tmp/asset.blend', 'folder\\asset.blend'):
            data = sample_asset()
            data['model_file'] = path
            with self.assertRaises(ValueError):
                validate_asset(data)

    def test_empty_fruit_list_allowed(self):
        data = sample_asset()
        data['fruits'] = []
        data['parts_summary']['fruit_count'] = 0
        validate_asset(data)

    def test_fruit_outside_asset(self):
        data = sample_asset()
        data['bounds_local']['max'][2] = 1
        with self.assertRaises(ValueError):
            validate_asset(data)

    def test_rotation_translation_and_scale(self):
        matrix = sample_environment()['instances'][0]['transform_asset_to_world']
        self.assertEqual(transform_point(matrix, [2, 3, 4]), [7, 7, 4])
        bounds = transform_bounds(matrix, {'min': [0, 0, 0], 'max': [2, 3, 4]})
        self.assertEqual(bounds, {'min': [7, 5, 0], 'max': [10, 7, 4]})
        scale = [[2, 0, 0, 1], [0, 3, 0, 2], [0, 0, 4, 3], [0, 0, 0, 1]]
        self.assertEqual(transform_point(scale, [1, 1, 1]), [3, 5, 7])

    def test_invalid_transform(self):
        for factor in (0, -1):
            matrix = [[factor, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
            with self.assertRaises(ValueError):
                validate_transform(matrix)

    def test_fruit_world_identity(self):
        asset = sample_asset()
        instance = sample_environment()['instances'][0]
        world = fruit_world_records(asset, instance)[0]
        self.assertEqual(world['global_fruit_id'], 'tree_001/Fruit_0001')
        self.assertEqual(world['center_world_m'], [10, 5.2, 2])

    def test_environment_references_and_unique_ids(self):
        validate_environment(sample_environment())
        for field in ('reference', 'duplicate'):
            data = sample_environment()
            if field == 'reference':
                data['instances'][0]['asset_ref'] = 'missing'
            else:
                data['instances'].append(copy.deepcopy(data['instances'][0]))
            with self.assertRaises(ValueError):
                validate_environment(data)

    def test_empty_geometry_rejected(self):
        with self.assertRaises(ValueError):
            bounds_from_points([])

    def test_real_generated_metadata_when_available(self):
        for path in (ROOT / 'generated').glob('*/asset_metadata.json'):
            validate_asset(json.loads(path.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
