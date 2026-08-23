import unittest

from cogs.poll import build_tallies, parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_plain_seconds(self):
        self.assertEqual(parse_duration('45'), 45)

    def test_units(self):
        self.assertEqual(parse_duration('30s'), 30)
        self.assertEqual(parse_duration('5m'), 300)
        self.assertEqual(parse_duration('1h'), 3600)

    def test_rejects_non_durations(self):
        self.assertIsNone(parse_duration('Red'))
        self.assertIsNone(parse_duration('five minutes'))
        self.assertIsNone(parse_duration(''))


class BuildTalliesTests(unittest.TestCase):
    def test_counts_votes_per_option(self):
        votes = {'1': 0, '2': 1, '3': 0, '4': 2}
        self.assertEqual(build_tallies(['a', 'b', 'c'], votes), [2, 1, 1])

    def test_empty_votes(self):
        self.assertEqual(build_tallies(['a', 'b'], {}), [0, 0])

    def test_ignores_out_of_range_indices(self):
        self.assertEqual(build_tallies(['a', 'b'], {'1': 9}), [0, 0])


if __name__ == '__main__':
    unittest.main()
