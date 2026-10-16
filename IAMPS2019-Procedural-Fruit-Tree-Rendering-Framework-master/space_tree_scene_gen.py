import bpy
import random as rd
from pathlib import Path

# Blender's Run Script uses a virtual __file__; the Text datablock holds the disk path.
text = getattr(bpy.context.space_data, 'text', None)
if text is not None and not text.filepath:
    raise RuntimeError("Open this script from disk in the Text Editor before running it.")
script_file = bpy.path.abspath(text.filepath) if text is not None else __file__
BASE_DIR = Path(script_file).resolve().parent
scene = bpy.context.scene
try:
    bpy.ops.mesh.sca_tree.get_rna_type()
except KeyError:
    raise RuntimeError("Enable SCA Tree Generator before running this script.") from None
for asset in (
    'leaf_texture/green_leaves_PNG3668.png', 'leaf_texture/green_leaves_PNG3638.png',
    'leaf_texture/autumn_leaves_PNG3609.webp', 'leaf_texture/autumn_leaves_PNG3581.webp',
    'fruit_model/orange_for_cycles.obj', 'fruit_model/orange_for_cycles.mtl',
    'fruit_model/apple_for_cycles.obj', 'fruit_model/apple_for_cycles.mtl',
    'fruit_model/Apple_Texture_by_AGF81.jpg', 'fruit_model/Color.jpg', 'fruit_model/Normal.jpg',
):
    if not (BASE_DIR / asset).is_file():
        raise FileNotFoundError(BASE_DIR / asset)

###################################################################################
#Parameter to set the type of tree: 'a' for an apple tree or 'o' for an orange tree
###################################################################################
fruit_type = 'a'

############################
#Chooses the cycles renderer
############################
scene.render.engine = 'CYCLES'

############################################################################################
# removing all the objects (the default cube, lamp and camera) already existing in the scene
############################################################################################
if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
for obj in bpy.context.view_layer.objects:
    obj.hide_set(False)
    obj.select_set(True)
bpy.ops.object.delete(use_global=False)

######################################
### architecture of generated tree ###
######################################

#################################################################################
#Create a dummy tree and delete it, so that the bark textures are properly loaded.
#################################################################################
bpy.ops.mesh.sca_tree(updateTree=True,
randomSeed=0,
maxIterations=100,
numberOfEndpoints=1000,
killDistance=1,
apicalcontrol=1,
apicalcontrolfalloff=15,
apicalcontroltiming=14,
newEndPointsPer1000=3,
addLeaves=True,
crownSize=5,
crownShape=1.25,
crownOffset=0.75,
noModifiers=False,
subSurface=True,
scale=0.02)

if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
for obj in bpy.context.view_layer.objects:
    obj.hide_set(False)
    obj.select_set(True)
bpy.ops.object.delete(use_global=False)

#########################
#Creating the actual tree
#########################
bpy.ops.mesh.sca_tree(updateTree=True,
randomSeed=0,
maxIterations=100,
numberOfEndpoints=1000,
killDistance=1,
apicalcontrol=1,
apicalcontrolfalloff=15,
apicalcontroltiming=14,
newEndPointsPer1000=3,
addLeaves=True,
crownSize=5,
crownShape=1.25,
crownOffset=0.75,
noModifiers=False,
subSurface=True,
scale=0.02,
barkMaterial='BarkBetter1.1')

tree = bpy.context.object
tree.name = 'Tree'

##########################################################
#importing the images of leaves as planes on the 2nd layer
##########################################################

#######################################
#enables 'import image as plane' add-on
#######################################

######################################################
#import the leaf images as planes on the 2nd layer,
#and scale them
######################################################
bpy.ops.image.import_as_mesh_planes(shader='SHADELESS', directory=str(BASE_DIR / 'leaf_texture'), files=[{'name': 'green_leaves_PNG3668.png'}], relative=False)

bpy.ops.image.import_as_mesh_planes(shader='SHADELESS', directory=str(BASE_DIR / 'leaf_texture'), files=[{'name': 'green_leaves_PNG3638.png'}], relative=False)

bpy.ops.image.import_as_mesh_planes(shader='SHADELESS', directory=str(BASE_DIR / 'leaf_texture'), files=[{'name': 'autumn_leaves_PNG3609.webp'}], relative=False)

