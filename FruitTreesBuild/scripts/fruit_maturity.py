"""Apple visual maturity presets; not biologically calibrated growth stages."""
import random


# shortcut: hue/size presets use the existing apple, replace with measured variants when available.
APPLE_STAGES = {'unripe': (0.80, 0.79), 'turning': (0.90, 0.73), 'ripe': (1.00, 0.50)}
APPLE_TONES = {'unripe': (0.60, 0.65), 'turning': (0.85, 0.66), 'ripe': (0.80, 0.75)}


def maturity_stages(counts, count, stage, seed):
    if counts is None:
        return [stage] * count
    stages = [stage for stage in APPLE_STAGES for _ in range(counts[stage])]
    # Keep maturity assignment independent of branch/fruit placement randomness.
    random.Random(seed + 7919).shuffle(stages)
    return stages


def apple_materials(source, stages):
    materials = {}
    for stage in sorted(set(stages) - {'unknown'}):
        material = source.copy()
        material.name = 'Apple_' + stage + '_v1'
        nodes, links = material.node_tree.nodes, material.node_tree.links
        color = next(node for node in nodes if node.type == 'BSDF_DIFFUSE').inputs['Color']
        if len(color.links) != 1:
            raise RuntimeError('Expected the bundled apple diffuse color link.')
        original = color.links[0].from_socket
        tint = nodes.new('ShaderNodeHueSaturation')
        tint.name = 'Apple_Maturity'
        tint.inputs['Hue'].default_value = APPLE_STAGES[stage][1]
        tint.inputs['Saturation'].default_value, tint.inputs['Value'].default_value = APPLE_TONES[stage]
        links.new(original, tint.inputs['Color'])
        links.new(tint.outputs['Color'], color)
        if stage == 'turning':
            # Reference: yellow-green shoulders grading into a rose-red lower body.
            warm = nodes.new('ShaderNodeHueSaturation')
            warm.inputs['Hue'].default_value = 0.49
            warm.inputs['Saturation'].default_value = 0.72
            warm.inputs['Value'].default_value = 0.82
            links.new(original, warm.inputs['Color'])
            coordinates = nodes.new('ShaderNodeTexCoord')
            height = nodes.new('ShaderNodeSeparateXYZ')
            links.new(coordinates.outputs['Generated'], height.inputs[0])
            stretch = nodes.new('ShaderNodeVectorMath')
            stretch.operation = 'MULTIPLY'
            stretch.inputs[1].default_value = (5, 5, 1)
            links.new(coordinates.outputs['Generated'], stretch.inputs[0])
            noise = nodes.new('ShaderNodeTexNoise')
            noise.inputs['Scale'].default_value = 3.0
            noise.inputs['Detail'].default_value = 2.0
            links.new(stretch.outputs['Vector'], noise.inputs['Vector'])
            variation = nodes.new('ShaderNodeMath')
            variation.operation = 'MULTIPLY_ADD'
            variation.inputs[1].default_value = 0.12
            links.new(noise.outputs['Fac'], variation.inputs[0])
            # shortcut: bundled apple shoulders face local -Z; recalibrate if replacing its mesh.
            links.new(height.outputs['Z'], variation.inputs[2])
            mask = nodes.new('ShaderNodeValToRGB')
            mask.color_ramp.elements[0].position = 0.45
            mask.color_ramp.elements[1].position = 0.85
            links.new(variation.outputs[0], mask.inputs['Fac'])
            blush = nodes.new('ShaderNodeMixRGB')
            blush.name = 'Apple_Blush'
            links.new(mask.outputs['Color'], blush.inputs[0])
            links.new(tint.outputs['Color'], blush.inputs[1])
            links.new(warm.outputs['Color'], blush.inputs[2])
            links.new(blush.outputs['Color'], color)
        materials[stage] = material
    return materials
