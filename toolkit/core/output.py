"""Per-run output routing and receipts, without changing the process directory."""
from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import uuid

_current = ContextVar('toolkit_output', default=None)


def current_output():
    return _current.get()


def output_directory(kind, fallback):
    context = current_output()
    path = context.root / {'wiki': 'wiki_output', 'audit': 'audit_output',
                           'cache': '.bmc_toolkit'}[kind] if context else Path(fallback)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def record_output(path):
    context = current_output()
    if context:
        context.record(path)


def record_error(message):
    context = current_output()
    if context:
        context.errors.append({'domain': context.domain, 'error': str(message)})


def record_warning(message):
    context = current_output()
    if context:
        context.warnings.append({'domain': context.domain, 'warning': str(message)})


@dataclass
class OutputContext:
    root: Path
    domain: str = ''
    artifacts: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    results: list = field(default_factory=list)
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self):
        self.root = Path(self.root).resolve()

    def record(self, path):
        path = Path(path).resolve()
        relative = path.relative_to(self.root)
        self.artifacts[str(relative)] = {
            'path': str(path), 'domain': self.domain,
            'kind': 'wiki' if relative.parts[0] == 'wiki_output' else 'audit',
            'size': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    @contextmanager
    def activate(self):
        token = _current.set(self)
        try:
            yield self
        finally:
            _current.reset(token)

    def finish(self):
        statuses = {result['name']: result['status'] for result in self.results}
        for artifact in self.artifacts.values():
            artifact['domain_status'] = statuses.get(artifact['domain'], 'FAIL' if self.errors else 'PASS')
        report = {'run_id': self.run_id, 'status': 'FAIL' if self.errors else (
                      'PASS_WITH_WARNINGS' if self.warnings else 'PASS'),
                  'domains': self.results, 'errors': self.errors,
                  'warnings': self.warnings,
                  'artifacts': list(self.artifacts.values())}
        directory = self.root / 'audit_output'
        directory.mkdir(parents=True, exist_ok=True)
        # Unique receipts retain earlier runs; latest always describes this attempt.
        for name in [f'output_receipt_{self.run_id}.json', 'output_receipt.json']:
            target = directory / name
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(target)
        return report
