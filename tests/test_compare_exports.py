import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from scripts.compare_exports import compare_xlsx


class ExportComparisonTests(unittest.TestCase):
    def test_number_format_difference_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.xlsx"
            right = root / "right.xlsx"
            for path, number_format in ((left, "General"), (right, "0")):
                workbook = Workbook()
                cell = workbook.active["A1"]
                cell.value = 1
                cell.number_format = number_format
                workbook.save(path)

            difference = compare_xlsx(left, right)

        self.assertIn("number formats differ", difference)


if __name__ == "__main__":
    unittest.main()
