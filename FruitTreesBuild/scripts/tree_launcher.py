"""Internal shared launcher behind the two fixed tree-building scripts.

No third-party Python packages or bpy are required in the project interpreter.
The existing PowerShell entry retains isolated Blender settings and run logs.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.launcher_config import load_build_config, load_config, require_type

DEFAULT_CONFIG = ROOT / "configs" / "apple_tree.json"


def host_kind():
    if os.name == "nt":
        return "windows"
    if "WSL_DISTRO_NAME" in os.environ or "microsoft" in platform.release().lower():
        return "wsl"
    raise RuntimeError("This project uses Windows Blender. Run this entry from Windows or WSL.")


def translate_path(path, direction):
    result = subprocess.run(["wslpath", direction, str(path)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode:
        raise RuntimeError("WSL path conversion failed: " + result.stderr.strip())
    return result.stdout.strip()


def local_path(value):
    if host_kind() == "wsl" and re.match(r"^[A-Za-z]:[\\/]", str(value)):
        return Path(translate_path(value, "-u")).resolve()
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def windows_path(path):
    if host_kind() == "windows":
        return str(path)
    return translate_path(path, "-w")


def powershell_path(explicit=None):
    if explicit:
        candidate = local_path(explicit)
        if not candidate.is_file():
            raise FileNotFoundError("PowerShell executable not found: " + str(candidate))
        return candidate
    bundled = ROOT / '.runtime' / 'powershell' / 'pwsh.exe'
    if bundled.is_file():
        return bundled
    discovered = shutil.which("pwsh.exe")
    if discovered:
        return Path(discovered)
    if host_kind() == "windows":
        candidates = [Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe",
                      Path("C:/Program Files/PowerShell/7/pwsh.exe")]
    else:
        # Fallback installation locations; the bundled runtime takes priority.
        candidates = [Path("/mnt/c/Users/j/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"),
                      Path("/mnt/c/Program Files/PowerShell/7/pwsh.exe")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Windows PowerShell 7 not found. Restore .runtime/powershell or install PowerShell 7.")


def blender_candidates(report):
    discovered = shutil.which('blender.exe')
    if discovered:
        yield 'PATH', discovered
    # Query Windows through the existing shell, including when launched from WSL.
    query = r'''
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$keys = @('HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
          'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
          'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')
Get-ItemProperty -Path $keys -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like 'Blender*' -and $_.InstallLocation } |
    ForEach-Object { "registry`t" + (Join-Path $_.InstallLocation 'blender.exe') }
$apps = @('HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe',
          'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe')
Get-ItemProperty -Path $apps -ErrorAction SilentlyContinue |
    ForEach-Object { if ($_.'(default)') { "registry`t" + $_.'(default)' } }
$folders = @("$env:ProgramFiles\Blender Foundation\Blender*\blender.exe",
             "$env:LOCALAPPDATA\Programs\Blender Foundation\Blender*\blender.exe")
Get-Item -Path $folders -ErrorAction SilentlyContinue | Sort-Object FullName |
    ForEach-Object { "standard directory`t" + $_.FullName }
exit 0
'''
    try:
        result = subprocess.run([str(powershell_path()), '-NoLogo', '-NoProfile', '-NonInteractive',
                                 '-Command', query], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                encoding='utf-8', errors='replace', timeout=5)
        for line in result.stdout.splitlines():
            source, separator, value = line.partition('\t')
            if separator and value.strip():
                yield source, value.strip()
        if result.returncode:
            report.append('Windows installation lookup: ' + result.stderr.strip())
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report.append('Windows installation lookup: ' + str(exc))
    for candidate in sorted((ROOT / '.runtime').glob('blender*/blender.exe')):
        yield '.runtime', candidate


def resolve_blender(configured=None, explicit=None):
    host_kind()
    source, value = 'command line', explicit
    if not value:
        source, value = 'FRUITTREES_BLENDER', os.environ.get('FRUITTREES_BLENDER')
    if not value:
        local = ROOT / '.runtime/local.json'
        try:
            settings = load_config(local, {'blenderPath'}) if local.is_file() else {}
            value = settings.get('blenderPath')
            require_type('blenderPath', value, str, nullable=True)
        except (OSError, ValueError) as exc:
            raise ValueError('Invalid local Blender configuration {}: {}'.format(local, exc)) from exc
        source = str(local)
    if not value:
        source, value = 'configuration blenderPath', configured
    report, seen = [], set()
    strict = bool(value)
    candidates = [(source, value)] if strict else blender_candidates(report)
    for source, value in candidates:
        path = local_path(value)
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            if not path.is_file():
                raise ValueError('file does not exist')
            if path.suffix.lower() != '.exe':
                raise ValueError('expected a Windows Blender .exe, including under WSL')
            result = subprocess.run([str(path), '--version'], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, encoding='utf-8', errors='replace', timeout=5)
            version = re.search(r'^Blender\s+(\d+)\.(\d+)\.(\d+)\b', result.stdout, re.MULTILINE)
            if result.returncode or not version:
                raise ValueError('version check failed: ' + (result.stderr.strip() or result.stdout.strip()))
            if version.group(1, 2) != ('5', '2'):
                raise ValueError('requires Blender 5.2.x; found ' + version.group(0))
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            report.append('{}: {} ({})'.format(source, path, exc))
            if strict:
                break
        else:
            print('Blender: {} / {} / {}'.format(path, version.group(0), source), flush=True)
            return path
    raise RuntimeError('Cannot find compatible Blender 5.2.x.\n' + '\n'.join(report) +
                       '\nSet FRUITTREES_BLENDER, .runtime/local.json {"blenderPath":".../blender.exe"}'
                       ' or --blender. Automatic lookup checks PATH, Windows installs and optional .runtime.')


def parser(default_config=None):
    result = argparse.ArgumentParser(description="Build from the selected JSON configuration using Windows Blender.")
    result.add_argument("--config", default=str(default_config or DEFAULT_CONFIG))
    result.add_argument('--blender', help='Explicit Blender executable; otherwise discover the local installation.')
    result.add_argument("--dry-run", action="store_true", help="Diagnostic only: show the command without creating files.")
    return result


def build_command(args, expected_fruit=None):
    shell = powershell_path()
    script = ROOT / 'scripts/build_tree.ps1'
    if not script.is_file():
        raise FileNotFoundError("Project entry not found: " + str(script))
    command = [str(shell), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", windows_path(script)]
    config = local_path(args.config)
    if not config.is_file():
        raise FileNotFoundError("Configuration not found: " + str(config))
    settings = load_build_config(config)
    if expected_fruit:
        if settings.get('fruit', expected_fruit) != expected_fruit:
            raise ValueError('This fixed script builds ' + expected_fruit + ' trees only. Check fruit in ' + str(config))
    fruit = expected_fruit or settings.get('fruit', 'apple')
    method = settings.get('generator', 'auto')
    if method == 'sapling' and fruit != 'orange':
        raise ValueError('The Sapling route supports orange trees only.')
    height = settings.get('treeHeight', 4.)
    trunk = settings.get('trunkHeight', .6)
    if trunk >= height * .65:
        raise ValueError('trunkHeight must be less than 65% of treeHeight.')
    blender = resolve_blender(settings.get('blenderPath'), args.blender)
    command.extend(["-Config", windows_path(config), "-Fruit", fruit, '-BlenderPath', windows_path(blender)])
    return command


def execute(command):
    # Argument vectors are passed directly, never evaluated as a shell command.
    try:
        process = subprocess.Popen(command, cwd=str(ROOT), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                   errors="replace", bufsize=1)
    except OSError as exc:
        raise RuntimeError("Could not start Windows PowerShell. In WSL, check that Windows executable interop is enabled. " + str(exc))
    try:
        for line in process.stdout:
            print(line, end="", flush=True)
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        return 130
    finally:
        process.stdout.close()


def main(argv=None, default_config=None, expected_fruit=None):
    args = parser(default_config).parse_args(argv)
    try:
        command = build_command(args, expected_fruit=expected_fruit)
        if args.dry_run:
            print(json.dumps({"host": host_kind(), "python": sys.executable,
                              "project": str(ROOT), "command": command}, ensure_ascii=False, indent=2))
            return 0
        print("Project: " + str(ROOT), flush=True)
        print("Configuration: " + str(local_path(args.config)), flush=True)
        print("Launcher Python: " + sys.executable, flush=True)
        print("Blender uses its own Python; the selected backend is reported below.", flush=True)
        code = execute(command)
        if code:
            print("Run failed. Check the console and the generated run.log.", file=sys.stderr)
        return code
    except (OSError, ValueError, RuntimeError) as exc:
        print("Launcher error: " + str(exc), file=sys.stderr)
        return 1


