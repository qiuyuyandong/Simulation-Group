### BLENDER SCENE GENERATION SCRIPT ###

import bpy
import random as rd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
scene = bpy.context.scene
try:
    bpy.ops.curve.tree_add.get_rna_type()
except KeyError:
    raise RuntimeError("Enable Sapling Tree Gen before running this script.") from None
for asset in ('leaf_texture/TexturesCom_Leaves0089_1_masked_S.png', 'bark_texture/TexturesCom_CedarTreeBark_1K_albedo.tif', 'fruit_model/orange_for_cycles.obj', 'fruit_model/orange_for_cycles.mtl', 'fruit_model/Color.jpg', 'fruit_model/Normal.jpg'):
    if not (BASE_DIR / asset).is_file():
        raise FileNotFoundError(BASE_DIR / asset)

# using the cycles rendering engine

scene.render.engine = 'CYCLES'
scene.compositing_node_group = None

# removing all the objects already existing in the scene

if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
for obj in bpy.context.view_layer.objects:
    obj.hide_set(False)
    obj.select_set(True)
bpy.ops.object.delete(use_global=False)

# architecture of generated tree

bpy.ops.curve.tree_add(do_update=True,
                        bevel=True,
                        prune=False,
                        showLeaves=True,
                        useArm=False,
                        seed=0,
                        handleType='0',
                        levels=rd.randint(3, 4),
                        length=(1, 0.3, 0.6, 0.45),
                        lengthV=(0, 0, 0, 0),
                        taperCrown=0,
                        branches=(0, 50, 30, 10),
                        curveRes=(8, 5, 3, 1),
                        curve=(0, -40, -40, 0),
                        curveV=(20, 50, 75, 0),
                        curveBack=(0, 0, 0, 0),
                        baseSplits=0,
                        segSplits=(0, 0, 0, 0),
                        splitByLen=True,
                        rMode='rotate',
                        splitAngle=(0, 0, 0, 0),
                        splitAngleV=(0, 0, 0, 0),
                        scale=13,
                        scaleV=3,
                        attractUp=(0, 0, 0.5, 0.5),
                        attractOut=(0, 0, 0, 0),
                        shape='1',
                        shapeS='1',
                        customShape=(0.5, 1, 0.3, 0.5),
                        branchDist=1,
                        nrings=0,
                        baseSize=rd.uniform(0.1, 0.4),
                        baseSize_s=0.25,
                        splitHeight=rd.uniform(0.1, 0.2),
                        splitBias=rd.uniform(0.0, 1.0),
                        ratio=0.015,
                        minRadius=0.0015,
                        closeTip=False,
                        rootFlare=1,
                        autoTaper=True,
                        taper=(1, 1, 1, 1),
                        radiusTweak=(1, 1, 1, 1),
                        ratioPower=1.1,
                        downAngle=(90, 110, 45, 45),
                        downAngleV=(0, 80, 10, 10),
                        useOldDownAngle=False,
                        useParentAngle=True,
                        rotate=(99.5, 137.5, 137.5, 137.5),
                        rotateV=(rd.randint(-30, 30), rd.randint(-30, 30), rd.randint(-30, 30), rd.randint(-30, 30)),
                        scale0=1,
                        scaleV0=0.1,
                        pruneWidth=0.4,
                        pruneBase=0.3,
                        pruneWidthPeak=0.6,
                        prunePowerHigh=0.5,
                        prunePowerLow=0.001,
                        pruneRatio=1,
                        leaves=rd.randint(25, 50),
                        leafDownAngle=45,
                        leafDownAngleV=10,
                        leafRotate=137.5,
                        leafRotateV=0,
                        leafScale=0.17,
                        leafScaleX=1,
                        leafScaleT=0,
                        leafScaleV=0,
                        leafShape='hex',
                        leafangle=0,
                        horzLeaves=True,
                        leafDist=rd.choice(['1', '2', '3', '4', '5', '6', '7']),
                        bevelRes=0,
                        resU=4,
                        armAnim=False,
                        previewArm=False,
                        leafAnim=False,
                        frameRate=1,
                        loopFrames=0,
                        wind=1,
                        gust=1,
                        gustF=0.075,
                        af1=1,
                        af2=1,
                        af3=4,
                        makeMesh=False,
                        armLevels=2,
                        boneStep=(1, 1, 1, 1))

# textures and materials of generated tree

## leaves

leaf_material = bpy.data.materials.new("LEAF_material")
leaf_material.use_nodes = True
leaf_nodes = leaf_material.node_tree.nodes

leaf_nodes.clear()

node = leaf_nodes.new("ShaderNodeTexImage")
node.name = "Image Texture"

node = leaf_nodes.new("ShaderNodeInvert")
node.name = "Invert"

node = leaf_nodes.new("ShaderNodeBsdfDiffuse")
node.name = "Diffuse BSDF"

node = leaf_nodes.new("ShaderNodeBsdfTransparent")
node.name = "Transparent BSDF"

node = leaf_nodes.new("ShaderNodeAddShader")
node.name = "Add Shader"

node = leaf_nodes.new("ShaderNodeOutputMaterial")
node.name = "Material Output"

