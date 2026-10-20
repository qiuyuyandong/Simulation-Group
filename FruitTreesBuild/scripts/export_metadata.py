"""Extract appearance metadata from the saved model without saving/modifying it."""
import argparse
import datetime
import json
import sys
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from asset_export import collect_metadata, sha256, get_container
from asset_geometry import visual_objects
from verify_asset import verify_loaded_asset


def main():
    if bpy.app.version[:2] != (5, 2):
        raise RuntimeError('Use Blender 5.2.x for metadata extraction.')
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--reviewer')
    parser.add_argument('--review-note', default='')
    parser.add_argument('--review-mode', choices=('declared', 'automated_test'), default='declared')
    parser.add_argument('--check-attachments', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    directory = Path(args.output_dir).resolve()
    model = Path(bpy.data.filepath).resolve()
    if model.name != 'asset.blend' or not directory.is_dir() or not (directory == model.parent or model.parent in directory.parents):
        raise RuntimeError('Load asset.blend and stage metadata alongside it or in a child directory.')
    source_hash = sha256(model)
    review = {'status': 'user_declared_complete' if args.review_mode == 'declared' else 'automated_test_only',
              'reviewer': args.reviewer, 'note': args.review_note,
              'recorded_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'source_model_sha256': source_hash,
              'basis': 'Invocation records a user declaration, not proof of human inspection; automated tests are labelled separately.'}
    data = collect_metadata(model, review)
    report = verify_loaded_asset(data, model)
    if args.check_attachments:
        from attachment_diagnostics import diagnose
        report['fruit_attachment_diagnostics'] = diagnose(visual_objects(get_container()), bpy.data.objects['Tree'])
    else:
        report['fruit_attachment_diagnostics'] = {'status': 'not_checked', 'reason': 'Optional --check-attachments was not requested.'}
    if sha256(model) != source_hash:
        raise RuntimeError('The source model changed during extraction; save and retry.')
    for name, value in (('asset_metadata.json', data), ('validation_report.json', report)):
        with (directory / name).open('w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
    print('METADATA_EXPORTED ' + json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
