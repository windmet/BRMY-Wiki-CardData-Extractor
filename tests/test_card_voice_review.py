import unittest

from toolkit.domains.card_voice_review import build


def cue(name, text=None, raw=None):
    return {'CueName': name, 'UserData': raw if raw is not None else f'title:{{t}}text:{{{text}}}'}


CARDS = {
    418: {'CharacterCardName': 'A', 'CharacterId': 8, 'ReleaseDateTime': '2026-06-11T13:00:00+00:00'},
    431: {'CharacterCardName': 'B', 'CharacterId': 4, 'ReleaseDateTime': '2026-07-06T14:00:00+00:00'},
    432: {'CharacterCardName': 'C', 'CharacterId': 15, 'ReleaseDateTime': '2026-07-06T14:00:00+00:00'},
}


class ReviewTests(unittest.TestCase):
    def test_cross_card_reuse_marks_earliest_release_as_first(self):
        scanned = {cid: [cue('card_vo_skill', '結婚、か')] for cid in (418, 431, 432)}
        entries, _ = build(scanned, CARDS)
        kinds = {e['CharacterCardId']: e['Kind'] for e in entries}
        self.assertEqual({418: 'reused_first', 431: 'reused_copy', 432: 'reused_copy'}, kinds)
        self.assertEqual([418, 432], next(e for e in entries if e['CharacterCardId'] == 431)['RelatedCardIds'])

    def test_line_breaks_do_not_hide_reuse(self):
        scanned = {418: [cue('card_vo_skill', 'あ\\nい')], 431: [cue('card_vo_skill', 'あい')]}
        entries, _ = build(scanned, CARDS)
        self.assertEqual(2, len(entries))

    def test_gacha_cues_are_skipped_entirely(self):
        scanned = {418: [cue('card_vo_gacha', ''), cue('card_vo_home_1', '同じ'), cue('card_vo_gacha', '同じ')],
                   431: [cue('card_vo_gacha', '同じ')]}
        entries, skipped = build(scanned, CARDS)
        self.assertEqual(([], 3), (entries, skipped))

    def test_empty_malformed_and_same_card_duplicates(self):
        scanned = {418: [cue('card_vo_skill', ''), cue('card_vo_home_1', 'x'), cue('card_vo_home_2', 'x'),
                         cue('card_vo_skill_combi', raw='title:{コンビボイス}text:{}壊れた')]}
        entries, _ = build(scanned, CARDS)
        self.assertEqual(
            [('card_vo_home_1', 'same_card_duplicate'), ('card_vo_home_2', 'same_card_duplicate'),
             ('card_vo_skill', 'empty_text'), ('card_vo_skill_combi', 'malformed_metadata')],
            sorted((e['CueName'], e['Kind']) for e in entries))
        malformed = next(e for e in entries if e['Kind'] == 'malformed_metadata')
        self.assertIn('壊れた', malformed['RawUserData'])

    def test_unique_texts_produce_no_entries(self):
        scanned = {418: [cue('card_vo_skill', '一')], 431: [cue('card_vo_skill', '二')]}
        self.assertEqual([], build(scanned, CARDS)[0])


if __name__ == '__main__':
    unittest.main()
