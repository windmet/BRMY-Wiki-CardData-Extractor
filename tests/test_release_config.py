import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def package_name(requirement):
    return re.split(r"[<>=!~\[]", requirement, maxsplit=1)[0].strip().lower()


class ReleaseConfigTests(unittest.TestCase):
    def test_release_lock_covers_every_runtime_dependency(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        runtime = {
            package_name(requirement)
            for requirement in project["project"]["dependencies"]
        }
        release_lines = [
            line.strip()
            for line in (ROOT / "requirements" / "release-build.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        release = {package_name(requirement): requirement for requirement in release_lines}

        self.assertEqual(set(), runtime - release.keys())
        self.assertTrue(all("==" in requirement for requirement in release_lines))
        self.assertEqual("Nuitka==4.1.2", release["nuitka"])
        self.assertEqual("zstandard==0.25.0", release["zstandard"])

    def test_python_and_nuitka_pins_match_build_workflow(self):
        script = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "build-release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn('$expectedPython = "3.12.9"', script)
        self.assertIn('$expectedNuitka = "4.1.2"', script)
        self.assertIn('python-version: "3.12.9"', workflow)
        self.assertIn("github.event.pull_request.head.sha || github.sha", workflow)


class SmokeMarkerTests(unittest.TestCase):
    def test_smoke_list_markers_are_printed_by_the_list_command(self):
        import contextlib
        import io

        from toolkit.cli import cmd_list

        script = (ROOT / "scripts" / "smoke_release.ps1").read_text(encoding="utf-8")
        markers = re.search(r'foreach \(\$marker in @\(([^)]*)\)\)', script).group(1)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            cmd_list()
        for marker in re.findall(r'"([^"]+)"', markers):
            self.assertIn(marker, output.getvalue())


if __name__ == "__main__":
    unittest.main()