bpy.ops.image.import_as_mesh_planes(shader='SHADELESS', directory=str(BASE_DIR / 'leaf_texture'), files=[{'name': 'autumn_leaves_PNG3581.webp'}], relative=False)

bpy.data.objects['green_leaves_PNG3638'].location[0] = 2
bpy.data.objects['autumn_leaves_PNG3609'].location[0] = 4
bpy.data.objects['autumn_leaves_PNG3581'].location[0] = 6


bpy.data.objects['autumn_leaves_PNG3609'].rotation_euler[2] = -3.14159265/2
bpy.data.objects['autumn_leaves_PNG3609'].dimensions = [0.50775,0.79030,0.00320]

bpy.data.objects['autumn_leaves_PNG3581'].rotation_euler[2] = -3.14159265/2
bpy.data.objects['autumn_leaves_PNG3581'].dimensions = [0.92812,0.34389,0.01836]

bpy.data.objects['green_leaves_PNG3638'].dimensions[0] = 0.45702
bpy.data.objects['green_leaves_PNG3638'].dimensions[1] = 1.01056
bpy.data.objects['green_leaves_PNG3638'].dimensions[2] = 0.01250

bpy.data.objects['green_leaves_PNG3668'].dimensions[0] = 0.39461
bpy.data.objects['green_leaves_PNG3668'].dimensions[1] = 1.00073
bpy.data.objects['green_leaves_PNG3668'].dimensions[2] = 0.00200

##################################
#create a group of the four leaves
##################################
grp = bpy.data.collections.new('Leaves')
scene.collection.children.link(grp)
objects_to_add = ['autumn_leaves_PNG3609','autumn_leaves_PNG3581',
'green_leaves_PNG3638','green_leaves_PNG3668']
for name in objects_to_add:
    obj = bpy.data.objects[name]
    grp.objects.link(obj)
    for collection in list(obj.users_collection):
        if collection != grp:
            collection.objects.unlink(obj)
    obj.hide_render = True
    obj.hide_set(True)

####################################
#add leaves as particles to the tree
####################################
tree = bpy.data.objects['Tree']

##################################################################
#add 4 different types of leaves as 4 particle systems to the tree
##################################################################
#add leaves as particles to the tree

tree = bpy.data.objects['Tree']
leaves_particle_system = tree.modifiers.new("Leaves1", type="PARTICLE_SYSTEM").particle_system
leaves_particle_system.seed = 54
leaves_settings = leaves_particle_system.settings
leaves_settings.type = 'HAIR'
leaves_settings.use_advanced_hair = True
leaves_settings.hair_step = 5
leaves_settings.count = 250
leaves_settings.hair_length = 4
leaves_settings.emit_from = 'FACE'
leaves_settings.use_emit_random = True
leaves_settings.use_even_distribution = True
leaves_settings.distribution = 'RAND'
leaves_settings.userjit = 0
leaves_settings.jitter_factor = 1
leaves_settings.use_modifier_stack = True
leaves_settings.render_type = 'OBJECT'
leaves_settings.instance_object = bpy.data.objects['autumn_leaves_PNG3581']
leaves_settings.use_scale_instance = False
leaves_settings.particle_size = 0.250
leaves_settings.size_random = 1
leaves_settings.use_collection_count = True
leaves_settings.active_instanceweight_index = 0

tree = bpy.data.objects['Tree']
leaves_particle_system = tree.modifiers.new("Leaves2", type="PARTICLE_SYSTEM").particle_system
leaves_particle_system.seed = 54
leaves_settings = leaves_particle_system.settings
leaves_settings.type = 'HAIR'
leaves_settings.use_advanced_hair = True
leaves_settings.hair_step = 5
leaves_settings.count = 1500
leaves_settings.hair_length = 4
leaves_settings.emit_from = 'FACE'
leaves_settings.use_emit_random = True
leaves_settings.use_even_distribution = True
leaves_settings.distribution = 'RAND'
leaves_settings.userjit = 0
leaves_settings.jitter_factor = 1
leaves_settings.use_modifier_stack = True
leaves_settings.render_type = 'OBJECT'
leaves_settings.instance_object = bpy.data.objects['autumn_leaves_PNG3609']
leaves_settings.use_scale_instance = False
leaves_settings.particle_size = 0.250
leaves_settings.size_random = 1
leaves_settings.use_collection_count = True
leaves_settings.active_instanceweight_index = 0

