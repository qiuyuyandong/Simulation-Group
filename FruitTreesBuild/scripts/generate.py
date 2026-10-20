"""Build an editable Blender 5.2 candidate; final metadata follows review."""
import argparse
import json
import math
import os
import random
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from blender_compat import update_scene


def setup_output(args, output):
    scene = bpy.context.scene
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    # Assign categories to the selected fruit materials, including the missing
    # apple indices in the original space-tree script.
    for obj in bpy.data.objects:
        for slot in obj.material_slots:
            if not slot.material:
                continue
            if obj.name in ('Apple', 'Orange'):
                slot.material.pass_index = 3
    if not args.frames:
        return []
    hdri = sorted((ROOT / 'hdri').glob('*.hdr'))
    if not hdri:
        raise RuntimeError('No HDRI file is available.')
    scene.world.node_tree.nodes['Environment Texture'].image = bpy.data.images.load(str(hdri[0]))
    return hdri


def resolve_images():
    """Repair author-machine image paths in the addon library before packing."""
    roots = (ROOT / 'bark_texture', ROOT / 'hdri')
    missing = []
    for image in list(bpy.data.images):
        if image.source != 'FILE' or image.packed_file or not image.filepath:
            continue
        path = Path(bpy.path.abspath(image.filepath))
        if not path.exists():
            filename = image.filepath.replace('\\', '/').split('/')[-1]
            matches = [root / filename for root in roots if (root / filename).exists()]
            if matches:
                image.filepath = str(matches[0])
                image.reload()
            else:
                missing.append(image.name)
    if missing:
        raise RuntimeError('Unresolved texture images: ' + ', '.join(missing))


def place_camera(index, args):
    rng = random.Random(args.seed + index * 1009)
    theta = -math.pi / 2 if index == 1 else 2 * math.pi * rng.random()
    radius = args.tree_height * 1.95
    camera = bpy.data.objects['Camera']
    camera.data.lens = 50
    camera.location = (radius * math.cos(theta), radius * math.sin(theta), args.tree_height * 0.64)
    bpy.data.objects['Empty'].location = (0, 0, args.tree_height * 0.5)
    update_scene()


