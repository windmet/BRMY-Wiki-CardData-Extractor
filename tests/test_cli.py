import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from toolkit import cli


class _FailingDomain:
    @staticmethod
    def run(session=None):
        raise RuntimeError("synthetic failure")


class _RecordingDomain:
    sessions = []

    @classmethod
    def run(cls, session=None):
        cls.sessions.append(session)


class _Assessment:
    errors = []


class _Session:
    assessment = _Assessment()

    def __init__(self):
        self.audit_calls = []

    def write_audit(self, domain_results, *, started_at, success):
        self.audit_calls.append((domain_results, success))


class CliTests(unittest.TestCase):
    def test_all_returns_failure_when_any_domain_fails(self):
        output = io.StringIO()
        session = _Session()
        with patch.dict(cli.DOMAINS, {"cards": _FailingDomain}, clear=True):
            with patch.object(cli, "prepare_masterdata", return_value="master_data.json"):
                with patch.object(cli.MasterDataSession, "open", return_value=session):
                    with redirect_stdout(output):
                        result = cli.cmd_all()

        self.assertFalse(result)
        self.assertIn("cards: synthetic failure", output.getvalue())
        self.assertFalse(session.audit_calls[-1][1])

    def test_main_exits_nonzero_when_all_fails(self):
        with patch.object(cli.sys, "argv", ["toolkit", "all"]):
            with patch.object(cli, "cmd_all", return_value=False):
                with self.assertRaisesRegex(SystemExit, "1"):
                    cli.main()

    def test_main_exits_nonzero_when_decrypt_input_is_missing(self):
        with patch.object(cli.sys, "argv", ["toolkit", "decrypt"]):
            with patch.object(cli, "cmd_decrypt", return_value=False):
                with self.assertRaisesRegex(SystemExit, "1"):
                    cli.main()

    def test_all_passes_one_session_to_domains_and_records_success(self):
        session = _Session()
        _RecordingDomain.sessions = []
        with patch.dict(cli.DOMAINS, {"cards": _RecordingDomain}, clear=True):
            with patch.object(cli, "prepare_masterdata", return_value="master_data.json"):
                with patch.object(cli.MasterDataSession, "open", return_value=session):
                    result = cli.cmd_all()

        self.assertTrue(result)
        self.assertEqual([session], _RecordingDomain.sessions)
        self.assertTrue(session.audit_calls[-1][1])

    def test_all_blocks_before_domains_when_required_schema_is_missing(self):
        session = _Session()
        session.assessment = type(
            "Assessment", (), {"errors": ["required field is missing"]}
        )()
        _RecordingDomain.sessions = []
        with patch.dict(cli.DOMAINS, {"cards": _RecordingDomain}, clear=True):
            with patch.object(cli, "prepare_masterdata", return_value="master_data.json"):
                with patch.object(cli.MasterDataSession, "open", return_value=session):
                    result = cli.cmd_all()

        self.assertFalse(result)
        self.assertEqual([], _RecordingDomain.sessions)
        self.assertFalse(session.audit_calls[-1][1])


if __name__ == "__main__":
    unittest.main()