tree = bpy.data.objects['Tree']
leaves_particle_system = tree.modifiers.new("Leaves3", type="PARTICLE_SYSTEM").particle_system
leaves_particle_system.seed = 54
leaves_settings = leaves_particle_system.settings
leaves_settings.type = 'HAIR'
leaves_settings.use_advanced_hair = True
leaves_settings.hair_step = 5
leaves_settings.count = 2000
leaves_settings.hair_length = 4
leaves_settings.emit_from = 'FACE'
leaves_settings.use_emit_random = True
leaves_settings.use_even_distribution = True
leaves_settings.distribution = 'RAND'
leaves_settings.userjit = 0
leaves_settings.jitter_factor = 1
leaves_settings.use_modifier_stack = True
leaves_settings.render_type = 'OBJECT'
leaves_settings.instance_object = bpy.data.objects['green_leaves_PNG3638']
leaves_settings.use_scale_instance = False
leaves_settings.particle_size = 0.250
leaves_settings.size_random = 1
leaves_settings.use_collection_count = True
leaves_settings.active_instanceweight_index = 0

tree = bpy.data.objects['Tree']
leaves_particle_system = tree.modifiers.new("Leaves4", type="PARTICLE_SYSTEM").particle_system
leaves_particle_system.seed = 54
leaves_settings = leaves_particle_system.settings
leaves_settings.type = 'HAIR'
leaves_settings.use_advanced_hair = True
leaves_settings.hair_step = 5
leaves_settings.count = 2000
leaves_settings.hair_length = 4
leaves_settings.emit_from = 'FACE'
leaves_settings.use_emit_random = True
leaves_settings.use_even_distribution = True
leaves_settings.distribution = 'RAND'
leaves_settings.userjit = 0
leaves_settings.jitter_factor = 1
leaves_settings.use_modifier_stack = True
leaves_settings.render_type = 'OBJECT'
leaves_settings.instance_object = bpy.data.objects['green_leaves_PNG3668']
leaves_settings.use_scale_instance = False
leaves_settings.particle_size = 0.250
leaves_settings.size_random = 1
leaves_settings.use_collection_count = True
leaves_settings.active_instanceweight_index = 0

#############################
#add orange object on layer 3
#############################
bpy.ops.wm.obj_import(filepath=str(BASE_DIR / "fruit_model/orange_for_cycles.obj"))
bpy.context.object.hide_render = True
bpy.context.object.hide_set(True)

######################################################################################
#adding the displace modifiers to the orange to give it random variations in structure
######################################################################################
tex = bpy.data.textures.new("CLOUDS",type='CLOUDS')
ob = bpy.data.objects['Orange']
mod = ob.modifiers.new(name="TEXMOD", type="DISPLACE")
mod.texture = tex
bpy.data.objects['Orange'].modifiers['TEXMOD'].strength = 0.2

tex = bpy.data.textures.new("CLOUDS",type='CLOUDS')
mod = ob.modifiers.new(name="TEXMODG", type="DISPLACE")
mod.texture = tex
bpy.data.objects['Orange'].modifiers['TEXMODG'].strength = 0.03
bpy.data.objects['Orange'].modifiers['TEXMODG'].texture_coords = 'GLOBAL'

###########################################################
# to avoid seing the original orange in the rendered images
###########################################################

###############################
#adding apple object on layer 4
###############################
bpy.ops.wm.obj_import(filepath=str(BASE_DIR / "fruit_model/apple_for_cycles.obj"))

bpy.context.object.name = 'Apple'
bpy.context.object.hide_render = True
bpy.context.object.hide_set(True)

##########################################################
# to avoid seing the original apple in the rendered images
##########################################################

#####################################################################################
#adding the displace modifiers to the apple to give it random variations in structure
#####################################################################################
tex = bpy.data.textures.new("CLOUDS",type='CLOUDS')
ob = bpy.data.objects['Apple']
mod = ob.modifiers.new(name="TEXMOD", type="DISPLACE")
mod.texture = tex
bpy.data.objects['Apple'].modifiers['TEXMOD'].strength = 0.2

