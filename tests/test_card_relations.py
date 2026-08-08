import json
import unittest
from pathlib import Path

from toolkit.domains.card_relations import _derive_acquisition


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
