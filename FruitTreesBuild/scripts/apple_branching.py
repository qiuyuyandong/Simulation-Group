"""Apple-only branch shaping: upward growth, wide forks and collar supports.

The upstream Space Colonization tree is kept. This module only repositions the
generated centerline and adds short support struts; it never changes topology
or the fruit/leaf attachment profiles.
"""
import math

from mathutils import Quaternion, Vector


def _horizontal_length(point, origin):
    return math.hypot(point.x - origin.x, point.y - origin.y)


def build_topology(points, parent):
    children = [[] for _ in points]
    for node, ancestor in parent.items():
        if ancestor is not None:
            children[ancestor].append(node)
    root = next(index for index, ancestor in parent.items() if ancestor is None)
    order = [root]
    for node in order:
        order.extend(children[node])
    descendants = {node: [node] for node in range(len(points))}
    for node in reversed(order[1:]):
        descendants[parent[node]].extend(descendants[node])
    return children, root, order, descendants


def _incoming(points, parent, node):
    """Direction in which the parent was already growing."""
    ancestor = parent[node]
    if ancestor is None:
        return Vector((0.0, 0.0, 1.0))
    grandparent = parent[ancestor]
    if grandparent is None:
        return Vector((0.0, 0.0, 1.0))
    direction = points[ancestor] - points[grandparent]
    return direction.normalized() if direction.length > 1e-9 else Vector((0.0, 0.0, 1.0))


def _rotate_subtree(points, descendants, node, pivot, axis, angle):
    if abs(angle) < 1e-9:
        return
    if axis.length < 1e-9:
        axis = Vector((0.0, 1.0, 0.0))
    rotation = Quaternion(axis.normalized(), angle)
    for index in descendants[node]:
        points[index] = pivot + rotation @ (points[index] - pivot)


def _fit_height(points, root, trunk_height, crown_height):
    top = max(point.z for point in points)
    current = top - trunk_height
    if current <= 1e-9:
        return 1.0
    scale = crown_height / current
    if abs(scale - 1.0) > 1e-9:
        for node in range(len(points)):
            points[node].z = trunk_height + (points[node].z - trunk_height) * scale
    return scale


