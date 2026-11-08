import unittest

from toolkit.core.skill_text import SkillTextRenderer, skill_values
from toolkit.core.tables import TableCatalog


TABLES = {
    "mst_text": [
        {"Id": 100014, "Text": "本部"},
        {"Id": 100115, "Text": "サン属性"},
        {"Id": 100118, "Text": "シングルコンボピース"},
        {"Id": 100132, "Text": "緑ひらめきピース"},
        {"Id": 100136, "Text": "大"},
    ],
    "mst_piece_info": [{"PieceInfoId": 2, "Name": "桃色ピース"}, {"PieceInfoId": 3, "Name": "空色ピース"}],
    "mst_character": [{"CharacterId": 1, "CharacterNameJpn": "皇坂逢"}],
}


def renderer(**kwargs):
    names = list(TABLES)
    return SkillTextRenderer(TableCatalog([{name: None for name in names}] + [TABLES[n] for n in names]), **kwargs)


class SkillTextTests(unittest.TestCase):
    def test_missing_values_are_zero_like_the_client_uint_arguments(self):
        values = skill_values({"SkillValue2": 5, "SkillValue3": 30})

        self.assertEqual("0 / 5 / 30", renderer().parse("skill_value1 / skill_value2 / skill_value3", values))

    def test_each_piece_placeholder_uses_its_own_skill_value(self):
        text = renderer().parse("text:{さらにpiece_value1piece_value2を4個消す！}", [2, 3, 0, 0, 0, 0])

        self.assertEqual("さらに桃色ピース空色ピースを4個消す！", text)

    def test_wiki_piece_labels_override_piece_info_names(self):
        text = renderer(piece_labels={2: "サンピース（桃色）"}).wiki_text(
            "piece_value1を2個作る！", {"SkillValue1": 2}
        )

        self.assertEqual("サンピース（桃色）を2個作る！", text)

    def test_labels_come_from_mst_text_and_characters(self):
        text = renderer().parse(
            "group_value1 attribute_value2 character_value3 strength_value4 combopiece_1 hiramekipiece_6",
            [1, 1, 1, 3, 0, 0],
        )

        self.assertEqual("本部 サン属性 皇坂逢 大 シングルコンボピース 緑ひらめきピース", text)

    def test_tags_are_replaced_by_the_first_match_like_the_client(self):
        self.assertEqual("A と A", renderer().parse("text:{A} と text:{B}", [0] * 6))
        self.assertEqual("x2", renderer().parse("combo:{x2}", [0] * 6))

    def test_unknown_labels_are_empty_and_reported(self):
        subject = renderer()

        self.assertEqual("を消す", subject.parse("piece_value1を消す", [9, 0, 0, 0, 0, 0]))
        self.assertEqual({("piece_value", 9)}, subject.unresolved)

    def test_wiki_text_turns_attribute_sprites_into_words(self):
        text = renderer().wiki_text(
            "<sprite name=piece_1><sprite name=piece_2>の出現確率がstrength_value3アップ！", {"SkillValue3": 3}
        )

        self.assertEqual("サンピースの出現確率が大アップ！", text)


if __name__ == "__main__":
    unittest.main()
