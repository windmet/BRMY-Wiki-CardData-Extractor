import os
import tempfile
import unittest
from pathlib import Path

from toolkit.domains.audio import (
    _scan_all_text_metadata,
    extract_text_metadata,
    scan_card_voices,
    text_to_html,
)
from toolkit.core.cri_utf import CriUtfError, parse_utf


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


if __name__ == "__main__":
    unittest.main()