tex = bpy.data.textures.new("CLOUDS",type='CLOUDS')
mod = ob.modifiers.new(name="TEXMODG", type="DISPLACE")
mod.texture = tex
bpy.data.objects['Apple'].modifiers['TEXMODG'].strength = 0.03
bpy.data.objects['Apple'].modifiers['TEXMODG'].texture_coords = 'GLOBAL'

########################################
#adding oranges as particles on the tree
########################################
orange = bpy.data.objects['Orange']
oranges_particle_system = tree.modifiers.new("Oranges", type="PARTICLE_SYSTEM").particle_system
oranges_particle_system.seed = 0
oranges_settings = oranges_particle_system.settings
oranges_settings.type = 'HAIR'
oranges_settings.use_advanced_hair = True
oranges_settings.hair_step = 5
oranges_settings.count = 100
oranges_settings.hair_length = 4
oranges_settings.emit_from = 'VERT'
oranges_settings.use_emit_random = True
oranges_settings.use_even_distribution = True
oranges_settings.distribution = 'RAND'
oranges_settings.userjit = 0
oranges_settings.jitter_factor = 1
oranges_settings.use_modifier_stack = False
oranges_settings.render_type = 'OBJECT'
oranges_settings.instance_object = bpy.data.objects['Orange']
oranges_settings.use_scale_instance = False
oranges_settings.particle_size = 0.120
oranges_settings.size_random = 0.364

#######################################
#adding apples as particles on the tree
#######################################
apple = bpy.data.objects['Apple']
apples_particle_system = tree.modifiers.new("Apples", type="PARTICLE_SYSTEM").particle_system
apples_particle_system.seed = 0
apples_settings = apples_particle_system.settings
apples_settings.type = 'HAIR'
apples_settings.use_advanced_hair = True
apples_settings.hair_step = 5
apples_settings.count = 100
apples_settings.hair_length = 4
apples_settings.emit_from = 'VERT'
apples_settings.use_emit_random = True
apples_settings.use_even_distribution = True
apples_settings.distribution = 'RAND'
apples_settings.userjit = 0
apples_settings.jitter_factor = 1
apples_settings.use_modifier_stack = False
apples_settings.render_type = 'OBJECT'
apples_settings.instance_object = bpy.data.objects['Apple']
apples_settings.use_scale_instance = False
apples_settings.particle_size = 0.070
apples_settings.size_random = 0.364



########################################
#adding softbody modifiers to the leaves
########################################
objects = ['autumn_leaves_PNG3581','autumn_leaves_PNG3609',
'green_leaves_PNG3638','green_leaves_PNG3668']

for object in objects:
    ob = bpy.data.objects[object]
    mod = ob.modifiers.new(name="SB", type="SOFT_BODY")

