import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import discover_cogs, require_token


class MainTests(unittest.TestCase):
    def test_discover_cogs_is_sorted_and_skips_private_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("zeta.py", "alpha.py", "_draft.py", "__init__.py", "notes.txt"):
                (root / name).touch()

            self.assertEqual(discover_cogs(root), ["cogs.alpha", "cogs.zeta"])

    def test_require_token_rejects_missing_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("main.load_dotenv"):
                with self.assertRaisesRegex(RuntimeError, "TOKEN is missing"):
                    require_token()

    def test_require_token_strips_whitespace(self):
        with patch.dict(os.environ, {"TOKEN": "  secret  "}, clear=True):
            with patch("main.load_dotenv"):
                self.assertEqual(require_token(), "secret")


if __name__ == "__main__":
    unittest.main()
