"""Increment the apple seed until N successful assets exist.

Run from the project root or PyCharm:

    python scripts/run_apple_seeds.py
    python scripts/run_apple_seeds.py --successes 5

Edit ``TARGET_SUCCESSES`` below to change the default n. Each attempt increments
``seed`` in the selected configuration, then runs the fixed
generate_apple_tree.py entry. A successful attempt keeps its
generated/apple_tree_NNN folder. A failed attempt deletes that folder only when
it has no asset.blend (i.e. it is just a reserved directory and logs). The
numbering high-water mark is intentionally not reset, so numbers are never
reused.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / 'configs' / 'apple_tree.json'
GENERATE_SCRIPT = ROOT / 'generate_apple_tree.py'

# Change this constant to set how many successful assets one run should collect.
TARGET_SUCCESSES = 1
# Safety cap so an unlucky seed range cannot run forever. Set to 0 for no cap.
MAX_ATTEMPTS = 200


def load_config(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('Configuration must be a JSON object: ' + str(path))
    if not isinstance(data.get('seed'), int) or isinstance(data.get('seed'), bool):
        raise ValueError('Configuration seed must be an integer: ' + str(path))
    return data


def write_config(path, data):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                         encoding='utf-8')
    temporary.replace(path)


def output_folders():
    generated = ROOT / 'generated'
    if not generated.is_dir():
        return set()
    return {path for path in generated.glob('apple_tree_*') if path.is_dir()}


def folder_number(path):
    try:
        return int(path.name.rsplit('_', 1)[1])
    except (IndexError, ValueError):
        return -1


def delete_placeholder(folder):
    """Delete only a newly reserved apple_tree_NNN directory under generated/."""
    generated = (ROOT / 'generated').resolve()
    resolved = folder.resolve()
    if resolved.parent != generated or not resolved.name.startswith('apple_tree_'):
        raise RuntimeError('Refusing to delete an unexpected path: ' + str(resolved))
    if (resolved / 'asset.blend').is_file():
        raise RuntimeError('Refusing to delete a folder containing asset.blend: ' + str(resolved))
    shutil.rmtree(resolved)


def run_once(config_path, seed, dry_run=False):
    command = [sys.executable, str(GENERATE_SCRIPT), '--config', str(config_path)]
    print('Seed {}: {}'.format(seed, ' '.join(command)), flush=True)
    if dry_run:
        return 0, None
    before = output_folders()
    code = subprocess.run(command, cwd=str(ROOT)).returncode
    after = output_folders()
    created = sorted(after - before, key=folder_number)
    if not created:
        print('  No new output folder was created (seed {}).'.format(seed), flush=True)
        return code, None
    folder = created[-1]
    if len(created) > 1:
        print('  Warning: multiple new folders detected; handling the newest: {}'.format(
            folder.name), flush=True)
    if code == 0 and (folder / 'asset.blend').is_file():
        print('  KEEP {} (asset.blend present)'.format(folder.name), flush=True)
        return 0, folder
    if (folder / 'asset.blend').is_file():
        print('  KEEP {} for inspection (process failed after asset export)'.format(
            folder.name), flush=True)
        return 1, folder
    print('  DELETE {} (failed placeholder, no asset.blend)'.format(folder.name),
          flush=True)
    delete_placeholder(folder)
    return 1, folder


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(DEFAULT_CONFIG),
                        help='Apple configuration to update; default configs/apple_tree.json')
    parser.add_argument('--successes', type=int, default=None,
                        help='Stop after this many successful assets; default TARGET_SUCCESSES')
    parser.add_argument('--max-attempts', type=int, default=None,
                        help='Maximum seed attempts; default MAX_ATTEMPTS, 0 = unlimited')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show the next seed and command without changing files')
    args = parser.parse_args(argv)
    target = TARGET_SUCCESSES if args.successes is None else args.successes
    max_attempts = MAX_ATTEMPTS if args.max_attempts is None else args.max_attempts
    if target < 1:
        parser.error('--successes must be at least 1')
    if max_attempts < 0:
        parser.error('--max-attempts cannot be negative')
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config_path = config_path.resolve()
    if not config_path.is_file():
        print('Configuration not found: ' + str(config_path), file=sys.stderr)
        return 1
    if not GENERATE_SCRIPT.is_file():
        print('Entry not found: ' + str(GENERATE_SCRIPT), file=sys.stderr)
        return 1

    try:
        data = load_config(config_path)
    except (OSError, ValueError) as exc:
        print('Configuration error: ' + str(exc), file=sys.stderr)
        return 1
    print('Target: {} successful apple assets; next seed {}.'.format(
        target, data['seed'] + 1), flush=True)
    if max_attempts:
        print('Maximum attempts: {}.'.format(max_attempts), flush=True)
    if args.dry_run:
        run_once(config_path, data['seed'] + 1, dry_run=True)
        print('Dry run only; no seed, folder, or asset was changed.', flush=True)
        return 0

    failures = 0
    kept = 0
    attempts = 0
    try:
        while kept < target:
            if max_attempts and attempts >= max_attempts:
                print('Reached maximum attempts ({}) with {} successes.'.format(
                    max_attempts, kept), file=sys.stderr)
                break
            attempts += 1
            data = load_config(config_path)
            next_seed = data['seed'] + 1
            print('\nAttempt {} (kept {}/{}): incrementing seed {} -> {}'.format(
                attempts, kept, target, data['seed'], next_seed), flush=True)
            data['seed'] = next_seed
            write_config(config_path, data)
            code, folder = run_once(config_path, next_seed)
            if code == 0 and folder is not None:
                kept += 1
            else:
                failures += 1
    except KeyboardInterrupt:
        print('\nInterrupted; the current generated folder was left for inspection.',
              file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        print('Batch error: ' + str(exc), file=sys.stderr)
        return 1

    print('\nDone. attempts={} kept={} failed={} target={}'.format(
        attempts, kept, failures, target), flush=True)
    return 0 if kept >= target else 1


if __name__ == '__main__':
    sys.exit(main())