################################
#Setting up nodes for the leaves
################################
for object in objects:
    leaf = bpy.data.objects[object]
    leaf_material = leaf.active_material
    leaf_material.use_nodes = True
    leaf_nodes = leaf_material.node_tree.nodes

    ##########################
    #delete all existing nodes
    ##########################
    leaf_nodes.clear()

    node = leaf_nodes.new("ShaderNodeTexImage")
    node.name = "Image Texture"
    if object[0] == 'a':
        leaf_texture_image = bpy.data.images.load(str(BASE_DIR / "leaf_texture" / (object + ".webp")))
    else:
        leaf_texture_image = bpy.data.images.load(str(BASE_DIR / "leaf_texture" / (object + ".png")))

    leaf_material.node_tree.nodes["Image Texture"].image = leaf_texture_image

    node = leaf_nodes.new("ShaderNodeHueSaturation")
    node.name = "HSV"
    leaf_material.node_tree.nodes["HSV"].inputs[0].default_value = 0.5
    leaf_material.node_tree.nodes['HSV'].inputs[1].default_value = 0
    leaf_material.node_tree.nodes['HSV'].inputs[2].default_value = 1
    leaf_material.node_tree.nodes['HSV'].inputs[3].default_value = 1

    node = leaf_nodes.new("ShaderNodeBrightContrast")
    node.name = "Bright Contrast"

    leaf_material.node_tree.nodes['Bright Contrast'].inputs[1].default_value = -3.3
    leaf_material.node_tree.nodes['Bright Contrast'].inputs[2].default_value = 14

    node = leaf_nodes.new("ShaderNodeMath")
    node.name = "Math Multiply"
    leaf_material.node_tree.nodes['Math Multiply'].operation = 'MULTIPLY'

    node = leaf_nodes.new("ShaderNodeValToRGB")
    node.name = "Color Ramp"

    leaf_material.node_tree.nodes['Color Ramp'].color_ramp.elements[0].position = 0
    leaf_material.node_tree.nodes['Color Ramp'].color_ramp.elements[0].color[0] = 0.002
    leaf_material.node_tree.nodes['Color Ramp'].color_ramp.elements[0].color[1] = 0.099
    leaf_material.node_tree.nodes['Color Ramp'].color_ramp.elements[0].color[2] = 0.000

    leaf_material.node_tree.nodes['Color Ramp'].color_ramp.elements[1].position = 1
    leaf_material.node_tree.nodes['Color Ramp'].color_ramp.elements[1].color[0] = 0.123
    leaf_material.node_tree.nodes['Color Ramp'].color_ramp.elements[1].color[1] = 0.083
    leaf_material.node_tree.nodes['Color Ramp'].color_ramp.elements[1].color[2] = 0.009

    node = leaf_nodes.new("ShaderNodeBump")
    node.name = "Bump"

    leaf_material.node_tree.nodes['Bump'].inputs[0].default_value = 1
    leaf_material.node_tree.nodes['Bump'].inputs[1].default_value = 0.1

    node = leaf_nodes.new("ShaderNodeBsdfGlossy")
    node.name = "Glossy BSDF"

    leaf_material.node_tree.nodes['Glossy BSDF'].distribution = 'GGX'
    leaf_material.node_tree.nodes['Glossy BSDF'].inputs[0].default_value[0] = 0.8
    leaf_material.node_tree.nodes['Glossy BSDF'].inputs[0].default_value[1] = 0.8
    leaf_material.node_tree.nodes['Glossy BSDF'].inputs[0].default_value[2] = 0.8
    leaf_material.node_tree.nodes['Glossy BSDF'].inputs[1].default_value = 0.333

    node = leaf_nodes.new("ShaderNodeBsdfDiffuse")
    node.name = "Diffuse BSDF"
    leaf_material.node_tree.nodes['Diffuse BSDF'].inputs[1].default_value = 0.950

    node = leaf_nodes.new("ShaderNodeBsdfTransparent")
    node.name = "Transparent BSDF"
    leaf_material.node_tree.nodes['Transparent BSDF'].inputs[0].default_value[0] = 1
    leaf_material.node_tree.nodes['Transparent BSDF'].inputs[0].default_value[1] = 1
    leaf_material.node_tree.nodes['Transparent BSDF'].inputs[0].default_value[2] = 1

    node = leaf_nodes.new("ShaderNodeBsdfTranslucent")
    node.name = "Translucent BSDF"

    node = leaf_nodes.new("ShaderNodeMixShader")
    node.name = "Mix Shader"

    leaf_material.node_tree.nodes['Mix Shader'].inputs[0].default_value = 0.082

    node = leaf_nodes.new("ShaderNodeAddShader")
    node.name = "Add Shader"

    node = leaf_nodes.new("ShaderNodeMixShader")
    node.name = "Mix Shader1"

    node = leaf_nodes.new("ShaderNodeOutputMaterial")
    node.name = "Material Output"

    #############################
    #Connecting the created nodes
    #############################
    output = leaf_nodes['Image Texture'].outputs['Color']
    input = leaf_nodes['HSV'].inputs['Color']
    leaf_material.node_tree.links.new(output, input)

    input = leaf_nodes['Bump'].inputs['Height']
    leaf_material.node_tree.links.new(output,input)

    input = leaf_nodes['Translucent BSDF'].inputs['Color']
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['HSV'].outputs['Color']
    input = leaf_nodes['Bright Contrast'].inputs['Color']
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Bright Contrast'].outputs[0]
    input = leaf_nodes['Math Multiply'].inputs[0]
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Mix Shader1'].outputs['Shader']
    input = leaf_nodes['Material Output'].inputs['Surface']
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Color Ramp'].outputs['Color']
    input = leaf_nodes['Math Multiply'].inputs[1]
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Math Multiply'].outputs[0]
    input = leaf_nodes['Diffuse BSDF'].inputs['Color']
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Diffuse BSDF'].outputs['BSDF']
    input = leaf_nodes['Mix Shader'].inputs[1]
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Mix Shader'].outputs[0]
    input = leaf_nodes['Add Shader'].inputs[1]
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Add Shader'].outputs['Shader']
    input = leaf_nodes['Mix Shader1'].inputs[2]
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Translucent BSDF'].outputs['BSDF']
    input = leaf_nodes['Add Shader'].inputs[0]
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Bump'].outputs['Normal']
    input = leaf_nodes['Diffuse BSDF'].inputs['Normal']
    leaf_material.node_tree.links.new(output,input)

    input = leaf_nodes['Glossy BSDF'].inputs['Normal']
    leaf_material.node_tree.links.new(output,input)

    input = leaf_nodes['Translucent BSDF'].inputs['Normal']
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Bright Contrast'].outputs[0]
    input = leaf_nodes['Math Multiply'].inputs[0]

    output = leaf_nodes['Image Texture'].outputs['Alpha']
    input = leaf_nodes['Mix Shader1'].inputs[0]
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Glossy BSDF'].outputs['BSDF']
    input = leaf_nodes['Mix Shader'].inputs[2]
    leaf_material.node_tree.links.new(output,input)

    output = leaf_nodes['Transparent BSDF'].outputs['BSDF']
    input = leaf_nodes['Mix Shader1'].inputs[1]
    leaf_material.node_tree.links.new(output,input)

