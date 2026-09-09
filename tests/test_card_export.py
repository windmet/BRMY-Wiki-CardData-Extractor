import json
import unittest
from pathlib import Path

from toolkit.domains.card_export import build_card_record
from toolkit.domains.cards import format_skill_desc, scan_card_voices, skill_values


CONTRACTS = json.loads(
    (Path(__file__).parent / "fixtures" / "card_contracts.json").read_text(encoding="utf-8")
)["export"]


def export_contract(name):
    case = CONTRACTS[name]
    return build_card_record(case["card_id"], case["card"]), case["expected"]


class CardExportTests(unittest.TestCase):
    def test_sparse_skill_values_keep_their_original_placeholder_indexes(self):
        values = skill_values({"SkillValue2": 5, "SkillValue3": 30}, 3)

        result = format_skill_desc(
            "skill_value1 / skill_value2 / skill_value3", values
        )

        self.assertEqual("skill_value1 / 5 / 30", result)

    def test_cards_uses_package_relative_audio_module(self):
        self.assertEqual("toolkit.domains.audio", scan_card_voices.__module__)

    def test_cr_card_preserves_both_characters_and_distinct_skill_voices(self):
        record, expected = export_contract("cr_partner_voices")
        self.assertEqual(expected, {key: record[key] for key in expected})

    def test_standard_combi_voice_is_not_treated_as_partner_skill(self):
        record, expected = export_contract("standard_combi")
        self.assertEqual(expected, {key: record[key] for key in expected})


if __name__ == "__main__":
    unittest.main()
