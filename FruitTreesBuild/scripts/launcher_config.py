"""Strict, standard-library-only configuration loading for public launchers."""
import json
import math


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate configuration field: ' + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Non-finite JSON number is not allowed: ' + value)


def load_config(path, allowed):
    with path.open(encoding='utf-8-sig') as handle:
        data = json.load(handle, object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(data, dict):
        raise ValueError('Configuration must be a JSON object: ' + str(path))
    unknown = set(data) - set(allowed)
    if unknown:
        raise ValueError('Unknown configuration fields in ' + str(path) + ': ' + ', '.join(sorted(unknown)))
    return data


def require_type(key, value, kind, nullable=False):
    if nullable and value is None:
        return
    # bool is a subclass of int; do not accept true as a count or thread limit.
    valid = isinstance(value, kind) and not (kind in (int, float) and isinstance(value, bool))
    if not valid:
        raise ValueError('Invalid type for configuration field ' + key + '; expected ' + kind.__name__ + '.')


BUILD_CHOICES = {'generator': ('auto', 'space', 'sapling'), 'fruit': ('apple', 'orange'),
                 'backend': ('modern',), 'profile': ('auto', 'orchard'),
                 'maturityStage': ('unknown', 'unripe', 'turning', 'ripe')}
BUILD_INTEGERS = {'seed': (0, 2147483647), 'frames': (0, 5000), 'resolution': (64, 4096),
                  'samples': (1, 4096), 'threads': (1, 256), 'leafCount': (0, 20000), 'fruitCount': (0, 2000)}
BUILD_DIMENSIONS = {'treeHeight': (.5, 20), 'trunkHeight': (.1, 10), 'trunkDiameter': (.02, 1),
                    'leafLength': (.02, .5), 'fruitDiameter': (.02, .3), 'crownWidth': (.5, 20),
                    'leafFruitClearance': (0, .05), 'branchUplift': (0, 1),
                    'branchAngleMin': (90, 180), 'leafSpacing': (0, .1),
                    'heightTaper': (0, .8)}
BUILD_FIELDS = set(BUILD_CHOICES) | set(BUILD_INTEGERS) | set(BUILD_DIMENSIONS) | {'blenderPath', 'fruitVariantId', 'noGround'}


def load_build_config(path):
    data = load_config(path, BUILD_FIELDS)
    for key, choices in BUILD_CHOICES.items():
        if key in data and data[key] not in choices:
            raise ValueError('Unsupported ' + key + ': choose ' + ', '.join(choices))
    for key, limits in BUILD_INTEGERS.items():
        if key in data:
            require_type(key, data[key], int)
            if not limits[0] <= data[key] <= limits[1]:
                raise ValueError('Configuration field out of range: ' + key)
    for key, limits in BUILD_DIMENSIONS.items():
        if key in data:
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not limits[0] <= value <= limits[1]:
                raise ValueError('Invalid dimension in configuration field: ' + key)
    for key in ('blenderPath', 'fruitVariantId'):
        if key in data:
            require_type(key, data[key], str, nullable=True)
    if 'noGround' in data:
        require_type('noGround', data['noGround'], bool)
    return data