###############################
#setting up nodes for the apple
###############################
apple = bpy.data.objects['Apple']
for apple_material in apple.data.materials:
    apple_material.use_nodes = True
    apple_nodes = apple_material.node_tree.nodes
    apple_nodes.clear()
    shader = apple_nodes.new("ShaderNodeBsdfPrincipled")
    output = apple_nodes.new("ShaderNodeOutputMaterial")
    color = apple_nodes.new("ShaderNodeTexImage")
    color.image = bpy.data.images.load(str(BASE_DIR / 'fruit_model/Apple_Texture_by_AGF81.jpg'))
    normal_image = apple_nodes.new("ShaderNodeTexImage")
    normal_image.image = bpy.data.images.load(str(BASE_DIR / 'fruit_model/Apple_Texture_by_AGF81.jpg'))
    normal_image.image.colorspace_settings.name = 'Non-Color'
    normal = apple_nodes.new("ShaderNodeNormalMap")
    links = apple_material.node_tree.links
    links.new(color.outputs['Color'], shader.inputs['Base Color'])
    links.new(normal_image.outputs['Color'], normal.inputs['Color'])
    links.new(normal.outputs['Normal'], shader.inputs['Normal'])
    links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    if apple_material.name.startswith('lambert2'):
        mapping = apple_nodes.new("ShaderNodeMapping")
        mapping.vector_type = 'TEXTURE'
        mapping.inputs['Rotation'].default_value = (0, 0, 5)
        mapping.inputs['Location'].default_value = (0, 1, 0)
        coordinates = apple_nodes.new("ShaderNodeTexCoord")
        links.new(coordinates.outputs['UV'], mapping.inputs['Vector'])
        links.new(mapping.outputs['Vector'], color.inputs['Vector'])
        links.new(mapping.outputs['Vector'], normal_image.inputs['Vector'])

# The modern OBJ importer does not create the legacy Mix nodes.
orange = bpy.data.objects['Orange']
for orange_material in orange.data.materials:
    orange_material.use_nodes = True
    orange_nodes = orange_material.node_tree.nodes
    orange_nodes.clear()
    shader = orange_nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs['Specular Tint'].default_value = (1, 0.689, 0.155, 1)
    output = orange_nodes.new("ShaderNodeOutputMaterial")
    color = orange_nodes.new("ShaderNodeTexImage")
    color.image = bpy.data.images.load(str(BASE_DIR / 'fruit_model/Color.jpg'), check_existing=True)
    normal_image = orange_nodes.new("ShaderNodeTexImage")
    normal_image.image = bpy.data.images.load(str(BASE_DIR / 'fruit_model/Normal.jpg'), check_existing=True)
    normal_image.image.colorspace_settings.name = 'Non-Color'
    normal = orange_nodes.new("ShaderNodeNormalMap")
    object_info = orange_nodes.new("ShaderNodeObjectInfo")
    ramp = orange_nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.319, 0.125, 0.015, 1)
    middle = ramp.color_ramp.elements.new(0.727)
    middle.color = (0.512, 0.386, 0.017, 1)
    ramp.color_ramp.elements[-1].color = (0.220, 0.314, 0.027, 1)
    mix = orange_nodes.new("ShaderNodeMixRGB")
    mix.inputs[0].default_value = 0.5
    links = orange_material.node_tree.links
    links.new(object_info.outputs['Random'], ramp.inputs['Factor'])
    links.new(ramp.outputs['Color'], mix.inputs[1])
    links.new(color.outputs['Color'], mix.inputs[2])
    links.new(mix.outputs['Color'], shader.inputs['Base Color'])
    links.new(normal_image.outputs['Color'], normal.inputs['Color'])
    links.new(normal.outputs['Normal'], shader.inputs['Normal'])
    links.new(shader.outputs['BSDF'], output.inputs['Surface'])

