"""Constrained orchard preview built from the upstream Space Tree skeleton.

The dimensions are configurable design targets, not measured crop parameters.
Blender 2.79 / Python 3.5 compatible. Only newly generated scenes are changed.
"""
import bisect
import hashlib
import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector
from blender_compat import (LEGACY, transform, update_scene, link_object,
                            asset_container, select_only, diffuse_material)
from fruit_attachment import (calibrate_mesh, wood_surface_bvh, place_at_branch,
                              record_attachment, verify_connections)
from apple_branching import (reshape_crown, merge_coincident_nodes)
from apple_crown import (mesh_dimensions, populate_apple_leaves, verify_apple_leaves,
                         fruit_clear_of_wood)


ROOT = Path(__file__).resolve().parent.parent


def extract_skeleton(tree):
    """Read connected centerline edges from native SCA or Sapling geometry."""
    surface_vertices = set(index for face in tree.data.polygons for index in face.vertices)
    edges = [tuple(edge.vertices) for edge in tree.data.edges
             if all(index not in surface_vertices for index in edge.vertices)]
    indices = sorted(set(index for edge in edges for index in edge))
    if not indices:
        raise RuntimeError('The upstream tree has no recoverable centerline skeleton.')
    remap = {old: new for new, old in enumerate(indices)}
    points = [transform(tree.matrix_world, tree.data.vertices[index].co) for index in indices]
    edges = [(remap[a], remap[b]) for a, b in edges]
    root = min(range(len(points)), key=lambda i: points[i].z)
    adjacency = [[] for point in points]
    for a, b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    parent = {root: None}
    order = [root]
    for node in order:
        for neighbor in adjacency[node]:
            if neighbor not in parent:
                parent[neighbor] = node
                order.append(neighbor)
    if len(order) != len(points) or len(edges) != len(points) - 1:
        raise RuntimeError('Expected one connected, acyclic branch skeleton.')
    loads = [1 for point in points]
    for node in reversed(order[1:]):
        loads[parent[node]] += loads[node]
    return points, parent, loads, root


def bark_material():
    material, diffuse = diffuse_material('Orchard_Bark', (0.22, 0.13, 0.07))
    material.pass_index = 1
    nodes = material.node_tree.nodes
    textures = sorted(path for path in (ROOT / 'bark_texture').iterdir()
                      if path.suffix.lower() in ('.jpg', '.jpeg', '.png', '.tif', '.tiff'))
    if textures:
        coords = nodes.new('ShaderNodeTexCoord')
        mapping = nodes.new('ShaderNodeMapping')
        if LEGACY:
            mapping.scale = (3, 3, 5)
        else:
            mapping.inputs['Scale'].default_value = (3, 3, 5)
        image = nodes.new('ShaderNodeTexImage')
        image.image = bpy.data.images.load(str(textures[0]))
        image.projection = 'BOX'
        image.projection_blend = 0.25
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.18
        bump.inputs['Distance'].default_value = 0.006
        links = material.node_tree.links
        links.new(coords.outputs['Generated'], mapping.inputs['Vector'])
        links.new(mapping.outputs['Vector'], image.inputs['Vector'])
        links.new(image.outputs['Color'], diffuse.inputs['Color'])
        links.new(image.outputs['Color'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], diffuse.inputs['Normal'])
    return material


