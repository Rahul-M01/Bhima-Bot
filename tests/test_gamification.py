import unittest

from cogs.analytics import extract_words
from cogs.levels import level_for_xp


class ExtractWordsTests(unittest.TestCase):
    def test_lowercases_and_skips_short_or_punctuated_tokens(self):
        text = 'Hello world! This BHIMA bot tracks words, e.g. ok no yes'
        self.assertEqual(extract_words(text),
                         ['hello', 'world', 'this', 'bhima', 'bot', 'tracks', 'words', 'yes'])

    def test_urls_contribute_words(self):
        self.assertEqual(extract_words('see https://example.com/long/path'),
                         ['see', 'https', 'example', 'com', 'long', 'path'])


class LevelCurveTests(unittest.TestCase):
    def test_formula_matches_level_squared_times_hundred(self):
        for level in range(0, 21):
            xp = level * level * 100
            if level == 0:
                self.assertEqual(level_for_xp(xp), 0)
            else:
                self.assertEqual(level_for_xp(xp), level)
                self.assertEqual(level_for_xp(xp - 1), level - 1)

    def test_negative_xp_clamps_to_zero(self):
        self.assertEqual(level_for_xp(-50), 0)


if __name__ == '__main__':
    unittest.main()
