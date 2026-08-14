import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
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


class _RecordingBirthdayDomain:
    calls = []

    @classmethod
    def run(cls, session=None, target_year=None, target_cycle=None):
        cls.calls.append((session, target_year, target_cycle))


class _RejectingBirthdayDomain:
    @staticmethod
    def run(session=None, target_year=None, target_cycle=None):
        raise ValueError("synthetic birthday option failure")


class _RecordingCardUpdateDomain:
    calls = []

    @classmethod
    def run(cls, old_workbook, audio_dir=None, session=None):
        cls.calls.append((old_workbook, audio_dir, session))


class _Assessment:
    errors = []


class _Session:
    assessment = _Assessment()

    def __init__(self):
        self.audit_calls = []

    def write_audit(self, domain_results, *, started_at, success):
        self.audit_calls.append((domain_results, success))


class CliTests(unittest.TestCase):
    def test_doctor_json_reports_registered_runtime(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = cli.cmd_doctor(as_json=True)

        report = json.loads(stream.getvalue())
        self.assertTrue(result)
        self.assertEqual("PASS", report["status"])
        self.assertIn("cards", report["domains"])
        self.assertIn("tkinter", {item["name"] for item in report["dependencies"]})

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

    def test_birthday_accepts_year_and_cycle_overrides(self):
        session = _Session()
        _RecordingBirthdayDomain.calls = []
        with patch.dict(cli.DOMAINS, {"birthday": _RecordingBirthdayDomain}, clear=True):
            with patch.object(cli, "prepare_masterdata", return_value="master_data.json"):
                with patch.object(cli.MasterDataSession, "open", return_value=session):
                    result = cli.cmd_run("birthday", ["--year", "2026", "--cycle", "3"])

        self.assertTrue(result)
        self.assertEqual([(session, 2026, 3)], _RecordingBirthdayDomain.calls)
        self.assertTrue(session.audit_calls[-1][1])

    def test_birthday_rejects_unknown_options(self):
        session = _Session()
        output = io.StringIO()
        with patch.dict(cli.DOMAINS, {"birthday": _RecordingBirthdayDomain}, clear=True):
            with patch.object(cli, "prepare_masterdata", return_value="master_data.json"):
                with patch.object(cli.MasterDataSession, "open", return_value=session):
                    with redirect_stdout(output):
                        result = cli.cmd_run("birthday", ["--unknown", "3"])

        self.assertFalse(result)
        self.assertIn("未知参数", output.getvalue())

    def test_birthday_validation_failure_is_recorded(self):
        session = _Session()
        output = io.StringIO()
        with patch.dict(cli.DOMAINS, {"birthday": _RejectingBirthdayDomain}, clear=True):
            with patch.object(cli, "prepare_masterdata", return_value="master_data.json"):
                with patch.object(cli.MasterDataSession, "open", return_value=session):
                    with redirect_stdout(output):
                        result = cli.cmd_run("birthday", ["--cycle", "3"])

        self.assertFalse(result)
        self.assertIn("参数错误", output.getvalue())
        self.assertFalse(session.audit_calls[-1][1])

    def test_card_update_passes_old_workbook_and_audio_directory(self):
        session = _Session()
        _RecordingCardUpdateDomain.calls = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_workbook = root / "old.xlsx"
            old_workbook.touch()
            audio = root / "Musics"
            audio.mkdir()
            with patch.dict(
                cli.DOMAINS,
                {"card_update": _RecordingCardUpdateDomain},
                clear=True,
            ):
                with patch.object(cli, "prepare_masterdata", return_value="master_data.json"):
                    with patch.object(cli.MasterDataSession, "open", return_value=session):
                        result = cli.cmd_update_cards(str(old_workbook), str(audio))

        self.assertTrue(result)
        self.assertEqual(
            [(str(old_workbook), str(audio), session)],
            _RecordingCardUpdateDomain.calls,
        )
        self.assertTrue(session.audit_calls[-1][1])


if __name__ == "__main__":
    unittest.main()
