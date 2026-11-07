import io
import unittest
from unittest.mock import Mock, patch

from toolkit.core.console import configure_console, safe_print


class ConsoleTests(unittest.TestCase):
    def test_configures_both_output_streams_for_utf8_replacement(self):
        stdout = Mock()
        stderr = Mock()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            configure_console()

        stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
        stderr.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")

    def test_safe_print_replaces_unencodable_status_text(self):
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")

        safe_print("卡牌增量更新", file=stream)
        stream.flush()

        self.assertEqual("??????", raw.getvalue().decode("cp1252").strip())


if __name__ == "__main__":
    unittest.main()
