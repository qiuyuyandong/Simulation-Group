"""Normalize ONLY a newly generated candidate into a standalone editable file."""
import argparse
import sys
from pathlib import Path
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from asset_export import get_container, geometry_bounds
from asset_geometry import group_objects, check_visual_structure
from blender_compat import select_only


def main():
    if bpy.app.version[:2] != (5, 2):
        raise RuntimeError('Use Blender 5.2.x for this project.')
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset-file', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source = Path(args.asset_file).resolve()
    if source.name != 'asset.blend' or source != Path(bpy.data.filepath).resolve():
        raise RuntimeError('Load the newly generated asset.blend.')
    if (source.parent / 'asset_metadata.json').exists():
        raise RuntimeError('Candidate normalization must not overwrite a reviewed asset.')
    group = get_container()
    if group is None:
        raise RuntimeError('Missing asset collection.')
    scenes = [scene for scene in bpy.data.scenes if set(group_objects(group)) == set(scene.objects)]
    if not scenes:
        raise RuntimeError('Expected a standalone asset scene.')
    scene = scenes[0]
    bpy.context.window.scene = scene
    for other in list(bpy.data.scenes):
        if other != scene:
            bpy.data.scenes.remove(other)
    if set(bpy.data.objects) != set(group_objects(group)) or scene.camera or scene.world:
        raise RuntimeError('Candidate contains non-asset objects, camera or world.')
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.
    root = bpy.data.objects['Tree']
    bounds, _ = geometry_bounds(check_visual_structure(group, root), root)
    select_only(root)
    center = Vector(tuple((a + b) / 2 for a, b in zip(bounds['min'], bounds['max'])))
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.type = 'MATERIAL'
                area.spaces.active.region_3d.view_location = root.matrix_world @ center
                area.spaces.active.region_3d.view_distance = max(2, (bounds['max'][2] - bounds['min'][2]) * 1.8)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(source), check_existing=False)
    print('CANDIDATE_READY ' + str(source))


if __name__ == '__main__':
    main()
