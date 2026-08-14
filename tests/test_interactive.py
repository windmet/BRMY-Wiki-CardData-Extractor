import unittest

from toolkit.interactive import parse_birthday_selection


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


if __name__ == "__main__":
    unittest.main()
