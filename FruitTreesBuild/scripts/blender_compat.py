"""Small API bridge; compatible with Blender 2.79's Python 3.5."""
import bpy

LEGACY = bpy.app.version < (2, 80, 0)


def transform(matrix, value):
    return matrix * value if LEGACY else matrix @ value


def update_scene():
    if LEGACY:
        bpy.context.scene.update()
    else:
        bpy.context.view_layer.update()


def link_object(obj):
    if LEGACY:
        bpy.context.scene.objects.link(obj)
    else:
        bpy.context.scene.collection.objects.link(obj)


def asset_container(name):
    if LEGACY:
        return bpy.data.groups.new(name)
    group = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(group)
    return group


def select_only(obj):
    for other in bpy.context.scene.objects:
        if LEGACY:
            other.select = other == obj
        else:
            other.select_set(other == obj)
    if LEGACY:
        bpy.context.scene.objects.active = obj
    else:
        bpy.context.view_layer.objects.active = obj


def diffuse_material(name, color, roughness=0.75):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = tuple(color[:3]) if LEGACY else tuple(color[:3]) + (1,)
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    diffuse = nodes.new('ShaderNodeBsdfDiffuse')
    diffuse.inputs['Color'].default_value = tuple(color[:3]) + (1,)
    diffuse.inputs['Roughness'].default_value = roughness
    material.node_tree.links.new(diffuse.outputs['BSDF'], output.inputs['Surface'])
    return material, diffuse


def evaluated_coordinates(obj):
    """Object-space geometry, not the unevaluated Skin centerline."""
    if obj.type == 'MESH' and not obj.modifiers:
        return [vertex.co.copy() for vertex in obj.data.vertices]
    if LEGACY:
        mesh = obj.to_mesh(bpy.context.scene, True, 'RENDER')
        try:
            return [vertex.co.copy() for vertex in mesh.vertices]
        finally:
            bpy.data.meshes.remove(mesh)
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return [vertex.co.copy() for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def evaluated_surface(obj):
    """Object-space vertices and faces, including Skin/Subsurf, for ray tests."""
    if LEGACY:
        mesh = obj.to_mesh(bpy.context.scene, True, 'RENDER')
        try:
            return ([vertex.co.copy() for vertex in mesh.vertices],
                    [list(face.vertices) for face in mesh.polygons])
        finally:
            bpy.data.meshes.remove(mesh)
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return ([vertex.co.copy() for vertex in mesh.vertices],
                [list(face.vertices) for face in mesh.polygons])
    finally:
        evaluated.to_mesh_clear()
