"""Run Blender's Sapling branch generator in Blender 5.2 without its old UI.

Only the original IAMPS tree_add parameters are read from its source script.
The old scene script itself is never executed. We request Sapling's mesh
centerline, then the existing orchard asset pipeline builds bark/leaves/fruit.
"""
import ast
import importlib.util
import json
import random
from pathlib import Path
from types import SimpleNamespace

import bpy


ROOT = Path(__file__).resolve().parent.parent


def _literal(node, rng):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [_literal(item, rng) for item in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_literal(node.operand, rng)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'rd'
            and node.func.attr in ('randint', 'uniform', 'choice') and not node.keywords):
        return getattr(rng, node.func.attr)(*[_literal(item, rng) for item in node.args])
    raise ValueError('Unsupported original Sapling parameter expression: ' + ast.dump(node))


def original_parameters(seed, root=ROOT):
    source = root / 'vendor/iamps/sapling_tree_scene_gen.py'
    syntax = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
    calls = [node for node in ast.walk(syntax)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == 'tree_add' and isinstance(node.func.value, ast.Attribute)
             and node.func.value.attr == 'curve' and isinstance(node.func.value.value, ast.Attribute)
             and node.func.value.value.attr == 'ops'
             and isinstance(node.func.value.value.value, ast.Name)
             and node.func.value.value.value.id == 'bpy']
    if len(calls) != 1:
        raise RuntimeError('Expected exactly one original Sapling tree_add call.')
    rng = random.Random(seed)
    values = {keyword.arg: _literal(keyword.value, rng) for keyword in calls[0].keywords}
    values.update(seed=seed, showLeaves=False, leaves=0, makeMesh=True, useArm=False,
                  leafDupliObj='NONE', bend=0.0)
    return values


def generate_sapling_skeleton(args, root=ROOT):
    source = root / 'vendor/sapling/utils.py'
    spec = importlib.util.spec_from_file_location('fruit_sapling_core', str(source))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Expose Sapling's internal parent-spline map without changing its source.
    syntax = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
    function = next(node for node in syntax.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'addTree')
    function.body.append(ast.Return(value=ast.Tuple(elts=[ast.Name(id=name, ctx=ast.Load())
                         for name in ('splineToBone', 'isend', 'issplit', 'splitPidx')],
                         ctx=ast.Load())))
    wrapper = ast.Module(body=[function], type_ignores=[])
    exec(compile(ast.fix_missing_locations(wrapper), str(source), 'exec'), module.__dict__)
    parameters = original_parameters(args.seed, root)
    # Keep the upstream generator, but replace its long, densely branched
    # generic tree preset with an explicit managed-citrus design approximation.
    # Fixed levels avoid seed-dependent 3/4-level geometry explosions.
    parameters.update(levels=3, branches=(0, 28, 16, 5),
                      length=(1, .48, .65, .45), lengthV=(0, .12, .16, .12),
                      baseSize=.055, baseSize_s=.25, shape='1', shapeS='1',
                      baseSplits=2, splitHeight=.04, splitAngle=(28, 0, 0, 0),
                      splitAngleV=(8, 0, 0, 0),
                      downAngle=(90, 80, 52, 45), downAngleV=(0, 12, 18, 10),
                      curve=(0, -12, -10, 0), curveV=(12, 22, 25, 0),
                      attractUp=(0, 0, .2, .15), resU=3)
    lineage = module.addTree(SimpleNamespace(**parameters))
    tree = bpy.data.objects.get('treemesh')
    if tree is None or tree.type != 'MESH' or not tree.data.edges:
        raise RuntimeError('Sapling did not produce a usable mesh centerline.')
    curve = bpy.data.objects.get('tree')
    if curve is None or curve.type != 'CURVE':
        raise RuntimeError('Sapling did not preserve its parent-spline curve.')
    bridges, maximum_gap, original_components = _join_sapling_stems(tree.data, curve.data, lineage,
                                                                     parameters['resU'])
    if bridges:
        old_mesh = tree.data
        mesh = bpy.data.meshes.new('Sapling_Connected_Centerline')
        mesh.from_pydata([tuple(vertex.co) for vertex in old_mesh.vertices],
                         [tuple(edge.vertices) for edge in old_mesh.edges] + bridges, [])
        mesh.update()
        tree.data = mesh
        bpy.data.meshes.remove(old_mesh)
    tree['skeleton_method'] = 'sapling'
    tree['sapling_design_profile'] = 'managed_citrus_rounded_v2_uncalibrated'
    tree['sapling_effective_parameters_json'] = json.dumps(parameters, sort_keys=True)
    tree['sapling_source_components'] = original_components
    tree['sapling_connected_max_gap_source_units'] = maximum_gap
    for obj in list(bpy.data.objects):
        if obj != tree:
            bpy.data.objects.remove(obj, do_unlink=True)
    tree.name = 'Tree'
    return tree, parameters


def generate_scene(args):
    if args.generator != 'sapling' or args.fruit != 'orange' or args.profile != 'orchard':
        raise ValueError('Sapling route currently supports orchard orange trees only.')
    generate_sapling_skeleton(args)
    from modern_scene import append_prototypes_and_world
    append_prototypes_and_world(args)
    return 'sapling_scene.py (Blender Sapling branch algorithm)'


def _join_sapling_stems(mesh, curves, lineage, resolution):
    """Turn Sapling's separate spline stems into one acyclic centerline.

    Sapling curves join visually, but many mesh endpoints are not shared. Its
    own parent-spline map identifies which stem to connect; use the closest
    evaluated mesh sample on that parent spline rather than an arbitrary twig.
    """
    vertices = mesh.vertices
    parents = list(range(len(vertices)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for edge in mesh.edges:
        first, second = edge.vertices
        root_a, root_b = find(first), find(second)
        if root_a != root_b:
            parents[root_b] = root_a
    components = {}
    for index in range(len(vertices)):
        components.setdefault(find(index), []).append(index)
    if len(mesh.edges) != len(vertices) - len(components):
        raise RuntimeError('Sapling centerline unexpectedly contains a cycle.')
    if len(components) == 1:
        return [], 0.0, 1
    bone, is_end, is_split, split_point = lineage
    if len(curves.splines) != len(bone):
        raise RuntimeError('Sapling spline lineage count mismatch.')
    cursor = 0
    spline_indices = []
    for spline, ending, splitting in zip(curves.splines, is_end, is_split):
        first = cursor
        cursor += int(splitting) + int(not ending)
        cursor += (len(spline.bezier_points) - 1) * resolution
        spline_indices.append(list(range(first, cursor)))
    if cursor != len(vertices):
        raise RuntimeError('Sapling mesh/spline vertex mapping changed.')
    bridges = []
    maximum_gap = 0.0
    for index, parent_bone in enumerate(bone):
        if not parent_bone:
            continue
        if not parent_bone.startswith('bone') or len(parent_bone) < 11:
            raise RuntimeError('Unexpected Sapling parent reference: ' + str(parent_bone))
        parent_spline = int(parent_bone[4:-4])
        child = spline_indices[index][0]
        candidates = spline_indices[parent_spline]
        parent = min(candidates, key=lambda other: (vertices[other].co - vertices[child].co).length_squared)
        if find(child) == find(parent):
            continue
        gap = (vertices[parent].co - vertices[child].co).length
        maximum_gap = max(maximum_gap, gap)
        bridges.append((parent, child))
        parents[find(child)] = find(parent)
    if len(bridges) != len(components) - 1:
        raise RuntimeError('Sapling parent map left disconnected stems: {} of {} joined.'.format(
            len(bridges), len(components) - 1))
    return bridges, maximum_gap, len(components)
