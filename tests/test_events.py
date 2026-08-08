import unittest

from toolkit.domains.events import _resolve_reward


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


if __name__ == "__main__":
    unittest.main()
