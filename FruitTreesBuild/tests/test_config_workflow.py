"""Configuration-driven public scripts; no GUI or tree generation required."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import tree_launcher
from scripts.launcher_config import load_build_config
import generate_metadata
import generate_apple_tree
import generate_orange_tree


class ConfigWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='_config_test_', dir=str(ROOT))
        self.directory = Path(self.temporary.name)
        self.config = self.directory / 'settings.json'

    def tearDown(self):
        self.temporary.cleanup()

    def write_config(self, data):
        self.config.write_text(json.dumps(data), encoding='utf-8')
        return str(self.config)

    def metadata_options(self, data, extra=()):
        argv = ['--config', self.write_config(data)] + list(extra)
        return generate_metadata.resolve_options(generate_metadata.parser().parse_args(argv))

    def tree_args(self, data):
        return tree_launcher.parser().parse_args(['--config', self.write_config(data)])

    def test_apple_entry_no_arguments_selects_apple_config(self):
        with patch.object(tree_launcher, 'execute', return_value=0) as execute, patch.object(tree_launcher, 'powershell_path', return_value=Path('pwsh.exe')):
            self.assertEqual(generate_apple_tree.main([]), 0)
        command = execute.call_args.args[0]
        self.assertEqual(command[command.index('-Fruit') + 1], 'apple')
        self.assertEqual(command[command.index('-Config') + 1], tree_launcher.windows_path(ROOT / 'configs/apple_tree.json'))

    def test_orange_entry_no_arguments_selects_orange_config(self):
        with patch.object(tree_launcher, 'execute', return_value=0) as execute, patch.object(tree_launcher, 'powershell_path', return_value=Path('pwsh.exe')):
            self.assertEqual(generate_orange_tree.main([]), 0)
        command = execute.call_args.args[0]
        self.assertEqual(command[command.index('-Fruit') + 1], 'orange')
        self.assertEqual(command[command.index('-Config') + 1], tree_launcher.windows_path(ROOT / 'configs/orange_tree.json'))

    def test_fixed_entry_rejects_other_fruit_before_execution(self):
        for expected, actual in (('apple', 'orange'), ('orange', 'apple')):
            args = self.tree_args({'fruit': actual})
            with patch.object(tree_launcher, 'powershell_path', return_value=Path('pwsh.exe')):
                with self.assertRaises(ValueError):
                    tree_launcher.build_command(args, expected_fruit=expected)

    def test_metadata_default_parser_needs_no_arguments(self):
        args = generate_metadata.parser().parse_args([])
        self.assertEqual(Path(args.config), ROOT / 'configs/export_metadata.json')

    def test_metadata_entry_no_arguments_reads_edited_configuration(self):
        self.write_config({'assetDir': 'generated/apple_tree_007', 'reviewMode': 'automated_test', 'threads': 2})
        with patch.object(generate_metadata, 'DEFAULT_CONFIG', self.config), patch.object(generate_metadata, 'generate') as generate:
            self.assertEqual(generate_metadata.main([]), 0)
        options = generate.call_args.args[0]
        self.assertEqual(options.asset_dir, 'generated/apple_tree_007')
        self.assertEqual(options.threads, 2)
        self.assertEqual(options.review_mode, 'automated_test')

    def test_metadata_config_supplies_all_runtime_options(self):
        args = self.metadata_options({'assetDir': 'generated/apple_tree_007', 'threads': 3,
                                     'reviewer': 'reviewer', 'reviewNote': 'saved edit', 'reviewMode': 'automated_test',
                                     'checkAttachments': True, 'verifyOnly': True, 'dryRun': True})
        self.assertEqual(args.asset_dir, 'generated/apple_tree_007')
        self.assertEqual(args.threads, 3)
        self.assertEqual(args.review_mode, 'automated_test')
        self.assertTrue(args.check_attachments and args.verify_only and args.dry_run)

    def test_metadata_explicit_false_is_not_lost(self):
        args = self.metadata_options({'assetDir': 'generated/apple_tree_007', 'checkAttachments': False, 'verifyOnly': False})
        self.assertFalse(args.check_attachments)
        self.assertFalse(args.verify_only)

    def test_metadata_advanced_overrides_remain_compatible(self):
        args = self.metadata_options({'assetDir': 'generated/apple_tree_007', 'verifyOnly': True},
                                     ['--asset-dir', 'generated/orange_tree_006', '--no-verify-only', '--threads', '2'])
        self.assertEqual(args.asset_dir, 'generated/orange_tree_006')
        self.assertFalse(args.verify_only)
        self.assertEqual(args.threads, 2)

    def test_metadata_empty_target_does_not_guess_latest(self):
        with self.assertRaisesRegex(ValueError, 'Set assetDir'):
            self.metadata_options({'assetDir': ''})

    def test_metadata_invalid_config_types_rejected(self):
        for bad in ({'verifyOnly': 'false'}, {'threads': True}, {'threads': 0}, {'reviewMode': 'ripe'}, {'unknownField': 3}):
            with self.assertRaises(ValueError):
                self.metadata_options({'assetDir': 'generated/apple_tree_007', **bad})

    def test_build_invalid_config_types_and_ranges_rejected(self):
        for data in ({'seed': True}, {'leafCount': -1}, {'noGround': 'false'}, {'fruit': 'pear'}, {'frames': 1.5}, {'leafCout': 12}):
            self.write_config(data)
            with self.assertRaises(ValueError):
                load_build_config(self.config)

    def test_duplicate_and_nonfinite_json_fields_rejected(self):
        for text in ('{"seed":1,"seed":2}', '{"treeHeight":NaN}', '[]'):
            self.config.write_text(text, encoding='utf-8')
            with self.assertRaises(ValueError):
                load_build_config(self.config)

    def test_citrus_width_and_clearance_are_explicit_dimensions(self):
        self.write_config({'crownWidth': 3.2, 'leafFruitClearance': .006})
        self.assertEqual(load_build_config(self.config), {'crownWidth': 3.2, 'leafFruitClearance': .006})
        self.write_config({'leafFruitClearance': 0})
        self.assertEqual(load_build_config(self.config)['leafFruitClearance'], 0)

    def test_citrus_invalid_dimensions_rejected(self):
        for data in ({'crownWidth': 0}, {'crownWidth': True}, {'leafFruitClearance': -.001},
                     {'leafFruitClearance': .1}, {'leafFruitClearance': '0.006'}):
            self.write_config(data)
            with self.assertRaises(ValueError):
                load_build_config(self.config)

    def test_citrus_configuration_does_not_change_apple_configuration(self):
        apple = load_build_config(ROOT / 'configs/apple_tree.json')
        orange = load_build_config(ROOT / 'configs/orange_tree.json')
        self.assertNotIn('crownWidth', apple)
        self.assertEqual(apple['leafCount'], 3000)
        self.assertEqual(orange['generator'], 'sapling')
        self.assertIn('crownWidth', orange)

    def test_all_three_public_run_configs_have_empty_parameters(self):
        for filename, script in (('Generate_Apple_Tree.run.xml', 'generate_apple_tree.py'),
                                  ('Generate_Orange_Tree.run.xml', 'generate_orange_tree.py'),
                                  ('Generate_Asset_Metadata.run.xml', 'generate_metadata.py')):
            tree = ET.parse(ROOT / '.run' / filename)
            options = {entry.attrib['name']: entry.attrib.get('value', '') for entry in tree.findall('.//option')}
            self.assertEqual(options['PARAMETERS'], '')
            self.assertEqual(options['SCRIPT_NAME'], '$PROJECT_DIR$/' + script)

    def test_project_has_exactly_three_public_python_scripts(self):
        self.assertEqual({path.name for path in ROOT.glob('*.py')},
                         {'generate_apple_tree.py', 'generate_orange_tree.py', 'generate_metadata.py'})

    def test_tree_launcher_uses_internal_build_script(self):
        with patch.object(tree_launcher, 'powershell_path', return_value=Path('pwsh.exe')):
            command = tree_launcher.build_command(tree_launcher.parser().parse_args([]), expected_fruit='apple')
        self.assertEqual(command[command.index('-File') + 1], tree_launcher.windows_path(ROOT / 'scripts/build_tree.ps1'))

    def test_tree_launcher_only_exposes_configuration_and_diagnostics(self):
        fields = {action.dest for action in tree_launcher.parser()._actions}
        self.assertEqual(fields, {'help', 'config', 'dry_run'})

    def test_missing_tree_config_is_rejected(self):
        args = tree_launcher.parser().parse_args(['--config', str(self.directory / 'missing.json')])
        with patch.object(tree_launcher, 'powershell_path', return_value=Path('pwsh.exe')):
            with self.assertRaises(FileNotFoundError):
                tree_launcher.build_command(args, expected_fruit='apple')

    def test_bundled_shell_has_priority_when_available(self):
        bundled = ROOT / '.runtime/powershell/pwsh.exe'
        if not bundled.is_file():
            self.skipTest('Scratch copy does not contain the bundled runtime.')
        self.assertEqual(tree_launcher.powershell_path(), bundled)

    def test_apple_cannot_use_orange_sapling_route(self):
        args = self.tree_args({'fruit': 'apple', 'generator': 'sapling'})
        with patch.object(tree_launcher, 'powershell_path', return_value=Path('pwsh.exe')):
            with self.assertRaises(ValueError):
                tree_launcher.build_command(args, expected_fruit='apple')

    def test_invalid_trunk_ratio_is_rejected(self):
        args = self.tree_args({'fruit': 'apple', 'treeHeight': 4., 'trunkHeight': 3.})
        with patch.object(tree_launcher, 'powershell_path', return_value=Path('pwsh.exe')):
            with self.assertRaises(ValueError):
                tree_launcher.build_command(args, expected_fruit='apple')

    def test_obsolete_entries_and_configuration_are_absent(self):
        for relative in ('Open-FruitTree.ps1', 'Generate-FruitTree.ps1', 'configs/apple_photo_reference.json',
                         '.run/Open_Latest_Fruit_Tree.run.xml', 'scripts/verify_saved_scene.py'):
            self.assertFalse((ROOT / relative).exists(), relative)


if __name__ == '__main__':
    unittest.main()
