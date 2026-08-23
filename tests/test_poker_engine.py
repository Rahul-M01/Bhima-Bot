import unittest

from poker_engine import (
    HAND_NAMES, RVAL, best_hand, best_omaha_hand, evaluate, fmt_hand, variant_key,
)


def card(spec):
    """'As' -> ('A', '♠'); '10s' -> ('10', '♠')."""
    rank = '10' if spec.startswith('10') else spec[0]
    suits = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}
    return rank, suits[spec[-1]]


def cards(*specs):
    return tuple(card(s) for s in specs)


class EvaluateTests(unittest.TestCase):
    def test_category_ordering(self):
        hands = {
            'High Card': cards('2h', '5s', '7d', '9c', 'Kh'),
            'One Pair': cards('2h', '2s', '7d', '9c', 'Kh'),
            'Two Pair': cards('2h', '2s', '9d', '9c', 'Kh'),
            'Three of a Kind': cards('2h', '2s', '2d', '9c', 'Kh'),
            'Straight': cards('5h', '6s', '7d', '8c', '9h'),
            'Flush': cards('2h', '5h', '7h', '9h', 'Kh'),
            'Full House': cards('2h', '2s', '2d', 'Kc', 'Kh'),
            'Four of a Kind': cards('2h', '2s', '2d', '2c', 'Kh'),
            'Straight Flush': cards('5h', '6h', '7h', '8h', '9h'),
        }
        for name, hand in hands.items():
            self.assertEqual(HAND_NAMES[evaluate(hand)[0]], name)

    def test_wheel_straight(self):
        score = evaluate(cards('Ah', '2s', '3d', '4c', '5h'))
        self.assertEqual(score, (4, [5, 4, 3, 2, 1]))


class BestHandTests(unittest.TestCase):
    def test_best_hand_picks_flush_from_seven(self):
        seven = cards('2h', '5h', '9h', 'Jh', 'Kh', 'Ad', 'Qc')
        best, score = best_hand(seven)
        self.assertEqual(HAND_NAMES[score[0]], 'Flush')
        self.assertEqual(len(best), 5)
        self.assertIn(card('Kh'), best)

    def test_best_omaha_hand_must_use_exactly_two_hole_cards(self):
        # Naive best-of-seven would find aces-full (AAA K K), but Omaha forces
        # exactly two hole cards, so the best legal hand is trips aces only.
        hole = cards('As', 'Ah', 'Ks', 'Kh')
        board = cards('Ac', 'Kd', '2s')
        _, score = best_omaha_hand(hole, board)
        self.assertEqual(score[0], 3)
        self.assertEqual(score, (3, [RVAL['A'], RVAL['K'], RVAL['2']]))
        self.assertNotEqual(score[0], HAND_NAMES.index('Full House'))


class VariantTests(unittest.TestCase):
    def test_variant_key_aliases(self):
        self.assertEqual(variant_key("Texas Hold'em"), 'holdem')
        self.assertEqual(variant_key(' OMAHA '), 'omaha')
        self.assertEqual(variant_key('7-card stud'), 'stud')
        self.assertIsNone(variant_key('garbage'))

    def test_fmt_hand_empty(self):
        self.assertEqual(fmt_hand([]), '—')


if __name__ == '__main__':
    unittest.main()
