from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from ..resources import ProdManifestProvider, atomic_json, sha256, inflate_raw
from ..resolve import synchronize, MASTER_KEY
from ..core.tables import TableCatalog
from .common import MasterData
from . import pins, puzzle, bartending, puzzle_enrichment, bartending_enrichment
from . import item_catalog, marvelous_challenge, collection_expansion, collection_support


def export_sources(masterdata, destination):
    """One decoded snapshot, native facts only. Missing tables/issues fail closed."""
    raw = Path(masterdata).read_bytes()
    snapshot = sha256(raw)
    payload = json.loads(raw)
    session = SimpleNamespace(tables=TableCatalog(payload))
    required = {'mst_puzzle_map', 'mst_puzzle_stage', 'mst_puzzle_stage_campaign',
                'mst_puzzle_drop_reward', 'mst_puzzle_drop_reward_basic',
                'mst_puzzle_achievement', 'mst_puzzle_achievement_group',
                'mst_puzzle_achievement_reward', 'mst_direct_reward',
                'mst_event', 'mst_event_b', 'mst_event_shift', 'mst_event_ingredient',
                'mst_event_puzzle_stage_ingredient', 'mst_event_puzzle_drop_reward_ingredient'}
    missing = required - set(session.tables.names)
    if missing:
        raise ValueError(f'Missing required website tables: {sorted(missing)}')
    md = MasterData(payload)
    stage = puzzle_enrichment.enrich(puzzle.extract(session), md)
    stage['Meta'].update(MasterdataSha256=snapshot, ExtractionKind='toolkit-website-source')
    recipes = bartending_enrichment.enrich(bartending.extract(session, stage), md)
    recipes['Meta'].update(MasterdataSha256=snapshot, ExtractionKind='toolkit-website-source')
    expansion, assets, audit = collection_expansion.extract(collection_support.MasterData(masterdata))
    if audit['issues']:
        raise ValueError('Collection extraction issues require review')
    results = {'pins': pins.export(Path(masterdata)), 'puzzle': stage, 'bartending': recipes,
               'marvelous': marvelous_challenge.extract(md), 'items': item_catalog.extract(md),
               'collections': expansion}
    for domain, source in results.items():
        if source.get('Issues'):
            raise ValueError(f'{domain}: extraction issues require review')
        source.setdefault('Meta', {}).update(MasterdataSha256=snapshot, ExtractionKind='toolkit-website-source')
    output = Path(destination)
    for domain, source in results.items():
        atomic_json(output / f'{domain}.json', source)
    atomic_json(output / 'collection-asset-requests.json', assets)
    atomic_json(output / 'collection-audit.json', audit)
    return results


def check(provider, output, *, offline=False):
    catalog = provider.refresh(offline=offline)
    if MASTER_KEY not in provider.resources:
        raise ValueError('Official manifest has no masterdata resource')
    report = {'schemaVersion': 1, 'status': 'checked', 'checkedAt': datetime.now(timezone.utc).isoformat(),
              'onlineFreshnessChecked': not offline, 'manifestSha256': catalog['manifest_sha256'],
              'resourceFingerprint': provider.resources[MASTER_KEY].fingerprint,
              'unknownCategoryCount': len(catalog['unknown_records'])}
    atomic_json(Path(output) / 'check.json', report)
    return report


def prepare(provider, output, cache, expected_manifest, *, offline=False):
    # Caller checked online. Consume those exact cached bytes, never race a second
    # refresh. Downloads are online unless explicitly offline; provenance remains
    # bound to the original download, even when its object is reused from cache.
    catalog = provider.refresh(offline=True)
    if catalog['manifest_sha256'] != expected_manifest:
        raise ValueError('Manifest changed since check; retry against current catalog')

    class Snapshot:
        def refresh(self, **kwargs):
            return {**catalog, 'offline': offline}

        def __getattr__(self, key):
            return getattr(provider, key)

    output = Path(output).resolve()
    receipt = synchronize(['groove', 'music', 'jukebox'], output, cache,
                          offline=offline, include_card_audio=False, provider=Snapshot())
    if receipt['status'] == 'FAIL' or receipt['errors']:
        raise ValueError('Toolkit generation failed; inspect output_receipt.json')
    artifact = next((row for row in receipt['artifacts']
                     if Path(row['path']).name == f"groove_export_receipt_{receipt['run_id']}.json"), None)
    if not artifact or sha256(Path(artifact['path']).read_bytes()) != artifact['sha256']:
        raise ValueError('Missing/tampered current GROOVE receipt')
    masterdata = output / '.bmc_toolkit/master_data.json'
    manifest = json.loads((output / 'audit_output/resource_manifest.json').read_text('utf-8'))
    downloads = [row for row in manifest['downloads'] if row['key'] == MASTER_KEY]
    if len(downloads) != 1:
        raise ValueError('Exactly one masterdata source is required')
    download = downloads[0]
    raw = Path(download['path']).read_bytes()
    decoded = Path(download['decoded_path']).read_bytes()
    cache_manifest = json.loads((output / '.bmc_toolkit/.bmc_toolkit/master_data_cache.json').read_text('utf-8'))
    if (sha256(raw) != download['sha256'] or inflate_raw(raw) != decoded
            or sha256(decoded) != download['decoded_sha256']
            or cache_manifest['source']['sha256'] != sha256(decoded)
            or cache_manifest['output']['sha256'] != sha256(masterdata.read_bytes())):
        raise ValueError('Masterdata chain changed before website extraction')
    sources = output / 'website_sources'
    export_sources(masterdata, sources)
    files = [path for path in sources.glob('*.json')] + [Path(row['path']) for row in receipt['artifacts']]
    report = {'schemaVersion': 1, 'status': 'PASS', 'runId': receipt['run_id'],
              'masterdataJsonSha256': sha256(masterdata.read_bytes()),
              'resourceFingerprint': download['fingerprint'],
              'provenance': json.loads(Path(artifact['path']).read_text('utf-8'))['provenance'],
              'grooveReceipt': str(Path(artifact['path']).relative_to(output)),
              'artifacts': [{'path': str(path.relative_to(output)), 'sha256': sha256(path.read_bytes())} for path in files],
              'warnings': receipt['warnings'], 'publication': 'source_only'}
    atomic_json(output / 'website_receipt.json', report)
    return report


def main(args):
    parser = argparse.ArgumentParser(description='Website native-source update; no publication')
    parser.add_argument('action', choices=('check', 'prepare'))
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--expected-manifest')
    options = parser.parse_args(args)
    provider = ProdManifestProvider(options.cache)
    options.output.mkdir(parents=True, exist_ok=True)
    try:
        if options.action == 'check':
            report = check(provider, options.output, offline=options.offline)
        else:
            if not options.expected_manifest:
                raise ValueError('prepare requires the manifest hash returned by check')
            report = prepare(provider, options.output, options.cache, options.expected_manifest, offline=options.offline)
        print(json.dumps({key: report.get(key) for key in ('status', 'manifestSha256', 'resourceFingerprint', 'runId')}))
        return True
    except Exception as error:
        atomic_json(options.output / 'website_failure.json', {'status': 'FAIL', 'error': str(error)})
        print(f'Website source update failed: {error}')
        return False
