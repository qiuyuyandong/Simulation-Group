"""Static citrus appearance: swept wood, trimmed leaves and real petioles.

These are visual meshes, not collision proxies or a botanical growth model.
The input image is sampled, not changed; its original texture and UVs remain.
"""
import math
from collections import defaultdict

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.geometry import closest_point_on_tri

from blender_compat import diffuse_material, update_scene
from fruit_attachment import wood_surface_bvh


def swept_wood_mesh(points, edges, radii, sides=8):
    """Sweep connected centerline chains without Skin's short-edge folds.

    Junctions use embedded overlapping tubes, not a watertight union. The
    smallest source twigs are retained; no crown convex hull is introduced.
    """
    neighbors = [[] for _ in points]
    for a, b in edges:
        neighbors[a].append(b)
        neighbors[b].append(a)
    visited, paths = set(), []
    for start in range(len(points)):
        if len(neighbors[start]) == 2:
            continue
        for nxt in sorted(neighbors[start]):
            if tuple(sorted((start, nxt))) in visited:
                continue
            path = [start, nxt]
            visited.add(tuple(sorted((start, nxt))))
            while len(neighbors[path[-1]]) == 2:
                following = next(value for value in neighbors[path[-1]] if value != path[-2])
                visited.add(tuple(sorted((path[-1], following))))
                path.append(following)
            paths.append(path)
    if len(visited) != len(edges):
        raise RuntimeError('Citrus wood sweep requires an acyclic skeleton.')
    vertices, faces = [], []
    for path in paths:
        clean = [path[0]]
        for index in path[1:]:
            if (points[index] - points[clean[-1]]).length > 1e-6:
                clean.append(index)
        if len(clean) < 2:
            continue
        rings = []
        previous_tangent, previous_side = None, None
        for position, index in enumerate(clean):
            if position == 0:
                tangent = (points[clean[1]] - points[index]).normalized()
                if index == 0:
                    # A planted trunk has a horizontal cut at ground z=0,
                    # even if the next centerline segment leans slightly.
                    tangent = Vector((0, 0, 1))
            elif position == len(clean) - 1:
                tangent = (points[index] - points[clean[-2]]).normalized()
            else:
                incoming = (points[index] - points[clean[position - 1]]).normalized()
                outgoing = (points[clean[position + 1]] - points[index]).normalized()
                tangent = (incoming + outgoing).normalized()
                if tangent.length < .5:
                    tangent = outgoing
            if previous_side is None:
                reference = Vector((0, 0, 1)) if abs(tangent.z) < .9 else Vector((0, 1, 0))
                side = tangent.cross(reference).normalized()
            else:
                side = previous_tangent.rotation_difference(tangent) @ previous_side
                side = (side - tangent * side.dot(tangent)).normalized()
            other = tangent.cross(side).normalized()
            radius = radii[index]
            if position == 0 and len(neighbors[index]) > 2:
                radius = min(radius, radii[clean[1]] * 1.15)
            if position == len(clean) - 1 and len(neighbors[index]) > 2:
                radius = min(radius, radii[clean[-2]] * 1.15)
            ring = []
            for step in range(sides):
                angle = 2 * math.pi * step / sides
                ring.append(len(vertices))
                vertices.append(tuple(points[index] + radius * (side * math.cos(angle) + other * math.sin(angle))))
            rings.append(ring)
            previous_tangent, previous_side = tangent, side
        faces.append(tuple(reversed(rings[0])))
        faces.append(tuple(rings[-1]))
        for first, second in zip(rings, rings[1:]):
            for step in range(sides):
                nxt = (step + 1) % sides
                faces.append((first[step], first[nxt], second[nxt], second[step]))
    mesh = bpy.data.meshes.new('Citrus_Swept_Wood')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    return mesh