def rebuild_tree(tree, args):
    original, parent, loads, root = extract_skeleton(tree)
    merged_nodes = 0
    if args.generator == 'space':
        original, parent, loads, root, merged_nodes = merge_coincident_nodes(
            original, parent, loads, root)
    origin = original[root]
    source_height = max(point.z for point in original) - origin.z
    vertical_scale = (args.tree_height - args.trunk_height) / source_height
    # Preserve the earlier 4 m preview's crown width: 79% of the tree height.
    # This keeps X/Y independent of TrunkHeight, as before.
    source_width = max(max(point[i] for point in original) - min(point[i] for point in original)
                       for i in (0, 1))
    if source_width <= 0:
        raise RuntimeError('Cannot scale a zero-width skeleton.')
    crown_width = getattr(args, 'crown_width', None)
    lateral_scale = (crown_width / source_width if crown_width is not None
                     else args.tree_height * 0.79 / source_width)
    crown = [(point - origin) * vertical_scale + Vector((0, 0, args.trunk_height))
             for point in original]
    for point, source in zip(crown, original):
        horizontal = (source - origin) * lateral_scale
        point.x = horizontal.x
        point.y = horizontal.y
    # Apple path: bend outer shoots upward, enforce wide fork openings and
    # re-fit the crown to the configured height. Sapling keeps its own shape.
    if args.generator == 'space':
        branch_report = reshape_crown(crown, parent, root, args,
                                      args.trunk_height, args.tree_height)
    else:
        branch_report = {'branch_shaping': 'sapling_profile_unchanged'}
    # A shared centerline vertex joins the new bare trunk and existing crown.
    # No separate cylinder, floating crown, or disconnected overlap is used.
    segments = max(6, int(math.ceil(args.trunk_height / 0.18)))
    rng = random.Random(args.seed + 701)
    lean_x = rng.uniform(-0.025, 0.025)
    lean_y = rng.uniform(-0.018, 0.018)
    base = [Vector((lean_x * math.sin(math.pi * i / segments),
                    lean_y * math.sin(math.pi * i / segments),
                    args.trunk_height * i / segments)) for i in range(segments)]
    points = base + crown
    crown_offset = len(base)
    edges = [(i, i + 1) for i in range(len(base) - 1)]
    edges.append((len(base) - 1, crown_offset + root))
    edges.extend((crown_offset + node, crown_offset + ancestor)
                 for node, ancestor in parent.items() if ancestor is not None)
    base_radius = args.trunk_diameter / 2
    crown_radius = base_radius * 0.78
    taper = float(getattr(args, 'height_taper', 0.4)) if args.generator == 'space' else 0.0
    crown_span = max(1e-6, args.tree_height - args.trunk_height)
    radii = [base_radius * (1 - 0.22 * i / segments) for i in range(segments)]
    crown_radii = []
    for load, point in zip(loads, crown):
        height_fraction = max(0.0, min(1.0, (point.z - args.trunk_height) / crown_span))
        radius = crown_radius * (load / loads[root]) ** 0.52
        radius *= 1.0 - taper * height_fraction ** 1.25
        crown_radii.append(max(0.0015, radius))
    radii.extend(crown_radii)
    if args.generator == 'space':
        from apple_wood import build_apple_wood
        mesh, wood_report, wood_segments = build_apple_wood(points, parent, radii,
                                                            crown_offset, root, args)
        branch_report.update(wood_report)
        collar_count = wood_report['branch_base_flare_count']
    else:
        from citrus_geometry import swept_wood_mesh
        mesh = swept_wood_mesh(points, edges, radii)
        collar_count = 0
        wood_segments = None
    branch_report.update({'branch_shaping': 'upward_wide_angle_v1',
                          'branch_collar_count': collar_count,
                          'merged_coincident_branch_nodes': merged_nodes,
                          'height_taper': taper,
                          'branch_uplift': float(getattr(args, 'branch_uplift', 0.18)),
                          'branch_angle_target_min_deg': float(getattr(args, 'branch_angle_min', 120.0))})
    for modifier in list(tree.modifiers):
        tree.modifiers.remove(modifier)
    tree.data = mesh
    tree.location = (0, 0, 0)
    tree.rotation_euler = (0, 0, 0)
    tree.scale = (1, 1, 1)
    if LEGACY:
        tree.hide = False
    else:
        tree.hide_viewport = False
    tree.hide_render = False
    tree['asset_role'] = 'tree_wood'
    tree['semantic_class'] = 'wood'
    if args.generator == 'space':
        tree['wood_surface_method'] = 'continuous_trunk_parallel_transport_tubes_v1'
    else:
        tree['wood_surface_method'] = 'parallel_transport_eight_sided_tubes_v1'
    material = bark_material()
    mesh.materials.append(material)
    update_scene()
    return crown, parent, crown_radii, branch_report, wood_segments


