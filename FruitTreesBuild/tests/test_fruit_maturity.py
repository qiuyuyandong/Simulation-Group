"""Exact, repeatable maturity allocation and public configuration validation."""
from collections import Counter
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fruit_maturity import maturity_stages
from scripts.launcher_config import load_build_config, validate_maturity_counts


class FruitMaturityTests(unittest.TestCase):
    def test_exact_counts_repeatable_and_independent_of_global_random(self):
        counts = {'unripe': 3, 'turning': 4, 'ripe': 5}
        state = random.getstate()
        first = maturity_stages(counts, 12, 'unknown', 101)
        self.assertEqual(Counter(first), counts)
        self.assertEqual(first, maturity_stages(dict(reversed(list(counts.items()))), 12, 'ripe', 101))
        self.assertEqual(random.getstate(), state)
        self.assertNotEqual(first, maturity_stages(counts, 12, 'unknown', 102))

    def test_single_stage_and_zero_fruit_compatibility(self):
        for stage in ('unknown', 'unripe', 'turning', 'ripe'):
            self.assertEqual(maturity_stages(None, 3, stage, 1), [stage] * 3)
        zero = dict.fromkeys(('unripe', 'turning', 'ripe'), 0)
        validate_maturity_counts(zero, 0, 'apple', None)
        self.assertEqual(maturity_stages(zero, 0, 'unknown', 1), [])
        validate_maturity_counts(None, 80, 'orange', 'orange_base_v1')

    def test_public_config_and_invalid_inputs(self):
        counts = {'unripe': 2, 'turning': 3, 'ripe': 5}
        base = {'fruit': 'apple', 'fruitCount': 10, 'maturityCounts': counts}
        invalid = [[], {}, {**counts, 'unknown': 0}, {**counts, 'ripe': -1},
                   {**counts, 'unripe': True}, {**counts, 'ripe': 5.0},
                   {**counts, 'ripe': '5'}, {**counts, 'ripe': 4}]
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            config.write_text(json.dumps(base), encoding='utf-8')
            self.assertEqual(load_build_config(config), base)
            for bad in invalid:
                with self.subTest(counts=bad):
                    config.write_text(json.dumps({**base, 'maturityCounts': bad}), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        load_build_config(config)
            for extra in ({'fruit': 'orange'}, {'fruitVariantId': 'apple_custom'}):
                config.write_text(json.dumps({**base, **extra}), encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_build_config(config)


if __name__ == '__main__':
    unittest.main()
