"""Read-only Blender regression on a newly generated orange asset.

Load asset.blend, then run this script. Optional --report writes test evidence.
No asset edits or metadata declarations are saved.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from asset_export import get_container, geometry_bounds, sha256
from asset_geometry import check_saved_scene
from citrus_geometry import (FruitClearance, verify_leaf_connections,
                             verify_leaf_fruit_clearance)
from fruit_attachment import verify_connections
from verify_asset import _same

parser = argparse.ArgumentParser()
parser.add_argument('--report')
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
args = parser.parse_args(argv)
model = Path(bpy.data.filepath).resolve()
source_hash = sha256(model)
group, root = get_container(), bpy.data.objects['Tree']
objects = check_saved_scene(group, root)
record = json.loads(root['generation_record_json'])['generation']
parameters = record['parameters']
if parameters['generator'] != 'sapling':
    raise RuntimeError('Citrus regression requires a Sapling candidate.')
leaves = [obj for obj in objects if obj.get('asset_role') == 'leaf']
fruits = [obj for obj in objects if obj.get('asset_role') == 'fruit']
assert len(leaves) == parameters['leaf_count']
assert len(fruits) == parameters['fruit_count']
assert {obj['fruit_id'] for obj in fruits} == {'Fruit_{:04d}'.format(i + 1) for i in range(len(fruits))}
leaf_checks = verify_leaf_connections(objects, root)
fruit_checks = verify_connections(objects, root)
clearance_checks = verify_leaf_fruit_clearance(leaves, fruits, parameters['leaf_fruit_clearance'])

# Actual positions, not a flag copied from the generation record.
spacing = parameters['leaf_length'] * .33
minimum_spacing = None
if len(leaves) > 1:
    tree = KDTree(len(leaves))
    for index, obj in enumerate(leaves):
        tree.insert(obj.matrix_world.translation, index)
    tree.balance()
    minimum_spacing = min(tree.find_n(obj.matrix_world.translation, 2)[1][2] for obj in leaves)
    assert minimum_spacing >= spacing - 1e-6
for obj in leaves:
    mesh = obj.data
    assert mesh.vertices[int(mesh['petiole_base_vertex'])].co.length < 1e-8
    assert mesh.vertices[int(mesh['blade_base_vertex'])].co.x > 0
    assert len(mesh.polygons) < 100
    assert mesh.uv_layers
    assert all(not any(n.bl_idname == 'ShaderNodeBsdfTransparent' for n in material.node_tree.nodes)
               for material in mesh.materials)
assert root.get('wood_surface_method') == 'parallel_transport_eight_sided_tubes_v1'
assert not any(obj.get('asset_role') == 'collision_proxy' for obj in objects)

# A detached leaf must fail, rather than returning an unconditional pass.
leaf = leaves[0] if leaves else None
if leaf:
    original_location = leaf.location.copy()
    leaf.location += Vector((10, 10, 10))
    try:
        try:
            verify_leaf_connections(objects, root)
        except RuntimeError:
            detached_leaf_rejected = True
        else:
            raise AssertionError('Detached leaf was accepted.')
    finally:
        leaf.location = original_location
        bpy.context.view_layer.update()
else:
    detached_leaf_rejected = None

# A triangle crossing a fruit with ALL THREE corners outside still conflicts.
if fruits:
    checker = FruitClearance(fruits[:1], parameters['leaf_fruit_clearance'])
    _, center, radius = checker.fruits[0]
    mesh = bpy.data.meshes.new('Temporary_Test_Triangle')
    extent = radius * 4
    mesh.from_pydata([(-extent, -extent, 0), (extent, -extent, 0), (0, extent, 0)], [], [(0, 1, 2)])
    assert all(Vector(v.co).length > radius for v in mesh.vertices)
    assert checker.conflicts(mesh, Matrix.Translation(center))
    assert not checker.conflicts(mesh, Matrix.Translation(center + Vector((0, 0, extent * 3))))
    bpy.data.meshes.remove(mesh)
    crossing_triangle_rejected = True
else:
    crossing_triangle_rejected = None

before_bounds, before_objects = geometry_bounds(objects, root)
before_fruit = {obj['fruit_id']: before_objects[obj.name] for obj in fruits}
old = root.matrix_world.copy()
root.matrix_world = Matrix.Translation((3., -2., .5)) @ Euler((.17, -.13, .61)).to_matrix().to_4x4() @ old
bpy.context.view_layer.update()
verify_leaf_connections(objects, root)
verify_leaf_fruit_clearance(leaves, fruits, parameters['leaf_fruit_clearance'])
after_bounds, after_objects = geometry_bounds(objects, root)
_same(before_bounds, after_bounds, 'rigid root placement bounds')
_same(before_fruit, {obj['fruit_id']: after_objects[obj.name] for obj in fruits}, 'rigid root fruit mapping')
root.matrix_world = old
bpy.context.view_layer.update()
assert sha256(model) == source_hash
report = {'result': 'passed', 'model_sha256': source_hash, 'leaf_connections': leaf_checks,
          'fruit_connections': fruit_checks, 'leaf_fruit_clearance': clearance_checks,
          'minimum_leaf_base_spacing_m': minimum_spacing, 'detached_leaf_rejected': detached_leaf_rejected,
          'crossing_triangle_with_exterior_corners_rejected': crossing_triangle_rejected,
          'rigid_placement_preserves_connections_clearance_and_local_fruits': True,
          'leaf_materials_opaque_and_uvs_preserved': True, 'no_collision_proxies': True,
          'saved_asset_unmodified': True, 'visual_bounds_local': before_bounds,
          'wood_vertices': len(root.data.vertices), 'wood_faces': len(root.data.polygons),
          'scope': 'visual geometry; not full blade/blade or wood self-intersection certification'}
if args.report:
    Path(args.report).write_text(json.dumps(report, indent=2), encoding='utf-8')
print('CITRUS_REGRESSION ' + json.dumps(report, sort_keys=True))