def normalized_prototype(source, size, leaf=False):
    """Keep upstream UVs/materials, but remove their exaggerated deformation."""
    mesh = source.data.copy()
    coords = [transform(source.matrix_world.to_3x3(), vertex.co) for vertex in mesh.vertices]
    lower = [min(point[i] for point in coords) for i in range(3)]
    upper = [max(point[i] for point in coords) for i in range(3)]
    spans = [upper[i] - lower[i] for i in range(3)]
    scale = size / max(spans)
    if leaf:
        longest = max(range(3), key=lambda i: spans[i])
        remaining = sorted([i for i in range(3) if i != longest], key=lambda i: spans[i], reverse=True)
        width, normal = remaining
        for vertex, point in zip(mesh.vertices, coords):
            vertex.co = ((point[longest] - lower[longest]) * scale,
                         (point[width] - (lower[width] + upper[width]) / 2) * scale,
                         (point[normal] - (lower[normal] + upper[normal]) / 2) * scale)
    else:
        center = Vector(tuple((a + b) / 2 for a, b in zip(lower, upper)))
        for vertex, point in zip(mesh.vertices, coords):
            vertex.co = (point - center) * scale
    mesh.update()
    return mesh


def branch_sampler(points, parent, radii, minimum_height, maximum_radius=.035):
    candidates = []
    cumulative = []
    total = 0
    for node, ancestor in sorted(parent.items()):
        if ancestor is None:
            continue
        a, b = points[ancestor], points[node]
        if min(a.z, b.z) < minimum_height:
            continue
        radius = (radii[node] + radii[ancestor]) / 2
        if radius > maximum_radius:
            continue
        weight = (b - a).length / (1 + radius / 0.008) ** 1.5
        if weight <= 0:
            continue
        total += weight
        candidates.append((a, b, radii[ancestor], radii[node], node))
        cumulative.append(total)
    if not candidates:
        raise RuntimeError('No suitable crown twigs; reduce trunk height or clearance.')

    def sample(rng, with_branch=False):
        index = min(bisect.bisect_left(cumulative, rng.random() * total), len(candidates) - 1)
        a, b, first_radius, second_radius, node = candidates[index]
        fraction = rng.uniform(0.08, 0.92)
        point = a.lerp(b, fraction)
        if with_branch:
            return {'point': point, 'radius': first_radius * (1 - fraction) + second_radius * fraction,
                    'tangent': (b - a).normalized(), 'length': (b - a).length,
                    'edge_id': node, 'fraction': fraction}
        return point
    return sample


def add_instance(name, mesh, location, rotation, kind, group):
    obj = bpy.data.objects.new(name, mesh)
    link_object(obj)
    obj.location = location
    obj.rotation_euler = rotation
    obj.parent = bpy.data.objects['Tree']
    obj['asset_role'] = kind
    obj['semantic_class'] = kind
    obj['instance_id'] = name
    group.objects.link(obj)
    return obj


def bounding_min_z(obj):
    return min(transform(obj.matrix_world, Vector(corner)).z for corner in obj.bound_box)