def citrus_leaf_mesh(length, texture):
    """Opaque alpha-contour blade + integrated 3-D petiole, rooted at x=0.

    A cut-out quad's midpoint is NOT a botanical attachment landmark. Here
    vertex zero is the real petiole base and the blade starts at its tip.
    """
    image = bpy.data.images.load(str(texture), check_existing=True)
    width_px, height_px = image.size
    pixels = list(image.pixels[:])

    def silhouette(u):
        x = min(width_px - 1, round(u * (width_px - 1)))
        ys = [y for y in range(height_px) if pixels[(y * width_px + x) * 4 + 3] >= .7]
        if not ys:
            raise RuntimeError('Leaf mask has no opaque silhouette at u=' + str(u))
        return min(ys) / (height_px - 1), max(ys) / (height_px - 1)

    samples = 24
    last_column = next(x for x in reversed(range(width_px))
                       if any(pixels[(y * width_px + x) * 4 + 3] >= .7 for y in range(height_px)))
    last_u = last_column / (width_px - 1)
    u_values = [.07 + (last_u - .07) * i / samples for i in range(samples + 1)]
    profiles = [silhouette(u) for u in u_values]
    base_v = sum(profiles[0]) / 2
    petiole_length = length * .075
    radius = length * .0055
    width_scale = length * height_px / width_px
    vertices = [(0, 0, 0), (petiole_length, 0, 0)]
    vertex_uv = [(0, base_v), (.07, base_v)]
    faces, materials = [], []
    rings = []
    for x, r in ((0, radius), (petiole_length, radius * .65)):
        ring = []
        for step in range(6):
            angle = 2 * math.pi * step / 6
            ring.append(len(vertices))
            vertices.append((x, r * math.cos(angle), r * math.sin(angle)))
            vertex_uv.append((0, base_v))
        rings.append(ring)
    for step in range(6):
        nxt = (step + 1) % 6
        faces.extend(((0, rings[0][nxt], rings[0][step]),
                      (rings[0][step], rings[0][nxt], rings[1][nxt], rings[1][step]),
                      (1, rings[1][step], rings[1][nxt])))
        materials.extend((1, 1, 1))
    rows = []
    for index, (u, (bottom, top)) in enumerate(zip(u_values, profiles)):
        fraction = index / samples
        x = petiole_length + (length - petiole_length) * fraction
        row = []
        center_v = (bottom + top) / 2
        for column, v in enumerate((bottom, center_v, top)):
            if index == 0 and column == 1:
                row.append(1)
                continue
            # Small longitudinal bend + transverse camber; not a flat card.
            z = length * (.035 * math.sin(math.pi * fraction) - .025 * fraction * fraction)
            if column != 1:
                z -= length * .025 * math.sin(math.pi * fraction)
            row.append(len(vertices))
            vertices.append((x, (v - base_v) * width_scale, z))
            vertex_uv.append((u, v))
        rows.append(row)
    for first, second in zip(rows, rows[1:]):
        for column in range(2):
            faces.append((first[column], second[column], second[column + 1], first[column + 1]))
            materials.append(0)
    mesh = bpy.data.meshes.new('Citrus_Leaf_With_Petiole')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv = mesh.uv_layers.new(name='Leaf_UV')
    for polygon, material_index in zip(mesh.polygons, materials):
        polygon.material_index = material_index
        polygon.use_smooth = True
        for loop in polygon.loop_indices:
            uv.data[loop].uv = vertex_uv[mesh.loops[loop].vertex_index]
    material = bpy.data.materials.new('Citrus_Leaf_Opaque_Contour')
    material.use_nodes = True
    material.pass_index = 2
    material.diffuse_color = (.16, .32, .055, 1)
    material.use_backface_culling = False
    surface = material.node_tree.nodes.get('Principled BSDF')
    surface.inputs['Roughness'].default_value = .43
    surface.inputs['Alpha'].default_value = 1
    source = material.node_tree.nodes.new('ShaderNodeTexImage')
    source.image = image
    material.node_tree.links.new(source.outputs['Color'], surface.inputs['Base Color'])
    petiole, _ = diffuse_material('Citrus_Leaf_Petiole', (.18, .27, .045), .6)
    petiole.pass_index = 2
    mesh.materials.append(material)
    mesh.materials.append(petiole)
    mesh['petiole_base_vertex'] = 0
    mesh['blade_base_vertex'] = 1
    mesh['petiole_length_m'] = petiole_length
    mesh['shape_basis'] = '24-section original alpha contour; shallow camber; integrated six-sided petiole'
    return mesh


class SpacingGrid:
    def __init__(self, minimum):
        self.minimum = minimum
        self.cells = defaultdict(list)

    def cell(self, point):
        return tuple(math.floor(value / self.minimum) for value in point)

    def available(self, point):
        x, y, z = self.cell(point)
        return all((point - previous).length >= self.minimum
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                   for previous in self.cells.get((x + dx, y + dy, z + dz), ()))

    def add(self, point):
        self.cells[self.cell(point)].append(point.copy())


class FruitClearance:
    """Conservative visual placement rule, not exported physics geometry.

    Fruit spheres enclose ACTUAL transformed fruit vertices, including stems.
    Test complete leaf triangles (petiole included), not only leaf origins or
    vertices: a triangle can cross a fruit even if its corners lie outside.
    """
    def __init__(self, fruits, clearance):
        self.clearance = clearance
        self.fruits = []
        self.cache = {}
        for obj in fruits:
            points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
            center = Vector(tuple((min(p[i] for p in points) + max(p[i] for p in points)) / 2
                                  for i in range(3)))
            radius = max((point - center).length for point in points)
            self.fruits.append((obj.name, center, radius))

    def conflicts(self, mesh, matrix):
        key = mesh.as_pointer()
        if key not in self.cache:
            points = [vertex.co.copy() for vertex in mesh.vertices]
            center = Vector(tuple((min(p[i] for p in points) + max(p[i] for p in points)) / 2
                                  for i in range(3)))
            radius = max((point - center).length for point in points)
            mesh.calc_loop_triangles()
            self.cache[key] = points, center, radius, [tuple(t.vertices) for t in mesh.loop_triangles]
        points, center, radius, triangles = self.cache[key]
        center_world = matrix @ center
        # Frobenius norm would be conservative but loose. The pipeline uses
        # uniform scale; largest singular value also supports edited leaves.
        linear = matrix.to_3x3()
        import numpy as np
        maximum_scale = float(np.linalg.svd(np.asarray(linear), compute_uv=False)[0])
        near = [(name, origin, size + self.clearance) for name, origin, size in self.fruits
                if (origin - center_world).length <= size + self.clearance + radius * maximum_scale]
        if not near:
            return []
        world = [matrix @ point for point in points]
        conflicts = []
        for name, origin, size in near:
            if any((closest_point_on_tri(origin, world[a], world[b], world[c]) - origin).length < size - 1e-7
                   for a, b, c in triangles):
                conflicts.append(name)
        return conflicts


