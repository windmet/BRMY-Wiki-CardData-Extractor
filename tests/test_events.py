import json
import os
import tempfile
import unittest
from pathlib import Path

from toolkit.core.session import MasterDataSession
from toolkit.domains.events import _resolve_reward, extract


class EventRewardTests(unittest.TestCase):
    def setUp(self):
        self.maps = {
            "cards": {426: "Vignette -Emperor-"},
            "items": {506: "Bookmark"},
            "ingredients": {},
            "titles": {},
            "pins": {},
            "home_voice_products": {},
        }

    def test_reward_type_one_is_character_card(self):
        reward = _resolve_reward(
            {"RewardTypeCode": 1, "RewardTargetId": 426, "RewardCount": 1},
            self.maps,
        )

        self.assertEqual("card", reward["RewardType"])
        self.assertEqual("Vignette -Emperor-", reward["RewardName"])

    def test_reward_type_two_is_item(self):
        reward = _resolve_reward(
            {"RewardTypeCode": 2, "RewardTargetId": 506, "RewardCount": 10},
            self.maps,
        )

        self.assertEqual("item", reward["RewardType"])
        self.assertEqual("Bookmark", reward["RewardName"])

    def test_extract_uses_named_event_table_and_allows_missing_extensions(self):
        data = [
            {"decoy_event": [0, 0], "mst_event": [0, 0]},
            [{"EventId": 999, "EventTitle": "Wrong Event", "IsActive": True}],
            [{
                "EventId": 1, "EventTitle": "Right Event", "EventFormat": 1,
                "IsActive": True,
            }],
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "master_data.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            session = MasterDataSession.open(path, required_schema={})
            previous = os.getcwd()
            os.chdir(root)
            try:
                archive = extract(session=session)
            finally:
                os.chdir(previous)

        self.assertEqual([1], [event["EventId"] for event in archive])
        self.assertEqual("Right Event", archive[0]["Title"])


if __name__ == "__main__":
    unittest.main()
