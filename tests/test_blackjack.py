import unittest

from cogs import blackjack


def hand(*specs):
    ranks = {'A': 'A', 'K': 'K', 'Q': 'Q', 'J': 'J'}
    return [(ranks.get(s[0], s[0]), '♠') for s in specs]


class HandValueTests(unittest.TestCase):
    def test_natural_blackjack(self):
        self.assertEqual(blackjack.hand_value(hand('A', 'K')), 21)

    def test_aces_demote_as_needed(self):
        self.assertEqual(blackjack.hand_value(hand('A', 'A', '9')), 21)
        self.assertEqual(blackjack.hand_value(hand('A', 'A', '9', '5')), 16)

    def test_face_cards_count_ten(self):
        self.assertEqual(blackjack.hand_value(hand('K', 'Q', '7')), 27)


class PayoutTests(unittest.TestCase):
    BET = 100

    def test_natural_pays_three_to_two(self):
        outcome = blackjack.resolve_outcome(20, True, 18, False)
        payout = blackjack.payout_for(self.BET, outcome)
        self.assertEqual(outcome, 'player_blackjack')
        self.assertEqual(payout, self.BET + 150)   # 3:2 profit plus returned stake

    def test_push_returns_stake(self):
        self.assertEqual(
            blackjack.payout_for(self.BET, blackjack.resolve_outcome(19, False, 19, False)),
            self.BET)

    def test_loss_returns_nothing(self):
        self.assertEqual(
            blackjack.payout_for(self.BET, blackjack.resolve_outcome(23, False, 5, False)),
            0)
        self.assertEqual(
            blackjack.payout_for(self.BET, blackjack.resolve_outcome(17, False, 21, False)),
            0)


class StatsTests(unittest.TestCase):
    def test_bump_stats_updates_net_and_biggest_win(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'blackjack_stats.json'
            original = blackjack.STATS_FILE
            blackjack.STATS_FILE = path
            try:
                entry = blackjack.bump_stats(1, 2, payout=250, bet=100)   # +150 net
                entry = blackjack.bump_stats(1, 2, payout=0, bet=50)      # loss
                entry = blackjack.bump_stats(1, 2, payout=75, bet=75)     # push
                data = json.loads(path.read_text())
                stored = data['1']['2']
            finally:
                blackjack.STATS_FILE = original
            self.assertEqual(entry['hands'], stored['hands'])
            self.assertEqual(stored['hands'], 3)
            self.assertEqual(stored['wins'], 1)
            self.assertEqual(stored['losses'], 1)
            self.assertEqual(stored['pushes'], 1)
            self.assertEqual(stored['net'], 100)
            self.assertEqual(stored['biggest_win'], 150)


if __name__ == '__main__':
    unittest.main()
