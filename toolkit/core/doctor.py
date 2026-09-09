"""Runtime self-checks shared by source installs and frozen executables."""
from __future__ import annotations

import importlib
import importlib.metadata
import platform
import sys


REQUIRED_MODULES = (
    ("lz4.block", "lz4"),
    ("msgpack", "msgpack"),
    ("mutagen", "mutagen"),
    ("openpyxl", "openpyxl"),
    ("tkinter", None),
)

REQUIRED_DOMAINS = {
    "audio", "birthday", "cards", "card_update", "charts", "events",
    "home_voices", "items", "lyrics", "missions", "music", "recipes",
    "scripts", "snap",
}


def _module_version(module, distribution, version_reader):
    if distribution:
        try:
            return version_reader(distribution)
        except importlib.metadata.PackageNotFoundError:
            pass
    return str(getattr(module, "__version__", "bundled"))


def build_doctor_report(
    domain_names,
    *,
    importer=importlib.import_module,
    version_reader=importlib.metadata.version,
):
    checks = []
    for module_name, distribution in REQUIRED_MODULES:
        try:
            module = importer(module_name)
            version = _module_version(module, distribution, version_reader)
            if module_name == "tkinter":
                version = str(getattr(module, "TkVersion", version))
            checks.append({
                "name": module_name,
                "status": "PASS",
                "version": version,
            })
        except Exception as error:
            checks.append({
                "name": module_name,
                "status": "FAIL",
                "error": f"{type(error).__name__}: {error}",
            })

    available_domains = sorted(set(domain_names))
    missing_domains = sorted(REQUIRED_DOMAINS - set(available_domains))
    status = "PASS" if not missing_domains and all(
        check["status"] == "PASS" for check in checks
    ) else "FAIL"
    return {
        "schema_version": 1,
        "status": status,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "executable": sys.executable,
        "frozen": bool(getattr(sys, "frozen", False) or "__compiled__" in globals()),
        "dependencies": checks,
        "domains": available_domains,
        "missing_domains": missing_domains,
    }