if fruit_type == 'o':
    apples_settings.count = 0
else:
    oranges_settings.count = 0

####################################
### Setup of ground truth labels ###
####################################

# what kind of supplementary information we want to create the labels
bpy.context.view_layer.use_pass_z = True
bpy.context.view_layer.use_pass_normal = True
bpy.context.view_layer.use_pass_material_index = True

# Setup of the material index for the semantic segmentation label
for material in tree.data.materials:
    material.pass_index = 1
for leaf_name in objects:
    bpy.data.objects[leaf_name].active_material.pass_index = 2
for fruit in (apple, orange):
    for material in fruit.data.materials:
        material.pass_index = 3

##########################################################################
# creation of a scene material
# no need to remove the existing nodes this time, we are going to use them
##########################################################################
compositor = bpy.data.node_groups.new("Tree Labels", "CompositorNodeTree")
scene.compositing_node_group = compositor
scene.render.use_compositing = True
scene_nodes = compositor.nodes
render_layers = scene_nodes.new("CompositorNodeRLayers")
render_layers.layer = bpy.context.view_layer.name
compositor.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
composite_output = scene_nodes.new("NodeGroupOutput")
compositor.links.new(render_layers.outputs['Image'], composite_output.inputs['Image'])

# creation of all needed nodes
node = scene_nodes.new("CompositorNodeNormalize")
node.name = "Normalize Depth"

node = scene_nodes.new("CompositorNodeNormalize")
node.name = "Normalize Normal"

node = scene_nodes.new("CompositorNodeNormalize")
node.name = "Normalize Material Index"

node = scene_nodes.new("ShaderNodeValToRGB")
node.name = "Color Ramp Depth"
# nothing to change for the depth map color ramp

#####################################################################################
# creation of the node used for semantic segmentation labels
# the color_ramp.elements are used to define what color each type of
# object will be. (leaf -> blue, tree -> brown, fruit -> yellow, bakground -> black).
#####################################################################################
node = scene_nodes.new("ShaderNodeValToRGB")
node.name = "Color Ramp Normal"

node.color_ramp.elements.new(0.33)
node.color_ramp.elements[1].color[0] = 0
node.color_ramp.elements[1].color[1] = 0
node.color_ramp.elements[1].color[2] = 1
node.color_ramp.elements[1].color[3] = 1

node.color_ramp.elements.new(0.66)
node.color_ramp.elements[2].color[0] = 1
node.color_ramp.elements[2].color[1] = 0
node.color_ramp.elements[2].color[2] = 0
node.color_ramp.elements[2].color[3] = 1

node = scene_nodes.new("ShaderNodeValToRGB")
node.name = "Color Ramp Material Index"

node.color_ramp.elements[0].color[0] = 0
node.color_ramp.elements[0].color[1] = 0
node.color_ramp.elements[0].color[2] = 0
node.color_ramp.elements[0].color[3] = 1

node.color_ramp.elements.new(0.33)
node.color_ramp.elements[1].color[0] = 0.030
node.color_ramp.elements[1].color[1] = 0.013
node.color_ramp.elements[1].color[2] = 0.002
node.color_ramp.elements[1].color[3] = 1

node.color_ramp.elements.new(0.66)
node.color_ramp.elements[2].color[0] = 0
node.color_ramp.elements[2].color[1] = 0
node.color_ramp.elements[2].color[2] = 1
node.color_ramp.elements[2].color[3] = 1

