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
from scripts.launcher_config import load_build_config

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


def parser(default_config=None):
    result = argparse.ArgumentParser(description="Build from the selected JSON configuration using Windows Blender.")
    result.add_argument("--config", default=str(default_config or DEFAULT_CONFIG))
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
    command.extend(["-Config", windows_path(config), "-Fruit", fruit])
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


