import unittest

from toolkit.core.availability import assessment_time, date_window


class AvailabilityTests(unittest.TestCase):
    def test_boundaries_and_offsets(self):
        start, end = '2026-09-09T09:00:00+09:00', '2026-09-10T09:00:00+09:00'
        for now, expected in [('2026-09-08T23:59:59Z', 'scheduled'),
                              ('2026-09-09T00:00:00Z', 'within_window'),
                              ('2026-09-10T00:00:00Z', 'expired')]:
            result = date_window(start, end, as_of=now, active=False)
            self.assertEqual(expected, result['Status'])
            self.assertFalse(result['IsActive'])
            self.assertEqual('not_assessed', result['AccountUnlock'])

    def test_placeholder_unbounded_and_invalid_are_distinct(self):
        now = '2026-09-09T00:00:00Z'
        for start, end, expected in [
            ('3001-01-01T00:00:00Z', '9999-01-01T00:00:00Z', 'unreleased_placeholder'),
            ('2001-01-01T00:00:00Z', '9999-01-01T00:00:00Z', 'within_window'),
            ('2001-01-01T00:00:00Z', '3001-01-01T00:00:00Z', 'unreleased_placeholder'),
            (None, None, 'unknown'),
            ('2026-09-09', '2026-09-10', 'unknown'),
            ('invalid', 'invalid', 'unknown'),
            ('2026-09-10T00:00:00Z', '2026-09-09T00:00:00Z', 'unknown'),
        ]:
            self.assertEqual(expected, date_window(start, end, as_of=now)['Status'])
        with self.assertRaises(ValueError):
            assessment_time('2026-09-09')


if __name__ == '__main__':
    unittest.main()
