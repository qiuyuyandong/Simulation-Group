import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('metadata_launcher', ROOT / 'generate_metadata.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class MetadataLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='_metadata_test_', dir=str(ROOT))
        self.directory = Path(self.temporary.name)
        self.stage = self.directory / '.metadata-test'
        self.stage.mkdir()
        (self.directory / 'asset.blend').write_bytes(b'unchanged model fixture')
        self.source_hash = launcher.checksum(self.directory / 'asset.blend')
        for name in ('asset_metadata.json', 'validation_report.json', 'metadata.log'):
            (self.stage / name).write_text('new ' + name, encoding='utf-8')

    def tearDown(self):
        self.temporary.cleanup()

    def test_parser_separates_metadata_from_tree_generation(self):
        args = launcher.parser().parse_args(['--asset-dir', 'generated/apple_tree_001'])
        self.assertFalse(args.verify_only)
        self.assertFalse(hasattr(args, 'seed'))
        self.assertFalse(hasattr(args, 'collision_config'))

    def test_publish_does_not_save_or_back_up_the_model(self):
        before = (self.directory / 'asset.blend').stat().st_mtime_ns
        backup = launcher.publish(self.directory, self.stage, self.source_hash)
        self.assertIsNone(backup)
        self.assertEqual(launcher.checksum(self.directory / 'asset.blend'), self.source_hash)
        self.assertEqual((self.directory / 'asset.blend').stat().st_mtime_ns, before)

    def test_existing_sidecars_are_backed_up(self):
        (self.directory / 'asset_metadata.json').write_text('old metadata', encoding='utf-8')
        backup = launcher.publish(self.directory, self.stage, self.source_hash)
        self.assertEqual((backup / 'asset_metadata.json').read_text(encoding='utf-8'), 'old metadata')
        self.assertFalse((backup / 'asset.blend').exists())

    def test_source_change_aborts_before_publication(self):
        (self.directory / 'asset.blend').write_bytes(b'changed externally')
        with self.assertRaises(RuntimeError):
            launcher.publish(self.directory, self.stage, self.source_hash)
        self.assertFalse((self.directory / 'asset_metadata.json').exists())
        self.assertTrue((self.stage / 'asset_metadata.json').exists())

    def test_publication_failure_restores_old_sidecars(self):
        (self.directory / 'asset_metadata.json').write_text('old metadata', encoding='utf-8')
        real_replace = launcher.os.replace
        def fail_report(source, target):
            if Path(target).name == 'validation_report.json':
                raise OSError('simulated failure')
            return real_replace(source, target)
        with patch.object(launcher.os, 'replace', side_effect=fail_report):
            with self.assertRaises(OSError):
                launcher.publish(self.directory, self.stage, self.source_hash)
        self.assertEqual((self.directory / 'asset_metadata.json').read_text(encoding='utf-8'), 'old metadata')
        self.assertFalse((self.directory / 'validation_report.json').exists())
        self.assertEqual(launcher.checksum(self.directory / 'asset.blend'), self.source_hash)

    def test_run_record_updates_without_new_number(self):
        (self.directory / 'metadata.json').write_text(json.dumps({'asset_number': 17, 'run_status': 'awaiting_manual_review'}), encoding='utf-8')
        launcher.publish(self.directory, self.stage, self.source_hash)
        record = json.loads((self.directory / 'metadata.json').read_text(encoding='utf-8'))
        self.assertEqual(record['asset_number'], 17)
        self.assertEqual(record['asset_stage'], 'metadata_generated')
        self.assertEqual(record['final_model_sha256'], self.source_hash)

    def test_malformed_historic_record_does_not_publish(self):
        (self.directory / 'metadata.json').write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            launcher.publish(self.directory, self.stage, self.source_hash)
        self.assertFalse((self.directory / 'asset_metadata.json').exists())

    def test_blender_command_only_extracts_or_verifies(self):
        with patch.object(launcher, 'windows_path', side_effect=str):
            command = launcher.blender_command(Path('blender.exe'), self.directory / 'asset.blend',
                                               'export_metadata.py', ['--output-dir', str(self.stage)], 3)
        self.assertIn('--disable-autoexec', command)
        self.assertEqual(command[command.index('--threads') + 1], '3')
        self.assertTrue(any(item.endswith('export_metadata.py') for item in command))
        self.assertFalse(any('prepare_asset_file' in item for item in command))

    def test_removed_implementation_is_not_in_active_project(self):
        for relative in ('finalize.py', 'scripts/collision_builder.py', 'scripts/collision_math.py',
                         'configs/collision_static.json', 'examples/collision_query.py',
                         'scripts/finalize_asset_file.py'):
            self.assertFalse((ROOT / relative).exists(), relative)


if __name__ == '__main__':
    unittest.main()
