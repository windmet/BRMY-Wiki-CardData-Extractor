import unittest

from toolkit.core.tables import TableCatalog
from toolkit.domains.cards import CARD_TABLES, _build_cards, _build_lookups


def catalog(tables):
    names = [name for name, _ in CARD_TABLES] + [
        'mst_home_voice', 'mst_item', 'mst_character', 'mst_sp_skill_effect', 'mst_notice',
        'mst_auto_skill_effect', 'mst_combination_effect', 'mst_leader_skill_effect',
        'mst_character_card_story_section', 'mst_gacha',
    ]
    return TableCatalog([{name: None for name in names}] + [tables.get(name, []) for name in names])


class CardBuildTests(unittest.TestCase):
    def setUp(self):
        self.tables = catalog({
            'mst_item': [{'ItemId': 7, 'ItemName': '砂時計'}],
            'mst_character': [{'CharacterId': 1, 'CharacterNameJpn': '皇坂逢'}],
            'mst_leader_skill_effect': [
                {'LeaderSkillEffectId': 2, 'SkillEffect': 'VisualUp', 'SkillDescription': 'skill_value1%UP'},
            ],
            'mst_character_card': [{'CharacterCardId': 1, 'CharacterCardName': 'A', 'CharacterId': 1}],
            'mst_character_card_leader_skill': [
                {'CharacterCardId': 1, 'LeaderSkillEffectId': 2, 'SkillValue1': 5},
            ],
            'mst_item_card_revision': [{
                'CharacterCardId': 1, 'RevisionRank': 1,
                'CostItemId1': 7, 'CostItemCount1': 3, 'CostItemId2': 0, 'CostItemCount2': 0,
            }],
            'mst_item_card_sp_skill_level_up': [
                {'CharacterCardId': 1, 'SpSkillLevel': 2, 'CostItemId1': 8, 'CostItemCount1': 1},
            ],
        })

    def build(self):
        return _build_cards(self.tables, _build_lookups(self.tables))[1]

    def test_upgrade_costs_read_cost_item_columns(self):
        costs = self.build()["UpgradeCosts"]

        self.assertEqual([{"Item": "砂時計", "Count": 3}], costs["Revision"]["Rank1"])
        self.assertEqual([{"Item": "Item_8", "Count": 1}], costs["SpSkill"]["Lv2"])

    def test_leader_skill_name_falls_back_to_skill_effect(self):
        leader = self.build()["LeaderSkill"]

        self.assertEqual({"Name": "VisualUp", "Desc": "5%UP"}, leader)


if __name__ == "__main__":
    unittest.main()
