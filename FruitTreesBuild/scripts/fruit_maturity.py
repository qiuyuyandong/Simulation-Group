"""Apple visual maturity presets; not biologically calibrated growth stages."""
import random


# shortcut: hue/size presets use the existing apple, replace with measured variants when available.
APPLE_STAGES = {'unripe': (0.80, 0.83), 'turning': (0.90, 0.60), 'ripe': (1.00, 0.50)}


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
        color = nodes['Diffuse BSDF'].inputs['Color']
        if len(color.links) != 1:
            raise RuntimeError('Expected the bundled apple diffuse color link.')
        original = color.links[0].from_socket
        tint = nodes.new('ShaderNodeHueSaturation')
        tint.name = 'Apple_Maturity'
        tint.inputs['Hue'].default_value = APPLE_STAGES[stage][1]
        links.new(original, tint.inputs['Color'])
        links.new(tint.outputs['Color'], color)
        materials[stage] = material
    return materials
