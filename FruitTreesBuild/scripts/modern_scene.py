"""Native Blender 5.2 Space Tree route without registering the legacy addon.

The vendored SCA algorithm and its ellipsoid2 function are loaded unchanged.
The original shader/UV prototypes are appended from a self-contained library.
"""
import ast
import importlib.util
import math
import random
from functools import partial
from pathlib import Path
import bpy
from mathutils import Vector
from blender_compat import link_object, update_scene

ROOT = Path(__file__).resolve().parent.parent


def generate_scene(args):
    if args.generator != 'space' or args.profile != 'orchard':
        raise ValueError('Space Tree requires generator=space and profile=orchard.')
    vendor = ROOT / 'vendor/spacetree/src/add_mesh_space_tree'
    spec = importlib.util.spec_from_file_location('iamps_sca_core', str(vendor / 'scanew.py'))
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    # Do not import the old addon's __init__: it registers removed API classes.
    parsed = ast.parse((vendor / '__init__.py').read_text(encoding='utf-8'))
    function = next(node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name == 'ellipsoid2')
    module = ast.Module(body=[function], type_ignores=[])
    namespace = {'Vector': Vector, 'random': random.random, 'sin': math.sin, 'cos': math.cos}
    exec(compile(ast.fix_missing_locations(module), str(vendor / '__init__.py'), 'exec'), namespace)
    volume = partial(namespace['ellipsoid2'], 6.25, 5, Vector((0, 0, 5.75)), 1, 1)
    sca = core.SCA(NBP=160, NENDPOINTS=1400, d=0.75, KILLDIST=0.55,
                   INFLUENCE=15, SEED=args.seed, TROPISM=0.15, volume=volume,
                   apicalcontrol=1, apicalcontrolfalloff=15, apicaltiming=14)
    sca.iterate(newendpointsper1000=3, maxtime=0)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    mesh = bpy.data.meshes.new('Space_Tree_Centerline')
    mesh.from_pydata([tuple(point.v) for point in sca.branchpoints],
                     [(index, point.parent) for index, point in enumerate(sca.branchpoints)
                      if point.parent is not None], [])
    mesh.update()
    tree = bpy.data.objects.new('Tree', mesh)
    link_object(tree)
    append_prototypes_and_world(args)
    return 'modern_scene.py (vendored Space Colonization core)'


def append_prototypes_and_world(args):
    """Use the same packed fruit/leaf prototypes and preview world for both trees."""
    library = ROOT / 'assets/source_prototypes.blend'
    if not library.is_file():
        raise FileNotFoundError('Missing assets/source_prototypes.blend; see docs/asset_metadata.md.')
    names = ['green_leaves_PNG3638', 'green_leaves_PNG3668', 'Apple', 'Orange']
    with bpy.data.libraries.load(str(library), link=False) as (source, destination):
        if any(name not in source.objects for name in names):
            raise RuntimeError('Incomplete source prototype library.')
        destination.objects = list(names)
    sources = bpy.data.collections.new('Source_Prototypes_Not_Asset')
    bpy.context.scene.collection.children.link(sources)
    for obj in destination.objects:
        sources.objects.link(obj)
        obj.hide_render = True
        obj.hide_set(True)
    # Solid-view colors are independent of shaders. Keep shader graphs intact.
    for name in names[:2]:
        for material in bpy.data.objects[name].data.materials:
            material.diffuse_color = (0.18, 0.32, 0.06, 1)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    world = bpy.data.worlds.new('Preview_World')
    world.use_nodes = True
    scene.world = world
    environment = world.node_tree.nodes.new('ShaderNodeTexEnvironment')
    environment.name = 'Environment Texture'
    world.node_tree.links.new(environment.outputs['Color'], world.node_tree.nodes['Background'].inputs['Color'])
    if args.frames:
        target = bpy.data.objects.new('Empty', None)
        link_object(target)
        camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
        link_object(camera)
        camera.data.sensor_width = 32
        constraint = camera.constraints.new('TRACK_TO')
        constraint.target = target
        constraint.track_axis = 'TRACK_NEGATIVE_Z'
        constraint.up_axis = 'UP_Y'
        scene.camera = camera
    update_scene()
