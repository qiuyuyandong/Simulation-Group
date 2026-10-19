"""Optional current-geometry connection checks, independent of core metadata.

Do not copy old branch_anchor_asset/stem_* properties as current landmarks.
Unsupported fruit topology is reported as unassessed, not silently passed.
"""
from mathutils import Vector
from fruit_attachment import calibrate_mesh, wood_surface_bvh


def diagnose(objects, root):
    fruits = [obj for obj in objects if obj.get('asset_role') == 'fruit']
    stems = next((obj for obj in objects if obj.get('asset_role') == 'fruit_stems'), None)
    wood = wood_surface_bvh(root)
    issues, passed, unassessed, used = [], 0, 0, set()
    cache = {}
    for obj in fruits:
        evaluated = None
        try:
            if obj.modifiers:
                import bpy
                evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                mesh = evaluated.to_mesh()
                key = ('evaluated', obj.as_pointer())
            else:
                mesh = obj.data
                key = (mesh.as_pointer(), obj.get('fruit_kind'))
            if key not in cache:
                cache[key] = calibrate_mesh(mesh, obj['fruit_kind'])
            landmarks = cache[key]
            if stems is None or stems.type != 'CURVE':
                raise ValueError('Missing connector curve.')
            index = int(obj['connection_spline_index'])
            if index in used or not 0 <= index < len(stems.data.splines):
                raise ValueError('Missing or duplicate fruit-to-connector index.')
            used.add(index)
            spline = stems.data.splines[index]
            if spline.type != 'POLY' or len(spline.points) != 2:
                raise ValueError('Only the original two-point connector is diagnosed.')
            tip = obj.matrix_world @ landmarks['tip']
            endpoints = [stems.matrix_world @ Vector(point.co[:3]) for point in spline.points]
            endpoints.sort(key=lambda point: (point - tip).length)
            end, anchor = endpoints
            error = (end - tip).length
            if error > 1e-5:
                issues.append({'fruit_id': obj['fruit_id'], 'status': 'failed',
                               'reason': 'Connector no longer meets current geometric stem tip.', 'endpoint_error_m': error})
                continue
            delta = anchor - end
            if delta.length < 1e-6:
                raise ValueError('Zero-length connector.')
            hit, normal, face, distance = wood.ray_cast(end, delta.normalized(), delta.length + 1e-5)
            if hit is None:
                issues.append({'fruit_id': obj['fruit_id'], 'status': 'failed',
                               'reason': 'Current connector does not reach evaluated wood surface.'})
                continue
            passed += 1
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            unassessed += 1
            issues.append({'fruit_id': obj.get('fruit_id'), 'status': 'not_assessed', 'reason': str(exc)})
        finally:
            if evaluated:
                evaluated.to_mesh_clear()
    failures = len(fruits) - passed - unassessed
    return {'status': 'failed' if failures else ('partially_unassessed' if unassessed else 'passed'),
            'fruit_count': len(fruits), 'passed': passed, 'failed': failures, 'not_assessed': unassessed,
            'issues': issues, 'unused_connector_splines': len(stems.data.splines) - len(used) if stems else None,
            'scope': 'Current calibrated fruit tips and actual connector/wood geometry; does not certify all mesh intersections.'}