output = leaf_nodes['Image Texture'].outputs['Alpha']
input = leaf_nodes['Invert'].inputs['Color']
leaf_material.node_tree.links.new(output, input)

output = leaf_nodes['Image Texture'].outputs['Color']
input = leaf_nodes['Diffuse BSDF'].inputs['Color']
leaf_material.node_tree.links.new(output, input)

output = leaf_nodes['Invert'].outputs['Color']
input = leaf_nodes['Transparent BSDF'].inputs['Color']
leaf_material.node_tree.links.new(output, input)

output = leaf_nodes['Diffuse BSDF'].outputs['BSDF']
input = leaf_nodes['Add Shader'].inputs[0]
leaf_material.node_tree.links.new(output, input)

output = leaf_nodes['Transparent BSDF'].outputs['BSDF']
input = leaf_nodes['Add Shader'].inputs[1]
leaf_material.node_tree.links.new(output, input)

output = leaf_nodes['Add Shader'].outputs['Shader']
input = leaf_nodes['Material Output'].inputs['Surface']
leaf_material.node_tree.links.new(output, input)

leaf_texture_image = bpy.data.images.load(str(BASE_DIR / "leaf_texture/TexturesCom_Leaves0089_1_masked_S.png"))
leaf_material.node_tree.nodes["Image Texture"].image = leaf_texture_image

bpy.data.objects['leaves'].active_material = leaf_material

## trunk and branches

wood_material = bpy.data.materials.new("WOOD_material")
wood_material.use_nodes = True
wood_nodes = wood_material.node_tree.nodes

wood_nodes.clear()

node = wood_nodes.new("ShaderNodeTexImage")
node.name = "Image Texture"

node = wood_nodes.new("ShaderNodeBsdfDiffuse")
node.name = "Diffuse BSDF"

node = wood_nodes.new("ShaderNodeOutputMaterial")
node.name = "Material Output"

output = wood_nodes["Image Texture"].outputs['Color']
input = wood_nodes["Diffuse BSDF"].inputs['Color']
wood_material.node_tree.links.new(output, input)

output = wood_nodes["Diffuse BSDF"].outputs["BSDF"]
input = wood_nodes["Material Output"].inputs['Surface']
wood_material.node_tree.links.new(output, input)

wood_texture_image = bpy.data.images.load(str(BASE_DIR / "bark_texture/TexturesCom_CedarTreeBark_1K_albedo.tif"))
wood_material.node_tree.nodes["Image Texture"].image = wood_texture_image

bpy.data.objects['tree'].active_material = wood_material

# fruits as a particle system

bpy.ops.wm.obj_import(filepath=str(BASE_DIR / "fruit_model/orange_for_cycles.obj"))

# to avoid seing the original fruit in the rendered images
bpy.data.objects['Orange'].hide_render = True
bpy.data.objects['Orange'].hide_set(True)

leaves = bpy.data.objects['leaves']
fruits_particle_system = leaves.modifiers.new("FRUITS", type='PARTICLE_SYSTEM').particle_system
fruits_settings = fruits_particle_system.settings

fruits_settings.type = "HAIR"
fruits_settings.use_advanced_hair = True
fruits_settings.hair_step = 5
fruits_settings.count = 500
fruits_settings.hair_length = 2.5
fruits_settings.emit_from = "FACE"
fruits_settings.use_emit_random = True
fruits_settings.use_even_distribution=True
fruits_settings.distribution = "JIT"
fruits_settings.use_rotations = True
fruits_settings.rotation_mode = "NOR_TAN"
fruits_settings.rotation_factor_random = 0.5
fruits_settings.phase_factor = -0.4
fruits_settings.phase_factor_random = 1.3
fruits_settings.render_type = "OBJECT"
fruits_settings.instance_object = bpy.data.objects['Orange']



# setup of the HDRI functions

world = scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    scene.world = world
world.use_nodes = True
world_nodes = world.node_tree.nodes
world_nodes.clear()

node = world_nodes.new("ShaderNodeTexEnvironment")
node.name = "Environment Texture"

node = world_nodes.new("ShaderNodeBackground")
node.name = "Background"

node = world_nodes.new("ShaderNodeOutputWorld")
node.name = "World Output"

output = world_nodes["Environment Texture"].outputs["Color"]
input = world_nodes["Background"].inputs["Color"]
world.node_tree.links.new(output, input)

output = world_nodes["Background"].outputs["Background"]
input = world_nodes["World Output"].inputs["Surface"]
world.node_tree.links.new(output, input)

# ( no need to chose the HDRI now )

# setup of the camera and the empty element used to point the camera

bpy.ops.object.camera_add()
camera = bpy.context.object
bpy.ops.object.empty_add(type='ARROWS')
empty = bpy.context.object
tracking = camera.constraints.new("TRACK_TO")
tracking.target = empty
tracking.track_axis = 'TRACK_NEGATIVE_Z'
tracking.up_axis = 'UP_Y'

# setup of the rendering options that are not going to change during data generation

scene.cycles.device="CPU"
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.use_overwrite = True
scene.render.use_file_extension = True
scene.cycles.samples = 32
scene.cycles.max_bounces = 9
scene.camera = camera