def populate_crown(points, parent, radii, args, wood_segments=None):
    rng = random.Random(args.seed + 1709)
    group = asset_container('OrchardTree_Asset')
    group.objects.link(bpy.data.objects['Tree'])
    from citrus_geometry import FruitClearance, verify_leaf_fruit_clearance
    if args.generator == 'sapling':
        from citrus_geometry import (citrus_leaf_mesh, SpacingGrid, place_leaf,
                                     verify_leaf_connections)
        leaf_meshes = [citrus_leaf_mesh(args.leaf_length,
                      ROOT / 'leaf_texture/TexturesCom_Leaves0089_1_masked_S.png')]
    else:
        # Space Tree retains its two packed green leaf prototypes.
        leaf_meshes = [normalized_prototype(bpy.data.objects[name], args.leaf_length, leaf=True)
                       for name in ('green_leaves_PNG3638', 'green_leaves_PNG3668')]
    for mesh in leaf_meshes:
        for material in mesh.materials:
            material.pass_index = 2
    if args.generator == 'space' and wood_segments:
        from apple_wood import segment_sampler
        sample_leaf = segment_sampler(wood_segments,
                                      args.trunk_height + args.leaf_length + 0.04, .035,
                                      include_trunk=False)
    else:
        sample_leaf = branch_sampler(points, parent, radii,
                                     args.trunk_height + args.leaf_length + 0.04,
                                     maximum_radius=.014 if args.generator == 'sapling' else .035)
    wood = wood_surface_bvh(bpy.data.objects['Tree'])
    spacing = SpacingGrid(args.leaf_length * .33) if args.generator == 'sapling' else None
    leaves = []
    placement_stats = {'fruit_clearance_rejections': 0}

    # Fruit first for the apple path, so leaves can keep clear of actual fruit
    # volumes. The Sapling path keeps its original random order: fruit is also
    # placed before leaves there, but its leaf loop remains unchanged.
    source = bpy.data.objects['Apple' if args.fruit == 'apple' else 'Orange']
    fruit_mesh = normalized_prototype(source, args.fruit_diameter)
    for material in fruit_mesh.materials:
        material.pass_index = 3
    landmarks = calibrate_mesh(fruit_mesh, args.fruit)
    profile = landmarks['profile']
    body_materials = [index for index, material in enumerate(fruit_mesh.materials)
                      if material and material.name.split('.')[0] == profile['body_material']]
    if len(body_materials) != 1:
        raise RuntimeError('Missing/ambiguous fruit body material for collision checks.')
    body_vertices = sorted({index for polygon in fruit_mesh.polygons
                            if polygon.material_index == body_materials[0]
                            for index in polygon.vertices})
    if not body_vertices:
        raise RuntimeError('Fruit body has no vertices for collision checks.')
    alignment = landmarks['fruit_up_axis'].rotation_difference(Vector((0, 0, 1)))
    if args.generator == 'space' and wood_segments:
        from apple_wood import segment_sampler
        sample_fruit = segment_sampler(wood_segments,
                                       args.trunk_height + args.fruit_diameter * 1.5 + 0.06, .035,
                                       include_trunk=False)
    else:
        sample_fruit = branch_sampler(points, parent, radii,
                                      args.trunk_height + args.fruit_diameter * 1.5 + 0.06)
    fruits = []
    fruit_centers = []
    fruit_radii = []
    fruit_wood_rejections = 0
    fruit_spacing_rejections = 0
    stems = bpy.data.curves.new('Fruit_Stem_Links', 'CURVE')
    stems.dimensions = '3D'
    stems.bevel_depth = 0.0015
    stems.bevel_resolution = 0
    stem_material, diffuse = diffuse_material('Fruit_Stem_Material', (0.15, 0.22, 0.045))
    stem_material.pass_index = 3
    stems.materials.append(stem_material)
    for index in range(args.fruit_count):
        for attempt in range(2000):
            branch = sample_fruit(rng, with_branch=True)
            tilt = Euler((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12),
                          rng.uniform(0, 2 * math.pi)))
            rotation = transform(tilt.to_matrix(), alignment.to_matrix()).to_euler('XYZ')
            scale = rng.uniform(0.9, 1.1)
            placement = place_at_branch(branch, rotation, scale, landmarks, wood)
            if placement is None:
                continue
            location = placement['location']
            coordinates = [location + transform(rotation.to_matrix(), vertex.co) * scale
                           for vertex in fruit_mesh.vertices]
            lower = [min(point[i] for point in coordinates) for i in range(3)]
            upper = [max(point[i] for point in coordinates) for i in range(3)]
            center = Vector(tuple((a + b) / 2 for a, b in zip(lower, upper)))
            if lower[2] < args.trunk_height:
                continue
            if args.generator == 'space':
                body_center = location + transform(rotation.to_matrix(), landmarks['body_center']) * scale
                body_radius = max((body_center - (location + transform(rotation.to_matrix(),
                                   fruit_mesh.vertices[vertex].co) * scale)).length
                                  for vertex in body_vertices)
                if not fruit_clear_of_wood(body_center, body_radius, wood):
                    fruit_wood_rejections += 1
                    continue
                if all((body_center - previous).length > previous_radius + body_radius + 0.002
                       for previous, previous_radius in zip(fruit_centers, fruit_radii)):
                    break
                fruit_spacing_rejections += 1
            elif all((center - previous).length > args.fruit_diameter * 1.2 for previous in fruit_centers):
                break
        else:
            raise RuntimeError('Fruit spacing limit reached; lower FruitCount or FruitDiameter.')
        obj = add_instance('Fruit_{:04d}'.format(index + 1), fruit_mesh, location,
                           rotation, 'fruit', group)
        obj.scale = (scale, scale, scale)
        fruits.append(obj)
        if args.generator == 'space':
            fruit_centers.append(body_center)
            fruit_radii.append(body_radius)
        else:
            fruit_centers.append(center)
            fruit_radii.append(0.0)
        record_attachment(obj, landmarks, placement, index, args.fruit)
        spline = stems.splines.new('POLY')
        spline.points.add(1)
        spline.points[0].co = tuple(placement['anchor']) + (1,)
        spline.points[1].co = tuple(placement['endpoint']) + (1,)
    if fruits:
        stem_obj = bpy.data.objects.new('Fruit_Stems', stems)
        link_object(stem_obj)
        stem_obj.parent = bpy.data.objects['Tree']
        stem_obj['asset_role'] = 'fruit_stems'
        stem_obj['semantic_class'] = 'fruit_stems'
        group.objects.link(stem_obj)
    else:
        bpy.data.curves.remove(stems)

    if args.generator == 'sapling':
        update_scene()
        clearance = FruitClearance(fruits, args.leaf_fruit_clearance)
        leaf_rng = random.Random(args.seed + 3709)
        for index in range(args.leaf_count):
            for attempt in range(1000):
                placement = place_leaf(sample_leaf(leaf_rng, with_branch=True), leaf_rng, wood)
                if placement is None or not spacing.available(placement[0]):
                    continue
                location, rotation = placement
                scale = leaf_rng.uniform(.8, 1.15)
                matrix = Matrix.Translation(location) @ rotation.to_matrix().to_4x4() @ Matrix.Scale(scale, 4)
                if clearance.conflicts(leaf_meshes[0], matrix):
                    placement_stats['fruit_clearance_rejections'] += 1
                    continue
                spacing.add(location)
                break
            else:
                raise RuntimeError('Leaf spacing/fruit clearance capacity reached at leaf {} of {} ({} fruit-clearance rejections). Lower leafCount, leafLength or leafFruitClearance; no leaves were silently dropped.'.format(index + 1, args.leaf_count, placement_stats['fruit_clearance_rejections']))
            obj = add_instance('Leaf_{:04d}'.format(index + 1), leaf_meshes[0], location,
                               rotation, 'leaf', group)
            obj.scale = (scale, scale, scale)
            obj['leaf_attachment_method'] = 'petiole_on_wood_surface_v1'
            leaves.append(obj)
        leaf_checks = verify_leaf_connections(list(group.objects), bpy.data.objects['Tree'])
        clearance_checks = verify_leaf_fruit_clearance(leaves, fruits, args.leaf_fruit_clearance)
    else:
        update_scene()
        clearance = FruitClearance(fruits, args.leaf_fruit_clearance)
        dimensions = {mesh.name: mesh_dimensions(mesh) for mesh in leaf_meshes}
        placements, leaf_stats, leaf_index = populate_apple_leaves(
            sample_leaf, random.Random(args.seed + 3709), wood, leaf_meshes,
            dimensions, clearance, args)
        placement_stats.update(leaf_stats)
        for index, placement in enumerate(placements):
            obj = add_instance('Leaf_{:04d}'.format(index + 1), placement['mesh'],
                               placement['location'], placement['rotation'], 'leaf', group)
            obj.scale = (placement['scale'], placement['scale'], placement['scale'])
            obj['leaf_attachment_method'] = 'surface_normal_leaf_v1'
            obj['leaf_proxy_radius_m'] = placement['radius']
            leaves.append(obj)
        leaf_checks = verify_apple_leaves(placements, leaf_index, wood, leaves, fruits,
                                          args.leaf_spacing, args.leaf_fruit_clearance)
        clearance_checks = leaf_checks['fruit_clearance']
    update_scene()
    attachment_checks = verify_connections(list(group.objects), bpy.data.objects['Tree'])
    min_leaf = min([bounding_min_z(obj) for obj in leaves]) if leaves else None
    min_fruit = min([bounding_min_z(obj) for obj in fruits]) if fruits else None
    if any(value is not None and value < args.trunk_height for value in (min_leaf, min_fruit)):
        raise RuntimeError('Generated leaf/fruit bounds intrude into the bare trunk region.')
    return {'leaf_instances': len(leaves), 'fruit_instances': len(fruits),
            'minimum_leaf_z_m': min_leaf, 'minimum_fruit_z_m': min_fruit,
            'leaf_fruit_clear_of_trunk': True,
            'fruit_attachment_checks': attachment_checks,
            'leaf_attachment_checks': leaf_checks,
            'leaf_fruit_clearance_checks': clearance_checks,
            'fruit_wood_checks': ({'checked_fruits': len(fruits),
                                   'rejected_candidates': fruit_wood_rejections,
                                   'method': 'actual fruit body sphere vs evaluated skin surface'}
                                  if args.generator == 'space' else {'status': 'not_checked'}),
            'fruit_spacing_checks': ({'checked_fruits': len(fruits),
                                      'rejected_candidates': fruit_spacing_rejections,
                                      'minimum_body_clearance_m': 0.002,
                                      'method': 'actual fruit body spheres'}
                                     if args.generator == 'space' else {'method': 'target diameter spacing'}),
            'leaf_placement_stats': placement_stats,
            'leaf_base_minimum_spacing_m': args.leaf_length * .33 if args.generator == 'sapling' else args.leaf_spacing,
            'leaf_length_scale_range': [0.8, 1.15], 'fruit_diameter_scale_range': [0.9, 1.1]}


