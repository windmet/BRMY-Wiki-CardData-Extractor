import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from toolkit import cli


class CliTests(unittest.TestCase):
    def test_doctor_json_reports_registered_runtime(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = cli.cmd_doctor(as_json=True)

        report = json.loads(stream.getvalue())
        self.assertTrue(result)
        self.assertEqual("PASS", report["status"])
        self.assertIn("cards", report["domains"])
        self.assertIn("tkinter", {item["name"] for item in report["dependencies"]})

    def test_retired_commands_exit_with_replacement_hint(self):
        for command in ("decrypt", "all", "run", "update"):
            with patch("sys.argv", ["toolkit", command, "cards"]):
                with self.assertRaises(SystemExit) as raised:
                    cli.main()
            self.assertIn("已停用", str(raised.exception.code))
            self.assertIn("generate", str(raised.exception.code))

    def test_list_names_every_registered_task(self):
        output = io.StringIO()
        with redirect_stdout(output):
            cli.cmd_list()
        for name in cli.DOMAINS:
            self.assertIn(name, output.getvalue())


if __name__ == "__main__":
    unittest.main()
