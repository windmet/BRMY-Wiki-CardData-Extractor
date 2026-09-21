"""Windows-safe UTF-8 console configuration for CLI entry points."""
import sys


def safe_print(message, *, file=None):
    """Print status text without failing on legacy Windows code pages."""
    stream = file or sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    safe_message = str(message).encode(encoding, errors="replace").decode(encoding)
    print(safe_message, file=stream)


def configure_console():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not reconfigure:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
