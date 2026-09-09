import unittest

from toolkit.domains.event_classification import classify_event


class EventClassificationTests(unittest.TestCase):
    def test_making_formats_share_family_but_keep_subtype_and_code(self):
        normal = classify_event({'EventFormat': 3})
        special = classify_event({'EventFormat': 4})
        self.assertEqual(normal['Family'], special['Family'])
        self.assertNotEqual(normal['Subtype'], special['Subtype'])
        self.assertEqual(4, special['EventFormat'])

    def test_type_code_is_authoritative_and_title_prefix_only_refines_travel(self):
        for title, expected in [('Prequel Example', 'prequel'),
                                ('Travelogue Example', 'travelogue'),
                                ('Another name', 'travel_prequel')]:
            result = classify_event({'EventFormat': 2, 'EventTitle': title}, {'EventAType': 2})
            self.assertEqual(expected, result['Subtype'])
        result = classify_event({'EventFormat': 2, 'EventTitle': 'Prequel Example'}, {'EventAType': 5})
        self.assertEqual('anniversary', result['Subtype'])
        self.assertNotIn('EventTitle prefix', result['Basis'])

    def test_unknown_discriminators_remain_explicit(self):
        for event, extension in [({'EventFormat': 77}, {}),
                                 ({'EventFormat': 2}, {'EventAType': 99}),
                                 ({'EventFormat': 2}, None)]:
            self.assertEqual('unknown', classify_event(event, extension)['Status'])
        self.assertEqual('special', classify_event({'EventFormat': 2}, {'EventAType': 4})['Subtype'])


if __name__ == '__main__':
    unittest.main()