def reshape_crown(points, parent, root, args, trunk_height, tree_height):
    """Bend the SCA crown upward and widen its branch angles.

    ``points`` is the already scaled crown in metres. It is mutated in place
    so the caller's radii/attachment indices stay aligned.
    """
    children, root, order, descendants = build_topology(points, parent)
    crown_height = max(1e-6, tree_height - trunk_height)
    min_opening = math.radians(float(getattr(args, 'branch_angle_min', 120.0)))
    sibling_min = math.radians(35.0)
    # Keep apex children first: the first child continues the parent shoot.
    for node in order:
        kids = children[node]
        if len(kids) <= 1:
            continue
        incoming = (points[node] - points[parent[node]]).normalized() if parent[node] is not None else Vector((0.0, 0.0, 1.0))
        apex = max(kids, key=lambda kid: (points[kid] - points[node]).normalized().dot(incoming))
        children[node] = [apex] + [kid for kid in kids if kid != apex]

    # A parabolic lift: outer shoots rise more than the central axis. This is
    # applied in metres, before the final height fit, so it does not collapse
    # the crown into a vertical pole.
    max_radius = max((_horizontal_length(points[node], points[root]) for node in order), default=0.0)
    if max_radius > 1e-9:
        for node in order:
            if node == root:
                continue
            fraction = _horizontal_length(points[node], points[root]) / max_radius
            points[node].z += float(getattr(args, 'branch_uplift', 0.18)) * crown_height * fraction ** 1.6
    _fit_height(points, root, trunk_height, crown_height)
    # Round the upper silhouette: a flat-topped fan reads as a hedge, while a
    # gradual inward taper reads as a crown. Lower and middle shoots keep their
    # spread; only the top 45% of the radius is pulled in.
    for node in order:
        if node == root:
            continue
        height_fraction = max(0.0, min(1.0, (points[node].z - trunk_height) / crown_height))
        horizontal_factor = 1.0 - 0.28 * height_fraction ** 2.0
        points[node].x = points[root].x + (points[node].x - points[root].x) * horizontal_factor
        points[node].y = points[root].y + (points[node].y - points[root].y) * horizontal_factor
    _fit_height(points, root, trunk_height, crown_height)
    # An explicit crownWidth is a contract, not an initial guess: undo the
    # rounding taper's width loss before the final angle pass.
    explicit_width = getattr(args, 'crown_width', None)
    if explicit_width is not None:
        width = max(max(point[i] for point in points) - min(point[i] for point in points)
                    for i in (0, 1))
        if width > 1e-9:
            factor = float(explicit_width) / width
            for node in order:
                if node == root:
                    continue
                points[node].x = points[root].x + (points[node].x - points[root].x) * factor
                points[node].y = points[root].y + (points[node].y - points[root].y) * factor

    def enforce():
        minimum_elevation = math.radians(5.0)
        for node in order:
            if node == root:
                continue
            pivot = points[parent[node]].copy()
            incoming = _incoming(points, parent, node)
            direction = (points[node] - pivot).normalized()
            opening = direction.angle(-incoming)
            if opening < min_opening:
                axis = direction.cross(incoming)
                _rotate_subtree(points, descendants, node, pivot, axis, min_opening - opening)
            direction = (points[node] - pivot).normalized()
            elevation = math.asin(max(-1.0, min(1.0, direction.z)))
            if elevation < minimum_elevation:
                horizontal = Vector((direction.x, direction.y, 0.0))
                if horizontal.length > 1e-8:
                    axis = horizontal.normalized().cross(Vector((0.0, 0.0, 1.0)))
                    _rotate_subtree(points, descendants, node, pivot, axis,
                                    minimum_elevation - elevation)
            # Separate from earlier siblings; apex children come first.
            for sibling in children[parent[node]]:
                if sibling == node:
                    break
                sibling_direction = (points[sibling] - pivot).normalized()
                direction = (points[node] - pivot).normalized()
                angle = direction.angle(sibling_direction)
                if angle < sibling_min:
                    axis = sibling_direction.cross(direction)
                    if axis.length < 1e-8:
                        axis = incoming.cross(sibling_direction)
                    _rotate_subtree(points, descendants, node, pivot, axis, sibling_min - angle)
            # Re-check both constraints after the sibling separation.
            for _ in range(3):
                direction = (points[node] - pivot).normalized()
                opening = direction.angle(-incoming)
                elevation = math.asin(max(-1.0, min(1.0, direction.z)))
                if opening >= min_opening and elevation >= minimum_elevation:
                    break
                if opening < min_opening:
                    axis = direction.cross(incoming)
                    _rotate_subtree(points, descendants, node, pivot, axis, min_opening - opening)
                    direction = (points[node] - pivot).normalized()
                elevation = math.asin(max(-1.0, min(1.0, direction.z)))
                if elevation < minimum_elevation:
                    horizontal = Vector((direction.x, direction.y, 0.0))
                    if horizontal.length > 1e-8:
                        axis = horizontal.normalized().cross(Vector((0.0, 0.0, 1.0)))
                        _rotate_subtree(points, descendants, node, pivot, axis,
                                        minimum_elevation - elevation)

    for _ in range(2):
        enforce()
        _fit_height(points, root, trunk_height, crown_height)
    enforce()

    return crown_statistics(points, parent, root, trunk_height, tree_height, children,
                            float(getattr(args, 'branch_angle_min', 120.0)))


