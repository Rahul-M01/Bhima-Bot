import tempfile
import unittest
from pathlib import Path

import economy


class EconomyStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'economy.json'

    def tearDown(self):
        self._tmp.cleanup()

    def test_new_users_start_with_starting_balance(self):
        self.assertEqual(economy.get_balance(1, 42, path=self.path), economy.STARTING_BALANCE)

    def test_add_and_spend_chips(self):
        balance = economy.add_chips(1, 42, 100, path=self.path)
        self.assertEqual(balance, economy.STARTING_BALANCE + 100)
        self.assertTrue(economy.spend_chips(1, 42, 50, path=self.path))
        self.assertEqual(economy.get_balance(1, 42, path=self.path),
                         economy.STARTING_BALANCE + 50)

    def test_spend_rejects_insufficient_funds(self):
        with self.subTest('negative amounts'):
            self.assertFalse(economy.spend_chips(1, 42, -5, path=self.path))
        with self.subTest('more than the balance'):
            self.assertFalse(economy.spend_chips(1, 42, economy.STARTING_BALANCE + 1,
                                                 path=self.path))
            self.assertEqual(economy.get_balance(1, 42, path=self.path),
                             economy.STARTING_BALANCE)

    def test_daily_bonus_respects_cooldown(self):
        now = 1_000_000
        claimed, retry = economy.claim_daily(1, 42, now=now, path=self.path)
        self.assertEqual(claimed, economy.DAILY_BONUS)
        claimed_again, retry_again = economy.claim_daily(1, 42, now=now + 60, path=self.path)
        self.assertEqual(claimed_again, 0)
        self.assertEqual(retry_again, economy.DAILY_COOLDOWN_SECONDS - 60)
        claimed_later, _ = economy.claim_daily(1, 42,
                                               now=now + economy.DAILY_COOLDOWN_SECONDS + 1,
                                               path=self.path)
        self.assertEqual(claimed_later, economy.DAILY_BONUS)

    def test_top_holders_ranking(self):
        economy.add_chips(1, 'a', 300, path=self.path)
        economy.add_chips(1, 'b', -400, path=self.path)
        holders = economy.top_holders(1, limit=2, path=self.path)
        self.assertEqual([uid for uid, _ in holders], ['a', 'b'])
        self.assertGreaterEqual(holders[0][1], holders[1][1])

    def test_seconds_until_daily_clamps_at_zero(self):
        self.assertEqual(economy.seconds_until_daily(0, now=10 * economy.DAILY_COOLDOWN_SECONDS), 0)


if __name__ == '__main__':
    unittest.main()
