import unittest
from types import SimpleNamespace

from toolkit.core.tables import TableCatalog
from toolkit.domains.birthday_archive import extract


class AnnualBirthdayTests(unittest.TestCase):
    def test_year_is_part_of_key_and_present_is_not_direct_reward(self):
        tables = {
            'mst_character_birthday': [{'CharacterId': 1, 'Year': 2025, 'TapRewardNo1': 7}, {'CharacterId': 1, 'Year': 2026}],
            'mst_character_birthday_login_bonus_sequence': [{'CharacterId': 1, 'Year': 2026, 'Sequence': 1, 'PresentId': 7}],
            'mst_direct_reward': [{'DirectRewardGroupId': 7, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 3}],
            'mst_present': [{'PresentId': 7, 'RewardTypeCode': 2, 'RewardTargetId': 1, 'RewardCount': 9}],
            'mst_item': [{'ItemId': 1, 'ItemName': 'Item'}],
            'mst_character_birthday_mini_game_text': [{'CharacterId': 2, 'Year': 2026, 'Text': 'Orphan'}],
        }
        data = extract(SimpleNamespace(tables=TableCatalog([dict.fromkeys(tables, []), *tables.values()])), as_of='2026-09-09T00:00:00Z')
        old, new = data['Birthdays']
        self.assertEqual([], old['LoginRewards'])
        self.assertEqual(3, old['TapRewards'][0]['Rewards'][0]['RewardCount'])
        self.assertEqual(9, new['LoginRewards'][0]['Rewards'][0]['RewardCount'])
        self.assertEqual([], new['Texts'])
        self.assertEqual('orphan_birthday_relation', data['Issues'][0]['Status'])


if __name__ == '__main__':
    unittest.main()
