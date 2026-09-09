import importlib.metadata
import types
import unittest

from toolkit.core.doctor import REQUIRED_DOMAINS, build_doctor_report


class DoctorTests(unittest.TestCase):
    @staticmethod
    def importer(name):
        if name == "tkinter":
            return types.SimpleNamespace(TkVersion=8.6)
        return types.SimpleNamespace(__version__="module-version")

    @staticmethod
    def version_reader(name):
        versions = {
            "lz4": "4.4.5",
            "msgpack": "1.1.2",
            "mutagen": "1.47.0",
            "openpyxl": "3.1.5",
        }
        if name not in versions:
            raise importlib.metadata.PackageNotFoundError(name)
        return versions[name]

    def test_complete_runtime_reports_pass(self):
        report = build_doctor_report(
            REQUIRED_DOMAINS,
            importer=self.importer,
            version_reader=self.version_reader,
        )

        self.assertEqual("PASS", report["status"])
        self.assertEqual([], report["missing_domains"])
        self.assertEqual(5, len(report["dependencies"]))
        self.assertTrue(all(item["status"] == "PASS" for item in report["dependencies"]))

    def test_missing_domain_and_dependency_report_fail(self):
        def failing_importer(name):
            if name == "lz4.block":
                raise ImportError("synthetic missing module")
            return self.importer(name)

        report = build_doctor_report(
            REQUIRED_DOMAINS - {"cards"},
            importer=failing_importer,
            version_reader=self.version_reader,
        )

        self.assertEqual("FAIL", report["status"])
        self.assertEqual(["cards"], report["missing_domains"])
        self.assertEqual("FAIL", report["dependencies"][0]["status"])


if __name__ == "__main__":
    unittest.main()
