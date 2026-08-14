import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from toolkit import cli


class _FailingDomain:
    @staticmethod
    def run():
        raise RuntimeError("synthetic failure")


class CliTests(unittest.TestCase):
    def test_all_returns_failure_when_any_domain_fails(self):
        output = io.StringIO()
        with patch.dict(cli.DOMAINS, {"cards": _FailingDomain}, clear=True):
            with patch.object(cli, "prepare_masterdata", return_value=True):
                with redirect_stdout(output):
                    result = cli.cmd_all()

        self.assertFalse(result)
        self.assertIn("cards: synthetic failure", output.getvalue())

    def test_main_exits_nonzero_when_all_fails(self):
        with patch.object(cli.sys, "argv", ["toolkit", "all"]):
            with patch.object(cli, "cmd_all", return_value=False):
                with self.assertRaisesRegex(SystemExit, "1"):
                    cli.main()

    def test_main_exits_nonzero_when_decrypt_input_is_missing(self):
        with patch.object(cli.sys, "argv", ["toolkit", "decrypt"]):
            with patch.object(cli, "cmd_decrypt", return_value=False):
                with self.assertRaisesRegex(SystemExit, "1"):
                    cli.main()


if __name__ == "__main__":
    unittest.main()
