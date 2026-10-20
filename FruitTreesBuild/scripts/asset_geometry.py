"""Read-only appearance selection and saved-asset structure checks."""
import bpy
from blender_compat import update_scene
from metadata_contract import validate_unit_frame

VISUAL_ROLES = ('tree_wood', 'leaf', 'fruit', 'fruit_stems')
# Compatibility only: old delivered files are never edited by metadata export.
HISTORICAL_NONVISUAL_ROLES = ('collision_proxy',)


def group_objects(group):
    return sorted(group.all_objects, key=lambda obj: obj.name)


def visual_objects(group):
    return [obj for obj in group_objects(group)
            if obj.get('asset_role') not in HISTORICAL_NONVISUAL_ROLES]


def check_visual_structure(group, root):
    update_scene()
    validate_unit_frame([list(row) for row in root.matrix_world])
    objects = visual_objects(group)
    if root not in objects or root.type != 'MESH' or root.get('asset_role') != 'tree_wood':
        raise RuntimeError('Missing mesh wood root.')
    if any(obj.type not in ('MESH', 'CURVE') or obj.get('asset_role') not in VISUAL_ROLES for obj in objects):
        raise RuntimeError('Unexpected visual role/type; preserve supported asset_role properties.')
    if any(obj != root and obj.parent != root for obj in group_objects(group)):
        raise RuntimeError('All asset objects must directly follow the tree root.')
    if any(obj.hide_render or obj.hide_viewport or obj.hide_get() for obj in objects):
        raise RuntimeError('Hidden visual objects are ambiguous; delete excluded parts or unhide them.')
    identifiers = set()
    for obj in objects:
        if obj.constraints or (obj.animation_data and (obj.animation_data.action or obj.animation_data.drivers)):
            raise RuntimeError('Static asset contains animated/constrained object: ' + obj.name)
        for modifier in obj.modifiers:
            if modifier.show_viewport != modifier.show_render:
                raise RuntimeError('Viewport/render modifier mismatch: ' + obj.name)
            if modifier.type == 'SUBSURF' and modifier.levels != modifier.render_levels:
                raise RuntimeError('Viewport/render subdivision mismatch: ' + obj.name)
        if obj.get('asset_role') == 'fruit':
            identity = obj.get('fruit_id')
            if not isinstance(identity, str) or not identity.strip() or identity in identifiers:
                raise RuntimeError('Missing/duplicate fruit_id: ' + obj.name + '. Preserve existing IDs; assign a unique ID to a new copy.')
            identifiers.add(identity)
    return objects


def check_saved_scene(group, root):
    objects = check_visual_structure(group, root)
    if len(bpy.data.scenes) != 1 or bpy.context.scene.camera or bpy.context.scene.world:
        raise RuntimeError('Use the standalone asset.blend, with one scene and no camera/world.')
    if set(bpy.context.scene.objects) != set(group_objects(group)) or set(bpy.data.objects) != set(group_objects(group)):
        raise RuntimeError('Asset contains missing objects, helpers or unused source objects.')
    if bpy.context.scene.unit_settings.system != 'METRIC' or abs(bpy.context.scene.unit_settings.scale_length - 1) > 1e-9:
        raise RuntimeError('Asset scene must use metres with unit scale 1.')
    if any(image.source == 'FILE' and not image.packed_file for image in bpy.data.images):
        raise RuntimeError('Unpacked texture dependency. Pack resources and save the model first.')
    if any(node.bl_idname == 'NodeUndefined' for material in bpy.data.materials
           if material.node_tree for node in material.node_tree.nodes):
        raise RuntimeError('Unresolved material nodes.')
    if any(not obj.data.uv_layers for obj in objects if obj.get('asset_role') in ('leaf', 'fruit')):
        raise RuntimeError('Missing leaf or fruit UVs.')
    return objects
