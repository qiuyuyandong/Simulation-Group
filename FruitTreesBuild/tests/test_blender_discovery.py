"""Local executable selection without starting real Blender or changing config."""
import contextlib
import io
import json
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
import generate_metadata


class BlenderDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.first, self.second = self.root / 'first.exe', self.root / 'second.exe'
        self.first.touch()
        self.second.touch()
        for target, values in ((launcher, {'ROOT': self.root}), (os, {'environ': {}})):
            replacement = patch.multiple(target, **values)
            replacement.start()
            self.addCleanup(replacement.stop)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def result(self, text='Blender 5.2.1 LTS\r\n', code=0):
        return subprocess.CompletedProcess([], code, stdout=text, stderr='')

    def local_config(self, text):
        path = self.root / '.runtime/local.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def test_explicit_env_local_and_shared_precedence(self):
        self.local_config(json.dumps({'blenderPath': str(self.second)}))
        os.environ['FRUITTREES_BLENDER'] = str(self.second)
        with patch.object(launcher.subprocess, 'run', return_value=self.result()):
            self.assertEqual(launcher.resolve_blender('missing.exe', str(self.first)), self.first)
            self.assertEqual(launcher.resolve_blender('missing.exe'), self.second)
            del os.environ['FRUITTREES_BLENDER']
            self.assertEqual(launcher.resolve_blender('missing.exe'), self.second)
            self.local_config('{"blenderPath": null}')
            self.assertEqual(launcher.resolve_blender(str(self.first)), self.first)

    def test_invalid_explicit_sources_do_not_fall_back(self):
        sources = [({'explicit': 'missing.exe'}, {}), ({}, {'FRUITTREES_BLENDER': 'missing.exe'}),
                   ({'configured': 'missing.exe'}, {})]
        with patch.object(launcher, 'blender_candidates') as candidates:
            for arguments, environment in sources:
                with self.subTest(arguments=arguments, environment=environment), patch.dict(os.environ, environment, clear=True):
                    with self.assertRaisesRegex(RuntimeError, 'file does not exist'):
                        launcher.resolve_blender(**arguments)
            self.local_config('{"blenderPath": "missing.exe"}')
            with self.assertRaisesRegex(RuntimeError, 'local.json'):
                launcher.resolve_blender()
            candidates.assert_not_called()

    def test_bad_local_json_and_wrong_types_rejected(self):
        for text in ('{broken', '[]', '{"blenderPath": 2}', '{"blenderPath": "a", "blenderPath": "b"}'):
            self.local_config(text)
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'local.json'):
                launcher.resolve_blender()

    def test_rejects_wrong_version_failed_process_and_stderr_only(self):
        for result in (self.result('Blender 5.1.9'), self.result('Blender 5.2.1', 1), self.result('')):
            result.stderr = 'Blender 5.2.1'
            with self.subTest(result=result), patch.object(launcher.subprocess, 'run', return_value=result):
                with self.assertRaisesRegex(RuntimeError, 'first.exe'):
                    launcher.resolve_blender(explicit=str(self.first))

    def test_auto_skips_timeout_wrong_version_and_duplicate_paths(self):
        third = self.root / 'third.exe'
        third.touch()
        candidates = [('PATH', self.first), ('registry', self.first), ('registry', self.second), ('standard', third)]
        with patch.object(launcher, 'blender_candidates', return_value=iter(candidates)), \
                patch.object(launcher.subprocess, 'run', side_effect=[subprocess.TimeoutExpired([], 5),
                             self.result('Blender 6.0.0'), self.result()]) as probe:
            self.assertEqual(launcher.resolve_blender(), third)
            self.assertEqual(probe.call_count, 3)
            self.assertEqual(probe.call_args.kwargs['timeout'], 5)

    def test_registry_output_and_portable_candidate(self):
        portable = self.root / '.runtime/blender-custom/blender.exe'
        portable.parent.mkdir(parents=True)
        portable.touch()
        with patch.object(launcher.shutil, 'which', return_value=str(self.first)), \
                patch.object(launcher, 'powershell_path', return_value=Path('pwsh.exe')), \
                patch.object(launcher.subprocess, 'run', return_value=self.result('registry\t' + str(self.second) + '\r\n')):
            candidates = list(launcher.blender_candidates([]))
        self.assertEqual(candidates, [('PATH', str(self.first)), ('registry', str(self.second)), ('.runtime', portable)])

    def test_empty_discovery_reports_setup_choices(self):
        with patch.object(launcher, 'blender_candidates', return_value=iter([])):
            with self.assertRaisesRegex(RuntimeError, 'FRUITTREES_BLENDER.*local.json'):
                launcher.resolve_blender()

    def test_wsl_converts_windows_path_and_probes_windows_executable(self):
        windows = 'D:/Custom Blender/blender.exe'
        with patch.object(launcher, 'host_kind', return_value='wsl'), \
                patch.object(launcher, 'translate_path', return_value=str(self.first)) as translate, \
                patch.object(launcher.subprocess, 'run', return_value=self.result()) as probe:
            self.assertEqual(launcher.resolve_blender(explicit=windows), self.first)
        translate.assert_called_once_with(windows, '-u')
        self.assertEqual(probe.call_args.args[0], [str(self.first), '--version'])

    def test_metadata_calls_same_resolver_and_keeps_model_read_only(self):
        with tempfile.TemporaryDirectory(prefix='_config_test_', dir=str(ROOT)) as directory:
            asset = Path(directory)
            (asset / 'asset.blend').write_bytes(b'unchanged')
            config = asset / 'config.json'
            config.write_text(json.dumps({'assetDir': str(asset), 'blenderPath': None, 'dryRun': True}), encoding='utf-8')
            options = generate_metadata.resolve_options(generate_metadata.parser().parse_args(
                ['--config', str(config), '--blender', str(self.first)]))
            with patch.object(generate_metadata, 'resolve_blender', return_value=self.first) as resolve:
                generate_metadata.generate(options)
            resolve.assert_called_once_with(str(self.first), str(self.first))
            self.assertEqual((asset / 'asset.blend').read_bytes(), b'unchanged')


if __name__ == '__main__':
    unittest.main()
