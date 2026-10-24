"""Edit configs/export_metadata.json, then run this fixed script with no args.

The model is read-only. No geometry generation, resave or directory allocation.
Use ordinary Windows/WSL Python; Blender runs with its own bundled interpreter.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

from scripts.tree_launcher import ROOT, local_path, windows_path, host_kind, resolve_blender
from scripts.launcher_config import load_config, require_type

DEFAULT_CONFIG = ROOT / 'configs/export_metadata.json'
CONFIG_FIELDS = {'assetDir': 'asset_dir', 'blenderPath': 'blender', 'threads': 'threads',
                 'reviewer': 'reviewer', 'reviewNote': 'review_note', 'reviewMode': 'review_mode',
                 'checkAttachments': 'check_attachments', 'verifyOnly': 'verify_only', 'dryRun': 'dry_run'}
DEFAULTS = {'asset_dir': '', 'blender': None,
            'threads': 4, 'reviewer': None, 'review_note': '', 'review_mode': 'declared',
            'check_attachments': False, 'verify_only': False, 'dry_run': False}


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, data):
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parser():
    result = argparse.ArgumentParser(description='Generate asset-level appearance metadata from an already saved tree; never modify asset.blend.')
    result.add_argument('--config', default=str(DEFAULT_CONFIG), help='Default: configs/export_metadata.json. Normal use needs no arguments.')
    result.add_argument('--asset-dir', help='Optional override of assetDir in the configuration.')
    result.add_argument('--blender')
    result.add_argument('--threads', type=int)
    result.add_argument('--reviewer')
    result.add_argument('--review-note')
    result.add_argument('--review-mode', choices=('declared', 'automated_test'))
    result.add_argument('--check-attachments', action=argparse.BooleanOptionalAction, default=None, help='Optional connection diagnostics; not a full penetration test.')
    result.add_argument('--verify-only', action=argparse.BooleanOptionalAction, default=None, help='Check existing metadata without writing files.')
    result.add_argument('--dry-run', action=argparse.BooleanOptionalAction, default=None)
    return result


def resolve_options(args):
    config = local_path(args.config)
    settings = load_config(config, CONFIG_FIELDS)
    for key in ('assetDir', 'reviewNote'):
        if key in settings:
            require_type(key, settings[key], str)
    if 'blenderPath' in settings:
        require_type('blenderPath', settings['blenderPath'], str, nullable=True)
    if 'reviewer' in settings:
        require_type('reviewer', settings['reviewer'], str, nullable=True)
    if 'threads' in settings:
        require_type('threads', settings['threads'], int)
    for key in ('checkAttachments', 'verifyOnly', 'dryRun'):
        if key in settings:
            require_type(key, settings[key], bool)
    if 'reviewMode' in settings and settings['reviewMode'] not in ('declared', 'automated_test'):
        raise ValueError('reviewMode must be declared or automated_test.')
    values = dict(DEFAULTS)
    values.update({CONFIG_FIELDS[key]: value for key, value in settings.items()})
    values.update({field: getattr(args, field) for field in DEFAULTS if getattr(args, field) is not None})
    if not values['asset_dir'].strip():
        raise ValueError('Set assetDir in ' + str(config) + ' to the reviewed asset folder, e.g. generated/apple_tree_007. No file was modified.')
    if values['threads'] < 1:
        raise ValueError('threads must be positive.')
    return argparse.Namespace(config=str(config), blender_override=args.blender, **values)


def blender_environment():
    environment = dict(os.environ)
    for name, folder in (('BLENDER_USER_CONFIG', 'config'), ('BLENDER_USER_SCRIPTS', 'scripts'),
                         ('BLENDER_USER_DATAFILES', 'datafiles')):
        environment[name] = windows_path(ROOT / '.runtime/user' / folder)
    return environment


def blender_command(executable, model, script, arguments, threads):
    command = [str(executable), '--background', '--factory-startup', '--disable-autoexec',
               '--python-exit-code', '1', '--threads', str(threads), windows_path(model),
               '--python', windows_path(ROOT / 'scripts' / script)]
    if arguments:
        command += ['--'] + arguments
    return command


def run_blender(executable, model, script, arguments, threads, log):
    command = blender_command(executable, model, script, arguments, threads)
    with log.open('a', encoding='utf-8') as handle:
        process = subprocess.Popen(command, cwd=str(ROOT), env=blender_environment(), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        try:
            for line in process.stdout:
                print(line, end='', flush=True)
                handle.write(line)
            code = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            process.wait()
            raise
        finally:
            process.stdout.close()
    if code:
        raise RuntimeError(script + ' failed. No new metadata was published; inspect ' + str(log))


def publish(directory, stage, source_hash):
    """Back up/replace sidecars only; a changed source aborts publication."""
    if checksum(directory / 'asset.blend') != source_hash:
        raise RuntimeError('asset.blend changed during metadata extraction. Save the model and retry.')
    record_path = directory / 'metadata.json'
    record = json.loads(record_path.read_text(encoding='utf-8-sig')) if record_path.is_file() else None
    if record is not None and not isinstance(record, dict):
        raise ValueError('Historic metadata.json must contain a JSON object.')
    names = ('asset_metadata.json', 'validation_report.json', 'metadata.log', 'metadata.json')
    present = {name for name in names if (directory / name).is_file()}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:6]
    backup = directory / 'history' / stamp if present else None
    if backup:
        backup.mkdir(parents=True)
        for name in present:
            shutil.copy2(directory / name, backup / name)
    if record is not None:
        record.update({'run_status': 'complete', 'asset_stage': 'metadata_generated',
                       'asset_metadata_file': 'asset_metadata.json', 'final_model_sha256': source_hash,
                       'metadata_history_backup': 'history/' + stamp if backup else None})
        write_json(stage / 'metadata.json', record)
    replacements = ['asset_metadata.json', 'validation_report.json', 'metadata.log']
    if record is not None:
        replacements.append('metadata.json')
    published = []
    try:
        for name in replacements:
            os.replace(stage / name, directory / name)
            published.append(name)
    except BaseException:
        for name in published:
            if name in present:
                shutil.copy2(backup / name, directory / name)
            else:
                (directory / name).unlink()
        raise
    return backup


def generate(args):
    directory = local_path(args.asset_dir)
    if ROOT not in directory.parents:
        raise ValueError('Choose an asset directory inside this project, not the project root.')
    model = directory / 'asset.blend'
    if not model.is_file():
        raise FileNotFoundError(str(model))
    executable = resolve_blender(args.blender, args.blender_override)
    if args.threads < 1:
        raise ValueError('threads must be positive.')
    if args.dry_run:
        print(json.dumps({'host': host_kind(), 'configuration': args.config, 'asset': str(model), 'blender': str(executable),
                          'operation': 'read-only verify' if args.verify_only else 'read saved model / export sidecars / fresh-process verify',
                          'output': str(directory / 'asset_metadata.json'), 'model_will_be_modified': False,
                          'allocates_new_asset_number': False, 'review_mode': args.review_mode}, ensure_ascii=False, indent=2))
        return
    print('Configuration: ' + args.config, flush=True)
    print('Asset: ' + str(model), flush=True)
    print('Mode: ' + ('read-only verification' if args.verify_only else 'metadata export from saved model'), flush=True)
    if args.verify_only:
        command = blender_command(executable, model, 'verify_asset.py', [], args.threads)
        if subprocess.call(command, cwd=str(ROOT), env=blender_environment()):
            raise RuntimeError('Read-only verification failed; metadata may be stale.')
        return
    lock = directory / '.metadata.lock'
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError('Another exporter holds ' + str(lock) + '. Inspect any crashed process before removing the lock.')
    stage = None
    try:
        os.write(descriptor, str(os.getpid()).encode())
        source_hash = checksum(model)
        stage = Path(tempfile.mkdtemp(prefix='.metadata-', dir=str(directory)))
        log = stage / 'metadata.log'
        arguments = ['--output-dir', windows_path(stage), '--review-mode', args.review_mode]
        if args.reviewer:
            arguments += ['--reviewer', args.reviewer]
        if args.review_note:
            arguments += ['--review-note', args.review_note]
        if args.check_attachments:
            arguments.append('--check-attachments')
        run_blender(executable, model, 'export_metadata.py', arguments, args.threads, log)
        run_blender(executable, model, 'verify_asset.py', ['--metadata', windows_path(stage / 'asset_metadata.json')], args.threads, log)
        backup = publish(directory, stage, source_hash)
        stage.rmdir()
        print('Metadata ready: ' + str(directory / 'asset_metadata.json'), flush=True)
        print('asset.blend was read only; no new asset folder or number was created.', flush=True)
        if backup:
            print('Previous sidecars backed up: ' + str(backup), flush=True)
    except BaseException:
        if stage:
            print('Staging retained for inspection: ' + str(stage), file=sys.stderr)
        raise
    finally:
        os.close(descriptor)
        lock.unlink()


def main(argv=None):
    try:
        generate(resolve_options(parser().parse_args(argv)))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print('Metadata error: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
