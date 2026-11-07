import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from toolkit.core.tables import TableCatalog
from toolkit.domains.system_voices import extract


class SystemVoiceTests(unittest.TestCase):
    def test_type3_does_not_enter_staff_and_fallback_is_not_verified_text(self):
        tables = TableCatalog([{'mst_home_voice': [], 'mst_character': []}, [
            {'HomeVoiceTypeCode': 1, 'HomeVoiceTargetId': 1, 'VoiceCueName': 'vo_dl'},
            {'HomeVoiceTypeCode': 3, 'HomeVoiceTargetId': 24, 'VoiceCueName': 'vo_dl'}],
            [{'CharacterId': 24, 'CharacterNameJpn': 'レア'}]])
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'voice_rare_general.acb').write_bytes(b'fixture')
            for status in ('matched_by_title_fallback', 'matched_by_acb_utf'):
                with patch('toolkit.domains.system_voices.extract_text_metadata', return_value=([
                    {'CueName': 'vo_dl', 'MatchStatus': status, 'Text': 'text'}], True)):
                    data = extract(tables, root)
                self.assertEqual(1, len(data['Records']))
                self.assertEqual('not_applicable', data['StaffCompleteness'])
                self.assertEqual('resolved' if status == 'matched_by_acb_utf' else 'missing_cue_text', data['Records'][0]['Status'])
