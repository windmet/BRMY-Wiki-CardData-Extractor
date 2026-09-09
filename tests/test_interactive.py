import unittest
from datetime import date

from toolkit.interactive import parse_birthday_selection, parse_recent_year_selection


class InteractiveSelectionTests(unittest.TestCase):
    def test_empty_birthday_selection_uses_auto(self):
        self.assertEqual((None, None), parse_birthday_selection(""))
        self.assertEqual((None, None), parse_birthday_selection("auto"))

    def test_birthday_selection_accepts_cycle_or_start_year(self):
        self.assertEqual((None, 2), parse_birthday_selection("2"))
        self.assertEqual((2026, None), parse_birthday_selection("2026"))

    def test_birthday_selection_rejects_ambiguous_values(self):
        with self.assertRaisesRegex(ValueError, "1/2/3"):
            parse_birthday_selection("100")

    def test_recent_year_selection_defaults_or_accepts_fixed_date(self):
        self.assertEqual(
            "2026-08-15",
            parse_recent_year_selection("", today=date(2026, 8, 15)),
        )
        self.assertEqual("2026-06-22", parse_recent_year_selection("2026-06-22"))
        self.assertIsNone(parse_recent_year_selection("N"))

    def test_recent_year_selection_rejects_invalid_date(self):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            parse_recent_year_selection("2026-02-30")


if __name__ == "__main__":
    unittest.main()