def write_json(path, data):
    with path.open('w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def main():
    if bpy.app.version[:2] != (5, 2):
        raise RuntimeError('This package supports native Blender 5.2.x only.')
    parser = argparse.ArgumentParser()
    parser.add_argument('--generator', choices=('space', 'sapling'), default='space')
    parser.add_argument('--fruit', choices=('apple', 'orange'), default='apple')
    parser.add_argument('--maturity-stage', choices=('unknown', 'unripe', 'turning', 'ripe'), default='unknown')
    parser.add_argument('--fruit-variant-id')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--frames', type=int, default=0)
    parser.add_argument('--resolution', type=int, default=512)
    parser.add_argument('--samples', type=int, default=16)
    parser.add_argument('--profile', choices=('auto', 'orchard'), default='orchard')
    parser.add_argument('--tree-height', type=float, default=4.0)
    parser.add_argument('--trunk-height', type=float, default=0.6)
    parser.add_argument('--crown-width', type=float)
    parser.add_argument('--leaf-fruit-clearance', type=float, default=.006)
    parser.add_argument('--branch-uplift', type=float, default=.18)
    parser.add_argument('--branch-angle-min', type=float, default=120.)
    parser.add_argument('--height-taper', type=float, default=.4)
    parser.add_argument('--leaf-spacing', type=float, default=.0015)
    parser.add_argument('--trunk-diameter', type=float, default=0.18)
    parser.add_argument('--leaf-count', type=int, default=3000)
    parser.add_argument('--fruit-count', type=int, default=80)
    parser.add_argument('--leaf-length', type=float, default=0.16)
    parser.add_argument('--fruit-diameter', type=float, default=0.08)
    parser.add_argument('--no-ground', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.profile == 'auto':
        args.profile = 'orchard'
    if not args.fruit_variant_id:
        args.fruit_variant_id = args.fruit + '_base_v1'
    if args.generator == 'sapling' and args.fruit != 'orange':
        raise ValueError('The original Sapling example supports orange trees only.')
    if args.frames < 0 or args.resolution < 64 or args.samples < 1:
        raise ValueError('Invalid generation settings.')
    dimensions = (args.tree_height, args.trunk_height, args.trunk_diameter, args.leaf_length, args.fruit_diameter)
    if any(not math.isfinite(value) or value <= 0 for value in dimensions):
        raise ValueError('Shape dimensions must be finite and positive.')
    if args.crown_width is not None and (not math.isfinite(args.crown_width) or args.crown_width <= 0):
        raise ValueError('Crown width must be finite and positive.')
    if not math.isfinite(args.leaf_fruit_clearance) or not 0 <= args.leaf_fruit_clearance <= .05:
        raise ValueError('Leaf/fruit clearance must be between 0 and .05 metres.')
    if not math.isfinite(args.branch_uplift) or not 0 <= args.branch_uplift <= 1:
        raise ValueError('Branch uplift must be between 0 and 1.')
    if not math.isfinite(args.branch_angle_min) or not 90 <= args.branch_angle_min <= 180:
        raise ValueError('Minimum branch angle must be between 90 and 180 degrees.')
    if not math.isfinite(args.height_taper) or not 0 <= args.height_taper <= .8:
        raise ValueError('Height taper must be between 0 and .8.')
    if not math.isfinite(args.leaf_spacing) or not 0 <= args.leaf_spacing <= .1:
        raise ValueError('Leaf spacing must be between 0 and .1 metres.')
    if args.trunk_height >= args.tree_height * 0.65:
        raise ValueError('TrunkHeight must be less than 65% of TreeHeight to leave a usable crown.')
    if args.leaf_count < 0 or args.fruit_count < 0:
        raise ValueError('Instance counts cannot be negative.')
    output = Path(args.output).resolve()
    if ROOT not in output.parents or output == ROOT:
        raise ValueError('Output must be a new directory inside this project.')
    if any((output / name).exists() for name in ('scene.blend', 'asset.blend', 'asset_metadata.json', 'metadata.json')):
        raise ValueError('Refusing to overwrite an existing scene.')
    output.mkdir(parents=True, exist_ok=True)
    if args.frames:
        (output / 'images').mkdir(exist_ok=True)
    os.chdir(str(ROOT))
    if args.generator == 'space':
        from modern_scene import generate_scene as generate_modern_scene
    else:
        from sapling_scene import generate_scene as generate_modern_scene
    source_name = generate_modern_scene(args)
    from orchard_shape import build_orchard_shape
    structure = build_orchard_shape(args)
    hdri_paths = setup_output(args, output)
    scene = bpy.context.scene
    scene.frame_set(1)
    if args.frames:
        place_camera(1, args)
    if structure and scene.camera:
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.region_3d.view_rotation = scene.camera.matrix_world.to_quaternion()
    resolve_images()
    bpy.ops.file.pack_all()
    from asset_export import export_asset
    generation_record = export_asset(args, output, source_name, structure)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'scene.blend'))
    records = []
    for index in range(1, args.frames + 1):
        scene.frame_set(index)
        place_camera(index, args)
        scene.world.node_tree.nodes['Environment Texture'].image = bpy.data.images.load(
            str(hdri_paths[((index - 1) // 2) % len(hdri_paths)]))
        image_path = output / 'images' / ('image_{:04d}.png'.format(index))
        scene.render.filepath = str(image_path)
        bpy.ops.render.render(write_still=True)
        records.append({
            'view_index': index,
            'image_path': str(image_path.relative_to(output)),
            'camera_matrix_world': [list(row) for row in scene.camera.matrix_world],
            'camera_lens_mm': scene.camera.data.lens,
            'sensor_width_mm': scene.camera.data.sensor_width,
            'target_location': list(bpy.data.objects['Empty'].location),
        })
    metadata = {
        'blender_version': bpy.app.version_string,
        'generator': args.generator,
        'profile': args.profile,
        'fruit': args.fruit,
        'seed': args.seed,
        'source_script': source_name,
        'resolution': [args.resolution, args.resolution],
        'samples': args.samples,
        'scene_file': 'scene.blend',
        'backend': 'modern',
        'asset_metadata_file': None,
        'asset_file': 'asset.blend',
        'run_status': 'pending_candidate_save',
        'asset_stage': 'awaiting_manual_review',
        'maturity_stage': args.maturity_stage,
        'fruit_variant_id': args.fruit_variant_id,
        'generation_record': generation_record,
        'units': 'metres (design targets, not empirical calibration)' if structure else 'uncalibrated Blender units',
        'structure': structure,
        'views': records,
        'limitations': [
            'Uncalibrated generic tree, not a validated species or growth-stage model.',
            'Fruit connections are checked; citrus petiole contacts are checked. All mesh intersections remain unvalidated.',
            'Optional RGB previews are not a complete annotated training dataset.',
            'Third-party assets require a separate license review before redistribution.',
            'Review and save asset.blend, then run generate_metadata.py for current asset-level metadata.',
            'Maturity/variant labels do not automatically change the bundled fruit appearance.',
        ],
    }
    write_json(output / 'metadata.json', metadata)
    print('GENERATION_COMPLETE ' + str(output))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(traceback.format_exc(), flush=True)
        sys.stdout.flush()
        sys.stderr.flush()
        raise
