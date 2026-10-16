import bpy
import random as rd
import math as math
from pathlib import Path
import itertools

# This script is used to generate the images. It is meant to be used after the
# scene generation scripts (sapling_tree_scene_gen.py, space_tree_scene_gen.py).
#It controls parameters such as the number of images that are going to be
#rendered, the change frequency for the background images,the rendering quality,
#etc.

###################################
### Background image parameters ###
###################################

BASE_DIR = Path(__file__).resolve().parent
scene = bpy.context.scene
world = scene.world
if world is None or world.node_tree is None:
    raise RuntimeError("Run a tree scene generation script first.")
env_text_node = world.node_tree.nodes.get("Environment Texture")
if env_text_node is None:
    raise RuntimeError("The tree scene has no Environment Texture node.")

# the folder in which all HDRIs files are located
hdri_folder = BASE_DIR / 'hdri'

hdri_list = sorted(path for path in hdri_folder.iterdir() if path.is_file() and path.suffix.lower() in {'.hdr', '.exr'})
if not hdri_list:
    raise FileNotFoundError(f"No HDRI files in {hdri_folder}")
hdri_cycle_iterator = itertools.cycle(hdri_list)

# the background changes every change_frequency rendered images
change_frequency = 2
if change_frequency < 1:
    raise ValueError("change_frequency must be at least 1")

##########################################################
### Camera & render options & associated empty element ###
##########################################################

camera = scene.camera
if camera is None:
    raise RuntimeError("The tree scene has no active camera.")
tracking = next((constraint for constraint in camera.constraints if constraint.type == 'TRACK_TO'), None)
if tracking is None or tracking.target is None:
    raise RuntimeError("The camera must track the scene generation script's empty object.")
empty = tracking.target

# the number of samples used for rendering (the higher the better the generated images)
scene.cycles.samples = 64

# Enable Cycles render denoising.
scene.cycles.use_denoising = True

#####################################################
### Parameters of camera position and orientation ###
#####################################################

pi = 3.14159265

# definition of the 3D box the empty element (to which the camera is
# going to point toward) is going to be sampled from

x_range = [-3,3]
y_range = [-3,3]
z_range = [2,6]

# definition of the hollow cylinder the camera position is going to be sampled from

# height original
#h2 = 10
#h1 = 3
h2 = 5.2
h1 = 5
# radius original
#r1 = 3
#r2 = 10
r1 = 9
r2 = 10

############################
### Animation parameters ###
############################

# number of rendered images (change only ending_frame_num to modify the number
# of rendered images)
starting_frame_num = 1
ending_frame_num = 5000

scene.frame_end = ending_frame_num
output_folder = BASE_DIR / 'output/images'
output_folder.mkdir(parents=True, exist_ok=True)

#################
### MAIN LOOP ###
#################

for current_frame_num in range (starting_frame_num, ending_frame_num+1):

    # step forward in time
    bpy.context.scene.frame_set(current_frame_num)

    # random camera position parameters
    theta = rd.random()*2*pi
    alpha = rd.random()

    # modification of the camera location
    camera.location[0] = (r1+alpha*(r2-r1))*math.cos(theta)
    camera.location[1] = (r1+alpha*(r2-r1))*math.sin(theta)
    camera.location[2] = (h2-h1)*rd.random()+h1
    
    # recording the camera location at the current timestep
    camera.keyframe_insert(data_path='location', index=-1)

    # modification of the empty element location
    # because the camera is assigned to track this empty, it will modify
    # its orientation and make point toward the tree (with a random factor,
    # it will not always point toward the center of the tree)
    empty.location[0] = rd.random()*(x_range[1]-x_range[0])+x_range[0]
    empty.location[1] = rd.random()*(y_range[1]-y_range[0])+y_range[0]
    empty.location[2] = rd.random()*(z_range[1]-z_range[0])+z_range[0]

    empty.keyframe_insert(data_path='location', index=-1)

    # recording the camera orientation at the current timestep (making it
    # point toward the empty element location)
    camera.keyframe_insert(data_path='rotation_euler', index=-1)

    ## changing the background image (according to defined change_frequency)
    if (current_frame_num - starting_frame_num) % change_frequency == 0:
        current_hdri = next(hdri_cycle_iterator)
        current_bg_image = bpy.data.images.load(str(current_hdri), check_existing=True)
        env_text_node.image = current_bg_image

    # render and save the image
    # the labels are rendered automatically for each generated images (as defined
    # in the scene generation script)
    scene.render.filepath = str(output_folder / f'image_{current_frame_num}')
    bpy.ops.render.render(write_still=True)
