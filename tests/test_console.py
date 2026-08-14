import unittest
from unittest.mock import Mock, patch

from toolkit.core.console import configure_console


class ConsoleTests(unittest.TestCase):
    def test_configures_both_output_streams_for_utf8_replacement(self):
        stdout = Mock()
        stderr = Mock()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            configure_console()

        stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
        stderr.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    unittest.main()
