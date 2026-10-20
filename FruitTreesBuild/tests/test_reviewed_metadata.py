from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_asset_metadata import sample_asset
from metadata_contract import validate_asset, validate_unit_frame


def reviewed_fixture():
    data = sample_asset()
    data['schema_version'] = '3.0.0'
    data['parts_summary']['visual_object_count'] = 2
    data['review'] = {'status': 'user_declared_complete', 'source_model_sha256': data['model_sha256'],
                      'recorded_at_utc': '2026-10-14T00:00:00+00:00'}
    data['fruits'][0].update({'maturity_stage': 'unknown', 'fruit_variant_id': 'apple_base_v1'})
    return data


class ReviewedMetadataTests(unittest.TestCase):
    def test_visual_core_needs_no_attachment_tree_stage_or_collision(self):
        validate_asset(reviewed_fixture())

    def test_maturity_is_not_implicitly_ripe(self):
        for value in ('', 'mature_tree', None):
            data = reviewed_fixture()
            data['fruits'][0]['maturity_stage'] = value
            with self.assertRaises(ValueError):
                validate_asset(data)

    def test_missing_variant_rejected(self):
        for value in ('', ' ', None):
            data = reviewed_fixture()
            data['fruits'][0]['fruit_variant_id'] = value
            with self.assertRaises(ValueError):
                validate_asset(data)

    def test_tree_stage_excluded(self):
        data = reviewed_fixture()
        data['biological_info']['growth_stage'] = 'adult'
        with self.assertRaises(ValueError):
            validate_asset(data)

    def test_historical_collision_fields_not_reintroduced(self):
        for where in ('module', 'root', 'fruit'):
            data = reviewed_fixture()
            if where == 'module':
                data['collision'] = {'status': 'not_provided'}
            elif where == 'root':
                data['asset_root']['collision_container'] = 'Collision_Proxies'
            else:
                data['fruits'][0]['collision_enabled'] = True
            with self.assertRaises(ValueError):
                validate_asset(data)

    def test_review_must_refer_to_current_file(self):
        data = reviewed_fixture()
        data['review']['source_model_sha256'] = '1' * 64
        with self.assertRaises(ValueError):
            validate_asset(data)

    def test_empty_review_timestamp_rejected(self):
        data = reviewed_fixture()
        data['review']['recorded_at_utc'] = ''
        with self.assertRaises(ValueError):
            validate_asset(data)

    def test_root_frame_is_unit_and_rigid(self):
        validate_unit_frame([[0, -1, 0, 2], [1, 0, 0, 3], [0, 0, 1, 4], [0, 0, 0, 1]])
        with self.assertRaises(ValueError):
            validate_unit_frame([[2, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])

    def test_historic_schema2_can_read_visual_core_without_physics_code(self):
        data = reviewed_fixture()
        data['schema_version'] = '2.0.0'
        data['collision'] = {'status': 'historical_unchecked'}
        validate_asset(data)


if __name__ == '__main__':
    unittest.main()
