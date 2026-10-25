"""Exercise the real PowerShell allocator, without generating or opening models."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('allocator_launcher', ROOT / 'scripts/tree_launcher.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def quoted(value):
    return "'" + str(value).replace("'", "''") + "'"


class OutputDirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = launcher.powershell_path()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='_numbering_test_', dir=str(ROOT))
        self.output = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def allocate(self, fruit='apple', expect_error=False):
        command = ("$ErrorActionPreference = 'Stop'; . " +
                   quoted(launcher.windows_path(ROOT / 'scripts/Output-Directories.ps1')) +
                   '; New-FruitAssetDirectory -OutputRoot ' + quoted(launcher.windows_path(self.output)) +
                   ' -Fruit ' + quoted(fruit) + ' | ConvertTo-Json -Compress')
        result = subprocess.run([str(self.shell), '-NoLogo', '-NoProfile',
                                 '-NonInteractive', '-Command', command],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                encoding='utf-8', errors='replace', timeout=45)
        if expect_error:
            self.assertNotEqual(result.returncode, 0)
            return
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_first_then_second(self):
        self.assertEqual(self.allocate()['Name'], 'apple_tree_001')
        self.assertEqual(self.allocate()['Name'], 'apple_tree_002')

    def test_fruit_counters_are_independent(self):
        self.allocate()
        self.assertEqual(self.allocate('orange')['Name'], 'orange_tree_001')
        self.assertEqual(self.allocate()['Name'], 'apple_tree_002')

    def test_existing_incomplete_folder_is_not_overwritten(self):
        folder = self.output / 'apple_tree_001'
        folder.mkdir()
        marker = folder / 'run.log'
        marker.write_text('preserve me', encoding='utf-8')
        self.assertEqual(self.allocate()['Name'], 'apple_tree_002')
        self.assertEqual(marker.read_text(encoding='utf-8'), 'preserve me')

    def test_gaps_are_not_filled(self):
        (self.output / 'apple_tree_005').mkdir()
        self.assertEqual(self.allocate()['Name'], 'apple_tree_006')

    def test_deleted_number_is_not_reused(self):
        self.allocate()
        (self.output / 'apple_tree_001').rmdir()
        self.assertEqual(self.allocate()['Name'], 'apple_tree_002')

    def test_numbers_beyond_999(self):
        (self.output / 'apple_tree_999').mkdir()
        self.assertEqual(self.allocate()['Name'], 'apple_tree_1000')

    def test_nonmatching_names_are_ignored_and_files_are_reserved(self):
        (self.output / 'space_apple_seed101').mkdir()
        (self.output / 'apple_tree_002').write_text('not a directory', encoding='utf-8')
        self.assertEqual(self.allocate()['Name'], 'apple_tree_003')

    def test_parallel_reservations_have_distinct_numbers(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            names = [record['Name'] for record in pool.map(lambda _: self.allocate(), range(5))]
        self.assertEqual(sorted(names), ['apple_tree_{:03d}'.format(n) for n in range(1, 6)])

    def test_corrupt_state_fails_without_reusing_number(self):
        (self.output / '.asset-numbering.json').write_text('{broken', encoding='utf-8')
        self.allocate(expect_error=True)
        self.assertFalse((self.output / 'apple_tree_001').exists())

    def test_invalid_state_is_preserved_without_allocating(self):
        states = [
            {'schema_version': '2.0.0', 'last_allocated': {'apple': 0, 'orange': 0}},
            {'schema_version': '1.0.0', 'last_allocated': []},
            {'schema_version': '1.0.0', 'last_allocated': {'apple': 0}},
            {'schema_version': '1.0.0', 'last_allocated': {'apple': -1, 'orange': 0}},
            {'schema_version': '1.0.0', 'last_allocated': {'apple': 'bad', 'orange': 0}},
        ]
        path = self.output / '.asset-numbering.json'
        for state in states:
            with self.subTest(state=state):
                text = json.dumps(state)
                path.write_text(text, encoding='utf-8')
                self.allocate(expect_error=True)
                self.assertEqual(path.read_text(encoding='utf-8'), text)
                self.assertFalse((self.output / 'apple_tree_001').exists())


class WindowsPowerShell51OutputDirectoryTests(OutputDirectoryTests):
    @classmethod
    def setUpClass(cls):
        path = launcher.local_path(os.environ.get('SystemRoot', 'C:/Windows') +
                                   '/System32/WindowsPowerShell/v1.0/powershell.exe')
        if not path.is_file():
            raise unittest.SkipTest('Windows PowerShell 5.1 is not installed.')
        cls.shell = launcher.powershell_path(str(path))

    def test_shell_is_windows_powershell_51(self):
        result = subprocess.run([str(self.shell), '-NoLogo', '-NoProfile', '-NonInteractive',
                                 '-Command', '$PSVersionTable.PSVersion.ToString()'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout.strip(), r'^5\.1\.')


if __name__ == '__main__':
    unittest.main()
