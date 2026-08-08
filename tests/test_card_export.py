import json
import unittest
from pathlib import Path

from toolkit.domains.card_export import build_card_record


CONTRACTS = json.loads(
    (Path(__file__).parent / "fixtures" / "card_contracts.json").read_text(encoding="utf-8")
)["export"]


def export_contract(name):
    case = CONTRACTS[name]
    return build_card_record(case["card_id"], case["card"]), case["expected"]


class CardExportTests(unittest.TestCase):
    def test_cr_card_preserves_both_characters_and_distinct_skill_voices(self):
        record, expected = export_contract("cr_partner_voices")
        self.assertEqual(expected, {key: record[key] for key in expected})

    def test_standard_combi_voice_is_not_treated_as_partner_skill(self):
        record, expected = export_contract("standard_combi")
        self.assertEqual(expected, {key: record[key] for key in expected})


if __name__ == "__main__":
    unittest.main()
