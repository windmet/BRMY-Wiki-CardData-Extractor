import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toolkit.core import scanner
from toolkit.core.session import (
    MasterDataSession,
    build_schema_snapshot,
)
from toolkit.core.tables import TableCatalog


def _write_data(path, rows):
    data = [{"mst_sample": [0, 0]}, rows]
    path.write_text(json.dumps(data), encoding="utf-8")


class MasterDataSessionTests(unittest.TestCase):
    def test_open_loads_json_once_and_exposes_named_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "master_data.json"
            _write_data(path, [{"Id": 1, "Name": "A"}])

            with patch.object(scanner, "load_json", wraps=scanner.load_json) as load:
                session = MasterDataSession.open(
                    path, required_schema={"mst_sample": {"Id", "Name"}}
                )

            self.assertEqual(1, load.call_count)
            self.assertEqual(1, session.tables.rows("mst_sample")[0]["Id"])
            self.assertFalse(session.assessment.errors)

    def test_schema_fingerprint_ignores_row_count_only_changes(self):
        one = TableCatalog([{"mst_sample": 0}, [{"Id": 1, "Name": "A"}]])
        two = TableCatalog([
            {"mst_sample": 0},
            [{"Id": 1, "Name": "A"}, {"Id": 2, "Name": "B"}],
        ])

        self.assertEqual(
            build_schema_snapshot(one)["schema_fingerprint"],
            build_schema_snapshot(two)["schema_fingerprint"],
        )

    def test_missing_required_field_blocks_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "master_data.json"
            _write_data(path, [{"Id": 1}])

            session = MasterDataSession.open(
                path, required_schema={"mst_sample": {"Id", "Name"}}
            )

            self.assertEqual("FAIL", session.assessment.status)
            self.assertIn(
                "required field is missing: mst_sample.Name",
                session.assessment.errors,
            )

    def test_successful_run_records_baseline_and_reports_new_field(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "master_data.json"
            contract = {"mst_sample": {"Id", "Name"}}
            _write_data(path, [{"Id": 1, "Name": "A"}])
            first = MasterDataSession.open(path, required_schema=contract)

            manifest = first.write_audit(
                [{"name": "sample", "status": "PASS", "duration_seconds": 0.1}],
                started_at="2026-08-14T00:00:00+00:00",
                success=True,
            )

            self.assertEqual("PASS_WITH_WARNINGS", manifest["status"])
            self.assertIn("version", manifest["tool"])
            self.assertEqual(1, manifest["tool"]["parser_version"])
            self.assertTrue(first.schema_baseline_path.is_file())
            self.assertTrue((root / "audit_output" / "run_manifest.json").is_file())
            self.assertTrue((root / "audit_output" / "schema_report.md").is_file())

            _write_data(path, [{"Id": 1, "Name": "A", "NewField": 3}])
            second = MasterDataSession.open(path, required_schema=contract)

            self.assertEqual("WARN", second.assessment.status)
            self.assertIn(
                {
                    "kind": "field_added",
                    "table": "mst_sample",
                    "field": "NewField",
                },
                second.assessment.changes,
            )

    def test_row_count_change_is_reported_as_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "master_data.json"
            contract = {"mst_sample": {"Id", "Name"}}
            _write_data(path, [{"Id": 1, "Name": "A"}])
            first = MasterDataSession.open(path, required_schema=contract)
            first.write_audit([], started_at="2026-08-14T00:00:00+00:00", success=True)

            _write_data(
                path,
                [{"Id": 1, "Name": "A"}, {"Id": 2, "Name": "B"}],
            )
            second = MasterDataSession.open(path, required_schema=contract)

            self.assertEqual("WARN", second.assessment.status)
            self.assertIn(
                {
                    "kind": "row_count_changed",
                    "table": "mst_sample",
                    "before": 1,
                    "after": 2,
                },
                second.assessment.changes,
            )


if __name__ == "__main__":
    unittest.main()
