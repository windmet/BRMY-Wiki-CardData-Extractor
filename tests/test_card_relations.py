import json
import unittest
from pathlib import Path

from toolkit.domains.card_relations import _derive_acquisition, _serial_present_relations
from toolkit.core.tables import TableCatalog


CONTRACTS = json.loads(
    (Path(__file__).parent / "fixtures" / "card_contracts.json").read_text(encoding="utf-8")
)["acquisition"]


def derive_contract(name):
    case = CONTRACTS[name]
    result = _derive_acquisition(
        case["card_id"],
        case["raw"],
        case["events"],
        case["gachas"],
        case["exchanges"],
        case["reward_groups"],
    )
    return result, case["expected"]


class CardAcquisitionTests(unittest.TestCase):
    def test_serial_present_uses_typed_reward_and_preserves_all_sources(self):
        tables = {
            'mst_character_card': [{'CharacterCardId': 800, 'CharacterCardName': 'unrelated card name'}],
            'mst_item': [{'ItemId': 800, 'ItemName': 'not a card'}],
            'mst_present_serial_code': [{'PresentId': 15}, {'PresentId': 16}, {'PresentId': 17, 'IsActive': False}],
            'mst_present': [
                {'PresentId': 15, 'PresentSequenceNo': 1, 'RewardTypeCode': 1, 'RewardTargetId': 800, 'RewardCount': 1, 'PresentDescription': 'bonus A'},
                {'PresentId': 15, 'PresentSequenceNo': 2, 'RewardTypeCode': 2, 'RewardTargetId': 800},
                {'PresentId': 16, 'PresentSequenceNo': 1, 'RewardTypeCode': 1, 'RewardTargetId': 800, 'PresentDescription': 'bonus B'},
                {'PresentId': 17, 'PresentSequenceNo': 1, 'RewardTypeCode': 1, 'RewardTargetId': 800},
                {'PresentId': 16, 'PresentSequenceNo': 2, 'RewardTypeCode': 1, 'RewardTargetId': 800, 'IsActive': False},
            ],
            'mst_direct_reward': [{'DirectRewardGroupId': 15, 'RewardTypeCode': 1, 'RewardTargetId': 900}],
        }
        relations, audit = _serial_present_relations(TableCatalog([dict.fromkeys(tables, [])] + list(tables.values())))
        self.assertEqual([800], list(relations))
        self.assertEqual([15, 16], [r['PresentId'] for r in relations[800]])
        self.assertEqual(2, len(audit['SerialPresents']))
        result = _derive_acquisition(800, {'CardRouteCode': 2}, [], [], [], [], relations[800])
        self.assertEqual('序列码兑换', result['Method'])
        self.assertEqual('bonus A / bonus B', result['SourceName'])
        self.assertEqual([], result['Warnings'])
        self.assertEqual(2, len([r for r in result['Evidence'] if r['Kind'] == 'serial_present']))

    def test_serial_evidence_does_not_replace_established_gacha_source(self):
        result = _derive_acquisition(800, {'CardRouteCode': 1}, [],
                                     [{'GachaNames': ['original gacha']}], [], [],
                                     [{'PresentId': 15, 'PresentDescription': 'later bonus'}])
        self.assertEqual('original gacha', result['SourceName'])
        self.assertTrue(any(r['Kind'] == 'serial_present' for r in result['Evidence']))

    def test_missing_present_or_target_remains_auditable(self):
        tables = {'mst_present_serial_code': [{'PresentId': 10}, {'PresentId': 11}],
                  'mst_present': [{'PresentId': 10, 'RewardTypeCode': 1, 'RewardTargetId': 800}],
                  'mst_character_card': []}
        relations, audit = _serial_present_relations(TableCatalog([dict.fromkeys(tables, [])] + list(tables.values())))
        self.assertFalse(relations)
        self.assertEqual({'missing_target', 'missing_reward_group'}, {r['Resolution'] for r in audit['Issues']})

    def test_serial_without_description_does_not_claim_source_complete(self):
        result = _derive_acquisition(800, {'CardRouteCode': 2}, [], [], [], [], [{'PresentId': 15}])
        self.assertEqual('序列码兑换', result['Method'])
        self.assertTrue(result['Warnings'])

    def test_event_reward_uses_pickup_event(self):
        result, expected = derive_contract("event_reward")
        self.assertEqual(expected, {key: result[key] for key in expected})

    def test_exchange_reward_is_resolved_without_event(self):
        result, expected = derive_contract("exchange_reward")
        self.assertEqual(expected, {key: result[key] for key in expected})

    def test_unresolved_card_does_not_affect_following_cards(self):
        unknown = _derive_acquisition(500, {"CardRouteCode": 9}, [], [], [], [])
        known = _derive_acquisition(1, {"CardRouteCode": 1}, [], [], [], [])

        self.assertTrue(unknown["Warnings"])
        self.assertEqual("常驻", known["Method"])

    def test_initial_permanent_card_is_not_reclassified_by_reissue_gacha(self):
        result, expected = derive_contract("initial_permanent")
        self.assertEqual(expected, {key: result[key] for key in expected})


if __name__ == "__main__":
    unittest.main()
