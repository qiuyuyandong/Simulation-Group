"""Verify the release ZIP in Blender --background --factory-startup."""
import hashlib
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

import addon_utils
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'release/SCA_Tree_Generator_0.2.17_Blender_5.2.1.zip'
assert bpy.app.version == (5, 2, 1)

with tempfile.TemporaryDirectory(prefix='sca_share_check_') as temporary:
    stage = Path(temporary) / '换目录 带空格'
    stage.mkdir()
    with zipfile.ZipFile(PACKAGE) as archive:
        assert archive.testzip() is None
        assert all(not Path(name).is_absolute() and '..' not in Path(name).parts
                   for name in archive.namelist())
        archive.extractall(stage)
    plugin_dir = stage / 'add_mesh_space_tree'
    assert plugin_dir.resolve().is_relative_to(Path(temporary).resolve())
    sys.path.insert(0, str(stage))
    module = addon_utils.enable('add_mesh_space_tree', default_set=False)
    assert module is not None
    assert Path(module.__file__).resolve().parent == plugin_dir.resolve()
    assert module.bl_info['version'] == (0, 2, 17)

    # Hide the loose texture copies to verify that the library is self-contained.
    textures = plugin_dir / 'textures'
    hidden_textures = plugin_dir / 'textures_not_used'
    assert textures.resolve().parent == hidden_textures.resolve().parent == plugin_dir.resolve()
    textures.rename(hidden_textures)

    names = None
    for attempt in range(12):
        materials = module.load_materials_from_bundled_lib('add_mesh_space_tree', 'material_lib.blend', 'Bark')
        names = set(materials) if names is None else names
        assert set(materials) == names and 'BarkBetter1.1' in materials
        module.barkmaterials = materials
        assert bpy.ops.mesh.sca_tree(updateTree=False, barkMaterial='BarkBetter1.1') == {'PASS_THROUGH'}
    print('PASS stable_material_names_12_reloads', flush=True)

    assert bpy.ops.mesh.sca_tree(updateTree=True, numberOfEndpoints=80, maxIterations=35,
                                noModifiers=False, subSurface=True,
                                barkMaterial='BarkBetter1.1') == {'FINISHED'}
    assert len(bpy.context.object.data.polygons) > 0
    assert bpy.ops.mesh.sca_tree(updateTree=True, numberOfEndpoints=80, maxIterations=35,
                                noModifiers=False, skinMethod='BLENDER', subSurface=True,
                                addLeaves=True, leafParticles='LeavesChestnutSummer',
                                objectParticles='ObjectsApples', barkMaterial='BarkBetter1.1') == {'FINISHED'}
    tree = bpy.context.object
    assert len(tree.children) == 1 and len(tree.children[0].particle_systems) == 2
    packed_images = [image for image in bpy.data.images if image.source == 'FILE']
    assert packed_images and all(image.packed_files and image.size[0] > 0 for image in packed_images)
    print('PASS trees_presets_and_packed_textures', flush=True)

    # Render a small image using only resources from the relocated package.
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 2
    scene.render.resolution_x = scene.render.resolution_y = 64
    scene.render.resolution_percentage = 100
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.4, 0.4, 0.4, 1)
    camera = scene.camera
    camera.location = (9, -12, 8)
    camera.rotation_euler = (Vector((0, 0, 5)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(stage / 'render_check.png')
    bpy.ops.render.render(write_still=True)
    header = Path(scene.render.filepath).read_bytes()[:24]
    assert header[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II', header[16:24]) == (64, 64)
    print('PASS relocated_package_render', flush=True)

    addon_utils.disable('add_mesh_space_tree', default_set=False)
    assert addon_utils.enable('add_mesh_space_tree', default_set=False) is not None
    addon_utils.disable('add_mesh_space_tree', default_set=False)

print('ALL PORTABLE PLUGIN CHECKS PASSED', hashlib.sha256(PACKAGE.read_bytes()).hexdigest(), flush=True)