def verify_leaf_fruit_clearance(leaves, fruits, clearance):
    update_scene()
    checker = FruitClearance(fruits, clearance)
    issues = [{'leaf': obj.name, 'fruits': hits} for obj in leaves
              if (hits := checker.conflicts(obj.data, obj.matrix_world))]
    if issues:
        raise RuntimeError('Leaf intersects actual-fruit enclosing sphere plus clearance: ' + str(issues[:3]))
    return {'checked_leaves': len(leaves), 'checked_fruits': len(fruits),
            'clearance_m': clearance, 'conflicting_leaves': len(issues),
            'method': 'complete leaf triangles vs actual-fruit enclosing spheres, expanded by clearance',
            'scope': 'conservative geometry separation, not camera-view visibility; no physics objects created'}


def place_leaf(branch, rng, wood):
    tangent = branch['tangent']
    reference = Vector((0, 0, 1)) if abs(tangent.z) < .85 else Vector((0, 1, 0))
    side = tangent.cross(reference).normalized()
    other = tangent.cross(side).normalized()
    # Alternating/spiral design approximation along each shoot, not a measured
    # cultivar-specific phyllotaxis rule. Jitter prevents exact cloned whorls.
    slot = int(branch['fraction'] * branch['length'] / .025)
    angle = branch['edge_id'] * 2.39996323 + slot * math.pi + rng.uniform(-.3, .3)
    radial = side * math.cos(angle) + other * math.sin(angle)
    direction = (radial + tangent * .3 + Vector((0, 0, rng.uniform(-.25, .25)))).normalized()
    reach = max(.02, branch['radius'] * 4 + .006)
    outside = branch['point'] + direction * reach
    surface, normal, face, distance = wood.ray_cast(outside, -direction, reach * 2)
    if surface is None or (surface - branch['point']).length > reach * .85 or normal.dot(direction) < .15:
        return None
    # Embed only the petiole base in bark. The entire leaf then points outwards.
    base = surface - direction * .0005
    up = Vector((0, 0, 1))
    normal_leaf = (up - direction * up.dot(direction)).normalized()
    if normal_leaf.length < .5:
        normal_leaf = side
    normal_leaf = Quaternion(direction, rng.uniform(-.55, .55)) @ normal_leaf
    y_axis = normal_leaf.cross(direction).normalized()
    rotation = Matrix((direction, y_axis, direction.cross(y_axis))).transposed().to_euler()
    return base, rotation


def verify_leaf_connections(objects, root, tolerance=.0015):
    """Check saved petiole geometry against current evaluated wood geometry.

    Does not certify every blade/wood or blade/blade intersection.
    """
    update_scene()
    leaves = [obj for obj in objects if obj.get('leaf_attachment_method') == 'petiole_on_wood_surface_v1']
    wood = wood_surface_bvh(root)
    maximum = 0.
    for obj in leaves:
        mesh = obj.data
        if 'petiole_base_vertex' not in mesh or 'blade_base_vertex' not in mesh:
            raise RuntimeError('Missing actual leaf/petiole geometry: ' + obj.name)
        base = obj.matrix_world @ mesh.vertices[int(mesh['petiole_base_vertex'])].co
        blade = obj.matrix_world @ mesh.vertices[int(mesh['blade_base_vertex'])].co
        nearest, normal, face, distance = wood.find_nearest(base)
        if nearest is None or distance > tolerance:
            raise RuntimeError('Leaf petiole detached from actual wood: ' + obj.name)
        delta = blade - base
        hit, normal, face, distance_along = wood.ray_cast(blade, -delta.normalized(), delta.length + tolerance)
        if hit is None or not .001 <= delta.length <= .03:
            raise RuntimeError('Leaf petiole does not meet wood or has invalid length: ' + obj.name)
        maximum = max(maximum, distance)
    return {'checked_leaves': len(leaves), 'maximum_petiole_base_surface_distance_m': maximum,
            'surface_distance_tolerance_m': tolerance,
            'scope': 'actual petiole base and petiole-to-wood contact; not all mesh intersections'}