def crown_statistics(points, parent, root, trunk_height, tree_height, children=None, target_angle=120.0):
    if children is None:
        children, root, order, descendants = build_topology(points, parent)
    else:
        order = [root]
        for node in order:
            order.extend(children[node])
    openings = []
    lateral_openings = []
    elevations = []
    sibling_angles = []
    apex = {}
    for node, kids in enumerate(children):
        if not kids:
            continue
        incoming = (points[node] - points[parent[node]]).normalized() if parent[node] is not None else Vector((0.0, 0.0, 1.0))
        apex[node] = max(kids, key=lambda kid: (points[kid] - points[node]).normalized().dot(incoming))
    for node in order:
        if node == root:
            continue
        direction = (points[node] - points[parent[node]]).normalized()
        elevations.append(math.degrees(math.asin(max(-1.0, min(1.0, direction.z)))))
        opening = math.degrees(direction.angle(-_incoming(points, parent, node)))
        openings.append(opening)
        if node != apex.get(parent[node]):
            lateral_openings.append(opening)
        for sibling in children[parent[node]]:
            if sibling == node:
                break
            sibling_angles.append(math.degrees(direction.angle((points[sibling] - points[parent[node]]).normalized())))
    width = max(max(point[i] for point in points) - min(point[i] for point in points) for i in (0, 1))
    height = max(point.z for point in points) - trunk_height
    return {
        'branch_opening_angle_min_deg': round(min(openings), 3) if openings else None,
        'branch_opening_angle_mean_deg': round(sum(openings) / len(openings), 3) if openings else None,
        'lateral_branch_opening_angle_min_deg': round(min(lateral_openings), 3) if lateral_openings else None,
        'branch_opening_below_target_count': sum(value < target_angle - 0.05 for value in lateral_openings),
        'branch_elevation_mean_deg': round(sum(elevations) / len(elevations), 3) if elevations else None,
        'branch_elevation_min_deg': round(min(elevations), 3) if elevations else None,
        'branch_below_horizontal_count': sum(value < 0.0 for value in elevations),
        'branch_sibling_angle_min_deg': round(min(sibling_angles), 3) if sibling_angles else None,
        'branch_sibling_angle_mean_deg': round(sum(sibling_angles) / len(sibling_angles), 3) if sibling_angles else None,
        'crown_height_actual_m': round(height, 6),
        'crown_width_actual_m': round(width, 6),
        'branch_angle_target_min_deg': target_angle,
    }


def merge_coincident_nodes(points, parent, loads, root, tolerance=1e-5):
    """Collapse SCA's duplicated child points that share a parent and position.

    Space colonization can grow a second child from an unchanged parent in the
    same direction. The two points then occupy the same position and create a
    zero-angle fork and overlapping skin tubes. Merge only same-parent,
    same-position siblings; repeat because merging two coincident parents can
    expose the same duplication one level deeper.
    """
    total_removed = 0
    for _ in range(24):
        groups = {}
        for node in parent:
            point = points[node]
            key = (parent[node],
                   round(point.x / tolerance),
                   round(point.y / tolerance),
                   round(point.z / tolerance))
            groups.setdefault(key, []).append(node)
        alias = {}
        for group in groups.values():
            if len(group) < 2:
                continue
            representative = min(group)
            for node in group:
                if node != representative:
                    alias[node] = representative
        if not alias:
            break
        removed = set(alias)
        kept = [node for node in range(len(points)) if node not in removed]
        remap = {old: new for new, old in enumerate(kept)}
        new_points = [points[old].copy() for old in kept]
        new_parent = {}
        for old in kept:
            ancestor = parent[old]
            ancestor = alias.get(ancestor, ancestor)
            new_parent[remap[old]] = remap[ancestor] if ancestor is not None else None
        root = remap[alias.get(root, root)]
        points, parent = new_points, new_parent
        total_removed += len(removed)
    new_children = {}
    for node, ancestor in parent.items():
        if ancestor is not None:
            new_children.setdefault(ancestor, []).append(node)
    order = [root]
    for node in order:
        order.extend(new_children.get(node, ()))
    if len(order) != len(parent):
        raise RuntimeError('Coincident-node merge disconnected the apple skeleton.')
    loads = [1] * len(parent)
    for node in reversed(order[1:]):
        loads[parent[node]] += loads[node]
    return points, parent, loads, root, total_removed