def add_ground():
    if LEGACY:
        bpy.ops.mesh.primitive_plane_add(radius=12, location=(0, 0, 0))
    else:
        bpy.ops.mesh.primitive_plane_add(size=24, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = 'Ground_Preview'
    obj['asset_role'] = 'preview_ground_not_tree_asset'
    material, diffuse = diffuse_material('Ground_Soil_Preview', (0.09, 0.06, 0.027), 0.8)
    material.pass_index = 0
    nodes = material.node_tree.nodes
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 75
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.09, 0.06, 0.027, 1)
    ramp.color_ramp.elements[1].color = (0.3, 0.22, 0.10, 1)
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.25
    bump.inputs['Distance'].default_value = 0.015
    links = material.node_tree.links
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], diffuse.inputs['Color'])
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], diffuse.inputs['Normal'])
    obj.data.materials.append(material)
    return obj


def build_orchard_shape(args):
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    tree = bpy.data.objects['Tree']
    points, parent, radii, branch_report, wood_segments = rebuild_tree(tree, args)
    report = populate_crown(points, parent, radii, args, wood_segments)
    report.update(branch_report)
    if not args.no_ground:
        add_ground()
    select_only(tree)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.region_3d.view_location = Vector((0, 0, args.tree_height / 2))
                space.region_3d.view_distance = args.tree_height * 1.8
    report.update({
        'profile': 'orchard', 'tree_height_target_m': args.tree_height,
        'bare_trunk_height_target_m': args.trunk_height,
        'trunk_base_diameter_target_m': args.trunk_diameter,
        'bare_trunk_height_fraction': args.trunk_height / args.tree_height,
        'bare_trunk_centerline_vertex_count': max(6, int(math.ceil(args.trunk_height / 0.18))),
        'crown_height_target_m': args.tree_height - args.trunk_height,
        'horizontal_scale_basis': ('Explicit maximum X/Y skeleton width target; preserves source asymmetry.'
                                   if getattr(args, 'crown_width', None) is not None else
                                   'Default initial skeleton width target is 79% of TreeHeight; upper-crown '
                                   'taper and angle pass determine the reported actual width.'),
        'crown_width_target_m': getattr(args, 'crown_width', None),
        'crown_horizontal_geometry_sha256': hashlib.sha256(json.dumps(
            [[point.x, point.y] for point in points], separators=(',', ':')).encode('utf-8')).hexdigest(),
        'crown_skeleton_width_actual_m': max(max(point[i] for point in points) - min(point[i] for point in points)
                                              for i in (0, 1)),
        'leaf_length_target_m': args.leaf_length, 'fruit_diameter_target_m': args.fruit_diameter,
        'ground_z_m': 0 if not args.no_ground else None,
        'dimension_basis': 'Design targets in metres, not measured cultivar/growth-stage calibration.',
        'branch_algorithm': ('Blender Sapling hierarchical branches, connected at recorded parent splines; '
                             'lower rounded citrus design profile; independently scaled crown and swept wood tubes.'
                             if args.generator == 'sapling' else
                             'Upstream Space Tree skeleton, upward lift with wide fork openings, '
                             'height-dependent branch taper; one continuous parallel-transport trunk tube '
                             'with flared branch tubes and segment-level trunk clearance checks.'),
        'sapling_source_components_joined': (tree.get('sapling_source_components')
                                             if args.generator == 'sapling' else None),
        'sapling_max_parent_bridge_source_units': (tree.get('sapling_connected_max_gap_source_units')
                                                   if args.generator == 'sapling' else None),
        'sapling_design_profile': tree.get('sapling_design_profile') if args.generator == 'sapling' else None,
        'sapling_effective_parameters': (json.loads(tree['sapling_effective_parameters_json'])
                                         if args.generator == 'sapling' else None),
        'asset_group': 'OrchardTree_Asset',
        'visual_basis': 'Qualitative proportions, not a reconstruction or measured fit to the reference photograph.',
        'limitations': ['Generic branching, not a validated pruning/training system.',
                        ('Petiole contact is checked; all blade/wood and blade/blade intersections are not validated.'
                         if args.generator == 'sapling' else
                         'Leaves are surface-attached and use conservative capsule/blade-sample/fruit-sphere '
                         'checks; full triangle-level mesh intersection is not certified.'),
                        ('Swept citrus branch junctions overlap visually; they are not a watertight solid union.'
                         if args.generator == 'sapling' else
                         'Trunk is one continuous tube; branches attach with a small flared base overlap. '
                         'Branch/trunk capsules and triangulated mesh overlaps are checked after repair, '
                         'but the combined wood is not a watertight boolean union.'),
                        'Reference soil plane is not a calibrated agricultural terrain.'],
    })
    return report
