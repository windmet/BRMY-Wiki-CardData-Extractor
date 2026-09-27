import unittest

from toolkit.domains.home_voices import _conditions_sheet


class VoiceConditionsTests(unittest.TestCase):
    def test_global_and_character_windows_stay_separate_and_midnight_is_preserved(self):
        record = {'SubjectDisplayName': 'Subject', 'SpeakerCharacterName': 'Character',
                  'GlobalLimitedName': 'Name', 'StartTime': 'character-start', 'EndTime': 'character-end',
                  'GlobalLimitedRecords': [{'StartTime': 'global-start', 'EndTime': 'global-end'}],
                  'TimeDivisionRecords': [{'TimeDivisionName': 'night', 'StartHour': 0, 'StartMinutes': 0,
                                           'EndHour': 5, 'EndMinutes': 59}]}
        row = _conditions_sheet([record])['rows'][0]
        self.assertEqual(['character-start', 'character-end', 'global-start', 'global-end'], row[3:7])
        self.assertEqual(['night', '00:00', '05:59'], row[7:])


if __name__ == '__main__':
    unittest.main()
