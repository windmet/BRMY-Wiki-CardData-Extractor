import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toolkit.domains.audio import (
    _scan_all_text_metadata,
    extract_text_metadata,
    scan_card_voices,
    text_to_html,
    resource_keys,
)
from toolkit.core.cri_utf import CriUtfError, parse_utf
from toolkit.core.tables import TableCatalog


class AudioMetadataTests(unittest.TestCase):
    def test_extracts_card_metadata_and_normalizes_wiki_breaks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice_403.acb"
            path.write_bytes(
                b"binary\x00"
                + "title:{ホームボイス①}text:{一行目\\n二行目}".encode("utf-8")
                + b"\x00"
                + "title:{スキルボイス}text:{了解}".encode("utf-8")
                + b"\x00"
            )

            metadata, stable = extract_text_metadata(path)
            cards, warnings = scan_card_voices(directory)

            self.assertTrue(stable)
            self.assertEqual(2, len(metadata))
            self.assertEqual([], warnings)
            self.assertEqual("card_vo_home_1", cards["403"]["Entries"][0]["CueName"])
            self.assertEqual("一行目<br>二行目", cards["403"]["Entries"][0]["TextHtml"])
            self.assertEqual("card_vo_skill", cards["403"]["Entries"][1]["CueName"])

    def test_text_to_html_handles_literal_and_actual_newlines(self):
        self.assertEqual("a<br>b<br>c", text_to_html("a\\nb\nc"))

    def test_zero_byte_card_is_reported_and_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "voice_1.acb").write_bytes(b"")
            cards, warnings = scan_card_voices(directory)
            self.assertEqual({}, cards)
            self.assertEqual(1, len(warnings))

    def test_all_text_index_keeps_cue_audit_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice_example.acb"
            path.write_bytes(
                b"binary\x00"
                + "title:{季節}text:{一行目\\n二行目}".encode("utf-8")
                + b"\x00"
            )

            records, unstable = _scan_all_text_metadata(directory)

            self.assertEqual([], unstable)
            self.assertEqual(1, len(records))
            self.assertEqual("", records[0]["CueName"])
            self.assertIsNone(records[0]["CueIndex"])
            self.assertIsNone(records[0]["CueId"])
            self.assertEqual("matched_by_title_fallback", records[0]["MatchStatus"])
            self.assertTrue(records[0]["StableRead"])
            self.assertEqual("一行目<br>二行目", records[0]["TextHtml"])

    def test_invalid_utf_is_rejected_for_safe_fallback(self):
        with self.assertRaises(CriUtfError):
            parse_utf(b"not an acb")

    def test_generic_scan_skips_card_packages_and_embedded_card_cues(self):
        with tempfile.TemporaryDirectory() as root:
            for filename in ('voice_403.acb', 'custom_card.acb', 'voice_arima_general.acb'):
                Path(root, filename).write_bytes(b'fixture')
            metadata = [{'CueName': cue, 'Title': 'Title', 'Text': 'Text',
                         'MatchStatus': 'matched_by_acb_utf'}
                        for cue in ('card_vo_home_1', 'card_vo_gacha', 'vo_home_138')]
            with patch('toolkit.domains.audio.extract_text_metadata', return_value=(metadata, True)) as read:
                rows, _ = _scan_all_text_metadata(root, exclude_cards=True, card_names={'custom_card.acb'})
            self.assertEqual(1, read.call_count)
            self.assertEqual(['vo_home_138'], [r['CueName'] for r in rows])

    def test_generic_plan_excludes_standard_and_masterdata_card_packages(self):
        tables = TableCatalog([{'mst_character_card': 0}, [
            {'CharacterCardId': 1, 'VoiceCueSheetName': 'custom_card'}]])
        resources = dict.fromkeys(['Musics/voice_403.acb', 'Musics/custom_card.acb',
                                   'Musics/voice_arima_general.acb'])
        self.assertEqual(['Musics/voice_arima_general.acb'], resource_keys(tables, resources))


if __name__ == "__main__":
    unittest.main()