node.color_ramp.elements[3].position = 0.870
node.color_ramp.elements[3].color[0] = 1
node.color_ramp.elements[3].color[1] = 1
node.color_ramp.elements[3].color[2] = 0
node.color_ramp.elements[3].color[3] = 1

node = scene_nodes.new("CompositorNodeOutputFile")
node.name = "File Output Depth"
node.directory = str(BASE_DIR / "output/depth_map")
node.file_name = 'Image####'
node.file_output_items.new('RGBA', '')
node.format.media_type = 'IMAGE'
node.format.file_format = 'PNG'

node = scene_nodes.new("CompositorNodeOutputFile")
node.name = "File Output Normal"
node.directory = str(BASE_DIR / "output/normal_map")
node.file_name = 'Image####'
node.file_output_items.new('RGBA', '')
node.format.media_type = 'IMAGE'
node.format.file_format = 'PNG'

node = scene_nodes.new("CompositorNodeOutputFile")
node.name = "File Output Material Index"
node.directory = str(BASE_DIR / "output/segmentation_map")
node.file_name = 'Image####'
node.file_output_items.new('RGBA', '')
node.format.media_type = 'IMAGE'
node.format.file_format = 'PNG'

##############################################################################
# linking of the nodes together (have a look a the nodes in the blender GUI to
# understand the function of each node)
##############################################################################
output = render_layers.outputs['Depth']
input = scene_nodes["Normalize Depth"].inputs[0]
compositor.links.new(output, input)

output = render_layers.outputs['Normal']
input = scene_nodes["Normalize Normal"].inputs[0]
compositor.links.new(output, input)

output = render_layers.outputs['Material Index']
input = scene_nodes["Normalize Material Index"].inputs[0]
compositor.links.new(output, input)

output = scene_nodes["Normalize Depth"].outputs[0]
input = scene_nodes["Color Ramp Depth"].inputs["Factor"]
compositor.links.new(output, input)

output = scene_nodes["Normalize Normal"].outputs[0]
input = scene_nodes["Color Ramp Normal"].inputs["Factor"]
compositor.links.new(output, input)

output = scene_nodes["Normalize Material Index"].outputs[0]
input = scene_nodes["Color Ramp Material Index"].inputs["Factor"]
compositor.links.new(output, input)

output = scene_nodes["Color Ramp Depth"].outputs["Color"]
input = scene_nodes["File Output Depth"].inputs[0]
compositor.links.new(output, input)

output = scene_nodes["Color Ramp Normal"].outputs["Color"]
input = scene_nodes["File Output Normal"].inputs[0]
compositor.links.new(output, input)

output = scene_nodes["Color Ramp Material Index"].outputs["Color"]
input = scene_nodes["File Output Material Index"].inputs[0]
compositor.links.new(output, input)

################################################
### setup of the background (HDRI) functions ###
################################################

# creation of a world material
world = scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    scene.world = world
world.use_nodes = True
world_nodes = world.node_tree.nodes

# removal of default nodes
world_nodes.clear()

# creation of custom nodes
node = world_nodes.new("ShaderNodeTexEnvironment")
node.name = "Environment Texture"

node = world_nodes.new("ShaderNodeBackground")
node.name = "Background"

node = world_nodes.new("ShaderNodeOutputWorld")
node.name = "World Output"

# linking of the nodes together
output = world_nodes["Environment Texture"].outputs["Color"]
input = world_nodes["Background"].inputs["Color"]
world.node_tree.links.new(output, input)

output = world_nodes["Background"].outputs["Background"]
input = world_nodes["World Output"].inputs["Surface"]
world.node_tree.links.new(output, input)

# ( no need to chose the HDRI now )

##########################################################################
### setup of the camera and the empty element used to point the camera ###
##########################################################################

bpy.ops.object.camera_add()
camera = bpy.context.object
bpy.ops.object.empty_add(type='ARROWS')
empty = bpy.context.object
tracking = camera.constraints.new("TRACK_TO")
tracking.target = empty
tracking.track_axis = 'TRACK_NEGATIVE_Z'
tracking.up_axis = 'UP_Y'

##########################################################################################
### setup of the rendering options that are not going to change during data generation ###
##########################################################################################

scene.cycles.device="CPU"
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.use_overwrite = True
scene.render.use_file_extension = True
scene.cycles.samples = 32
scene.cycles.max_bounces = 9
scene.camera = camera
