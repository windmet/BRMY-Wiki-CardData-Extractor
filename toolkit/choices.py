"""GUI choice lists read from the newest verified masterdata in the resource cache."""
import json
from pathlib import Path

SUBJECTS_FILE = 'home_voice_subjects.json'


def latest_masterdata(cache):
    """Newest decoded masterdata a sync left behind; provenance marks a completed preparation."""
    candidates = [path for path in Path(cache).glob('production-*/jobs/*/master_data.s2b')
                  if path.with_suffix('.provenance.json').is_file()]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def save_subjects(cache_root, catalog_path):
    """Keep the subject list of a full home voice run next to the cached resources."""
    from .domains.home_voices import SUBJECT_FIELDS
    from .resources import atomic_json
    catalog = json.loads(Path(catalog_path).read_text(encoding='utf-8'))
    atomic_json(Path(cache_root) / SUBJECTS_FILE,
                [{key: subject.get(key) for key in SUBJECT_FIELDS} for subject in catalog['Subjects']])


def _saved_subjects(masterdata):
    path = masterdata.parents[2] / SUBJECTS_FILE
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []


def load_choices(cache):
    """Return cycle and subject options, or None when no masterdata has been cached yet."""
    from .core.masterdata import decode_masterdata
    from .core.tables import TableCatalog
    from .domains.birthday import cycle_options
    from .domains.home_voices import subject_options
    masterdata = latest_masterdata(cache) if cache else None
    if masterdata is None:
        return None
    tables = TableCatalog(decode_masterdata(str(masterdata)))
    return {
        'source': str(masterdata),
        'cycles': [(str(number), f'第{number}轮（{year}–{(year + 1) % 100:02d}）')
                   for number, year in cycle_options(tables)],
        'subjects': subject_options(tables, _saved_subjects(masterdata)),
    }
