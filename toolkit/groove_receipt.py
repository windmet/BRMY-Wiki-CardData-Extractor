"""Export-bound, public-safe provenance for the Calculator candidate gate.

This is an integrity receipt from a trusted local producer, not a signature.
Only synchronized production inputs qualify; JSON-only generation does not.
"""
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from .resources import inflate_raw, sha256, atomic_json
from .core.masterdata import sha256_file


def build_receipt(context, session, resource_manifest):
    if context.errors or not any(r == {'name': 'groove', 'status': 'PASS'}
                                 for r in context.results):
        raise ValueError('GROOVE receipt requires a successful current run')
    entries = [d for d in resource_manifest['downloads']
               if d['key'] == 'Tables/master_data.s2b']
    if len(entries) != 1:
        raise ValueError('GROOVE receipt requires exactly one masterdata input')
    source = entries[0]
    if source.get('provider') != 'production' or source.get('envelope') != 'raw-deflate':
        raise ValueError('Unsupported masterdata provenance')
    raw = Path(source['path']).read_bytes()
    decoded = Path(source['decoded_path']).read_bytes()
    if (sha256(raw) != source['sha256'] or inflate_raw(raw) != decoded
            or sha256(decoded) != source['decoded_sha256']
            or session.source.get('sha256') != source['decoded_sha256']
            or sha256_file(session.json_path) != session.json_sha256):
        raise ValueError('Masterdata input chain changed or is not bound to this session')
    target = context.root / 'audit_output/Groove_Optimizer_Source.json'
    artifact = context.artifacts.get(str(target.relative_to(context.root)))
    if not artifact or artifact['domain'] != 'groove' or sha256_file(target) != artifact['sha256']:
        raise ValueError('GROOVE export is not an unchanged artifact of this run')
    if json.loads(target.read_text(encoding='utf-8')).get('Issues'):
        raise ValueError('GROOVE export contains unresolved validation issues')
    provenance = {
        'sourceRetrievedAt': source['retrieved_at'],
        # The manifest associated with the actual download, not a later cache check.
        'sourceManifestSha256': source['manifest_sha256'],
        'sourceResourceFingerprint': source['fingerprint'],
        'sourceRawSha256': source['sha256'],
        'sourceDecodedSha256': source['decoded_sha256'],
    }
    timestamp = datetime.fromisoformat(provenance['sourceRetrievedAt'].replace('Z', '+00:00'))
    if timestamp.utcoffset() is None:
        raise ValueError('Retrieval timestamp must include a timezone')
    provenance['sourceRetrievedAt'] = timestamp.isoformat()
    for key, value in provenance.items():
        if key != 'sourceRetrievedAt' and not re.fullmatch('[a-f0-9]{64}', value):
            raise ValueError(f'Invalid provenance digest: {key}')
    modified = source.get('http', {}).get('Last-Modified')
    if modified:
        timestamp = parsedate_to_datetime(modified)
        if timestamp.utcoffset() is None:
            raise ValueError('Last-Modified must include a timezone')
        provenance['sourceLastModified'] = timestamp.astimezone(timezone.utc).isoformat()
    return {'exportSha256': artifact['sha256'], 'provenance': provenance}


def write_receipt(context, session, resource_manifest):
    receipt = build_receipt(context, session, resource_manifest)
    # No fixed filename: a failed retry must never look like a fresh receipt.
    target = context.root / 'audit_output' / f'groove_export_receipt_{context.run_id}.json'
    atomic_json(target, receipt)
    context.record(target)
