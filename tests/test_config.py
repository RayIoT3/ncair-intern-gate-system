import math
import unittest

import config


class ConfigTests(unittest.TestCase):
    def test_card_pool_preserves_configured_reserve_rate(self):
        self.assertEqual(config.CARD_COUNT,
                         math.ceil(config.INTERN_COUNT / (1 - config.CARD_RESERVE_RATE)))
        reserve = config.CARD_COUNT - config.INTERN_COUNT
        self.assertEqual(reserve, 80)
        self.assertEqual(reserve / config.CARD_COUNT, config.CARD_RESERVE_RATE)
