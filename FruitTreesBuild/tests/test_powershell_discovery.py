"""PowerShell selection and probes without starting Blender."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import tree_launcher as launcher


class PowerShellDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundled = self.root / '.runtime/powershell/pwsh.exe'
        self.pwsh = self.root / 'pwsh.exe'
        self.windows_shell = self.root / 'powershell.exe'
        self.system_shell = self.root / 'Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
        self.installed = self.root / 'Programs/PowerShell/7/pwsh.exe'
        for target, values in ((launcher, {'ROOT': self.root}),
                               (os, {'environ': {'SystemRoot': str(self.root / 'Windows'),
                                                'ProgramFiles': str(self.root / 'Programs')}})):
            replacement = patch.multiple(target, **values)
            replacement.start()
            self.addCleanup(replacement.stop)
        for target, name, options in (
                (launcher, 'host_kind', {'return_value': 'windows'}),
                (Path, 'home', {'return_value': self.root}),
                (launcher.shutil, 'which', {'side_effect': lambda name: {
                    'pwsh.exe': str(self.pwsh), 'powershell.exe': str(self.windows_shell)}.get(name)}),
                (launcher.subprocess, 'run', {'return_value': self.result()})):
            replacement = patch.object(target, name, **options)
            mocked = replacement.start()
            self.addCleanup(replacement.stop)
            if name == 'run':
                self.probe = mocked

    @staticmethod
    def result(version='7.6.5', code=0):
        return subprocess.CompletedProcess([], code, stdout=version + '\r\n', stderr='')

    def create(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    def test_bundled_then_path_pwsh_then_path_powershell(self):
        for candidate in (self.windows_shell, self.pwsh, self.bundled):
            self.create(candidate)
            self.assertEqual(launcher.powershell_path(), candidate)

    def test_system_shell_precedes_installed_pwsh(self):
        self.create(self.installed)
        self.assertEqual(launcher.powershell_path(), self.installed)
        self.create(self.system_shell)
        self.assertEqual(launcher.powershell_path(), self.system_shell)

    def test_explicit_path_has_priority_and_is_probed(self):
        self.create(self.bundled)
        explicit = self.create(self.root / 'custom shell.exe')
        self.assertEqual(launcher.powershell_path(str(explicit)), explicit)
        self.assertEqual(self.probe.call_args.args[0], [str(explicit), '-NoLogo', '-NoProfile',
                         '-NonInteractive', '-Command', '$PSVersionTable.PSVersion.ToString()'])
        self.assertEqual(self.probe.call_args.kwargs['timeout'], 5)

    def test_valid_versions_are_not_bound_to_seven(self):
        self.create(self.pwsh)
        for version in ('5.1.26100.9711', '7.6.5', '8.0.0', '8.0.0-preview.1'):
            with self.subTest(version=version):
                self.probe.return_value = self.result(version)
                self.assertEqual(launcher.powershell_path(), self.pwsh)

    def test_auto_skips_unusable_candidates(self):
        self.create(self.pwsh)
        self.create(self.windows_shell)
        failures = (OSError('cannot start'), subprocess.TimeoutExpired([], 5),
                    self.result('7.6.5', 1), self.result(''), self.result('not PowerShell'))
        for failure in failures:
            with self.subTest(failure=failure):
                self.probe.side_effect = [failure, self.result('5.1.26100.9711')]
                self.assertEqual(launcher.powershell_path(), self.windows_shell)

    def test_explicit_missing_or_broken_path_does_not_fall_back(self):
        self.create(self.bundled)
        explicit = self.root / 'custom.exe'
        with self.assertRaisesRegex(FileNotFoundError, 'custom.exe.*file does not exist'):
            launcher.powershell_path(str(explicit))
        self.probe.assert_not_called()
        self.create(explicit)
        self.probe.side_effect = OSError('cannot start')
        with self.assertRaisesRegex(FileNotFoundError, 'custom.exe.*cannot start'):
            launcher.powershell_path(str(explicit))
        self.probe.assert_called_once()

    def test_all_failed_candidates_report_clear_error(self):
        self.create(self.pwsh)
        self.probe.side_effect = OSError('cannot start')
        with self.assertRaisesRegex(FileNotFoundError, 'No usable PowerShell executable found') as error:
            launcher.powershell_path()
        self.assertIn(str(self.pwsh), str(error.exception))
        self.assertIn('cannot start', str(error.exception))

    def test_duplicate_candidates_are_only_probed_once(self):
        self.create(self.bundled)
        with patch.object(launcher.shutil, 'which', return_value=str(self.bundled)), \
                patch.object(Path, 'home', return_value=self.root):
            self.probe.side_effect = OSError('cannot start')
            with self.assertRaises(FileNotFoundError):
                launcher.powershell_path()
        self.probe.assert_called_once()

    def test_wsl_explicit_windows_path_is_converted_before_probe(self):
        self.create(self.windows_shell)
        windows = 'D:/Custom PowerShell/powershell.exe'
        with patch.object(launcher, 'host_kind', return_value='wsl'), \
                patch.object(launcher, 'translate_path', return_value=str(self.windows_shell)) as translate:
            self.assertEqual(launcher.powershell_path(windows), self.windows_shell)
        translate.assert_called_once_with(windows, '-u')
        self.assertEqual(self.probe.call_args.args[0][0], str(self.windows_shell))


if __name__ == '__main__':
    unittest.main()
