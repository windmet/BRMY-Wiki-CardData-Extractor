"""Production manifest protocol and verified raw-object cache.

Providers download bytes only. Format adapters consume these cached objects.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import tempfile
import urllib.parse
import urllib.request
import zlib

import msgpack

PRODUCTION_URL = 'https://s2b-assets-prod.s2b-coly.com/'
CATEGORY_PATHS = {0: 'Files/Android/', 1: 'Scripts/', 2: 'Tables/',
                  3: 'LightingSets/', 4: 'Movies/', 5: 'Musics/', 6: 'Jukebox/'}
MANIFEST_KEY = 'Tables/FileAssetList.s2bcoly'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_key(key):
    if not isinstance(key, str) or not key or key.startswith('/'):
        raise ValueError('invalid resource path')
    if any(part in {'', '.', '..'} for part in key.split('/')):
        raise ValueError('unsafe resource path')
    if any(character in key for character in '\\:*?"<>|#%') or any(ord(c) < 32 for c in key):
        raise ValueError('unsafe resource path characters')
    for part in key.split('/'):
        if part.endswith((' ', '.')) or part.split('.')[0].upper() in {
            'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
            *(f'LPT{i}' for i in range(1, 10)),
        }:
            raise ValueError('unsafe Windows resource name')
    return key


def inflate_raw(raw, limit=64 * 1024 * 1024):
    decoder = zlib.decompressobj(-15)
    result = decoder.decompress(raw, limit + 1)
    if len(result) > limit or decoder.unconsumed_tail:
        raise ValueError('decompressed data exceeds size limit')
    if not decoder.eof or decoder.unused_data:
        raise ValueError('truncated or trailing DEFLATE data')
    return result


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.partial', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8'))


@dataclass(frozen=True)
class Resource:
    key: str
    category: int
    metadata: list
    fingerprint: str
    provider: str = 'production'


def parse_manifest(raw):
    value = msgpack.unpackb(inflate_raw(raw), raw=False, strict_map_key=False)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], list):
        raise ValueError('unexpected production manifest structure')
    resources, unknown, seen = [], [], set()
    for index, row in enumerate(value[0]):
        if not isinstance(row, list) or len(row) < 5 or type(row[2]) is not int:
            raise ValueError(f'malformed manifest record {index}')
        validate_key(row[0])
        category = row[2]
        identity = (category, row[0])
        if identity in seen:
            raise ValueError(f'duplicate resource record: {row[0]}')
        seen.add(identity)
        if category not in CATEGORY_PATHS:
            unknown.append({'index': index, 'record': row})
            continue
        key = validate_key(CATEGORY_PATHS[category] + row[0])
        fingerprint = sha256(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        resources.append(Resource(key, category, row, fingerprint))
    return resources, unknown


class ProdManifestProvider:
    def __init__(self, cache, *, base_url=PRODUCTION_URL, opener=None, timeout=30):
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('provider requires an HTTPS base URL without credentials or query')
        self.base_url = base_url.rstrip('/') + '/'
        # Endpoint-specific namespace prevents accidental cross-provider reuse.
        self.root = Path(cache).resolve() / ('production-' + sha256(self.base_url.encode())[:12])
        self.opener = opener or urllib.request.urlopen
        self.timeout = timeout
        self.resources = {}
        self.unknown = []
        self.manifest_sha256 = None

    def _get(self, key, limit, cancelled=None):
        if cancelled and cancelled():
            raise InterruptedError('download cancelled')
        validate_key(key)
        url = urllib.parse.urljoin(self.base_url, urllib.parse.quote(key, safe='/'))
        request = urllib.request.Request(url, headers={'Accept-Encoding': 'identity', 'User-Agent': 'BRMY-Wiki-Toolkit'})
        chunks, size = [], 0
        with self.opener(request, timeout=self.timeout) as response:
            if response.status != 200:
                raise ValueError(f'HTTP {response.status}: {key}')
            if response.geturl() != url:
                raise ValueError('unexpected resource redirect')
            length = response.headers.get('Content-Length')
            expected = int(length) if length is not None else None
            if expected is not None and (expected < 0 or expected > limit):
                raise ValueError('resource exceeds size limit')
            while True:
                if cancelled and cancelled():
                    raise InterruptedError('download cancelled')
                chunk = response.read(min(1024 * 1024, limit + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise ValueError('resource exceeds size limit')
            if expected is not None and size != expected:
                raise ValueError('incomplete resource download')
            headers = {key: response.headers.get(key) for key in ['ETag', 'Last-Modified', 'Content-Length']}
        return b''.join(chunks), headers

    def refresh(self, *, offline=False, cancelled=None):
        path = self.root / 'manifest.bin'
        if offline:
            try:
                raw = path.read_bytes()
            except FileNotFoundError as error:
                raise FileNotFoundError(
                    '此缓存目录还没有正式资源清单。请切换到“正式服在线”检查并同步所需资源，'
                    '或在高级设置中选择已有缓存的目录，再使用离线模式。'
                ) from error
        else:
            raw, _ = self._get(MANIFEST_KEY, 16 * 1024 * 1024, cancelled)
        resources, unknown = parse_manifest(raw)
        self.resources = {resource.key: resource for resource in resources}
        self.unknown = unknown
        self.manifest_sha256 = sha256(raw)
        case_groups = {}
        for resource in resources:
            case_groups.setdefault(resource.key.casefold(), []).append(resource.key)
        report = {'provider': 'production', 'base_url': self.base_url,
                  'offline': offline, 'manifest_sha256': self.manifest_sha256,
                  'resource_count': len(resources), 'unknown_records': unknown,
                  'case_collisions': [keys for keys in case_groups.values() if len(keys) > 1],
                  'resources': [asdict(resource) for resource in resources]}
        if not offline:
            atomic_bytes(path, raw)
        atomic_json(self.root / 'catalog.json', report)
        return report

    def download(self, key, *, offline=False, cancelled=None, limit=128 * 1024 * 1024):
        if key not in self.resources:
            raise ValueError(f'resource not confirmed in manifest: {key}')
        resource = self.resources[key]
        # HTTP keys are case-sensitive; Windows paths are not. Isolate each key.
        path = self.root / 'raw' / sha256(key.encode('utf-8')) / Path(validate_key(key)).name
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('cache path escapes provider directory')
        metadata_path = path.with_name(path.name + '.metadata.json')
        try:
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            cached = (metadata['fingerprint'] == resource.fingerprint
                      and path.is_file() and path.stat().st_size == metadata['size']
                      and sha256(path.read_bytes()) == metadata['sha256'])
        except (OSError, ValueError, KeyError, TypeError):
            cached = False
        if cached:
            if metadata['size'] > limit:
                raise ValueError('cached resource exceeds size limit')
            return {**metadata, 'path': str(path), 'cache_hit': True, 'offline': offline}
        if offline:
            raise ValueError(f'离线缓存缺失或未通过校验：{key}。请切换到“正式服在线”重新同步此任务后再离线使用。')
        raw, headers = self._get(key, limit, cancelled)
        metadata = {'key': key, 'provider': 'production', 'base_url': self.base_url,
                    'fingerprint': resource.fingerprint, 'manifest_sha256': self.manifest_sha256,
                    'size': len(raw), 'sha256': sha256(raw), 'http': headers,
                    'retrieved_at': datetime.now(timezone.utc).isoformat()}
        atomic_bytes(path, raw)
        atomic_json(metadata_path, metadata)
        return {**metadata, 'path': str(path), 'cache_hit': False, 'offline': False}


def prepare_production_masterdata(download, destination):
    """Decode the verified production DEFLATE envelope; validate before publishing."""
    from .core.masterdata import decode_masterdata
    destination = Path(destination).resolve()
    raw = Path(download['path']).read_bytes()
    if sha256(raw) != download['sha256']:
        raise ValueError('raw masterdata cache changed')
    decoded = inflate_raw(raw)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(suffix='.s2b', dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(decoded)
        decode_masterdata(temporary)
        Path(temporary).replace(destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    provenance = {**download, 'decoded_path': str(destination),
                  'decoded_sha256': sha256(decoded), 'envelope': 'raw-deflate'}
    atomic_json(destination.with_suffix('.provenance.json'), provenance)
    return provenance


def main(args):
    import argparse
    parser = argparse.ArgumentParser(description='正式服资源清单与按需原始下载')
    parser.add_argument('action', choices=['catalog', 'download', 'masterdata'])
    parser.add_argument('keys', nargs='*')
    parser.add_argument('--cache', required=True)
    parser.add_argument('--offline', action='store_true')
    options = parser.parse_args(args)
    try:
        provider = ProdManifestProvider(options.cache)
        report = provider.refresh(offline=options.offline)
        print(f"正式清单：{report['resource_count']} 个已识别资源，{len(report['unknown_records'])} 条未识别类别")
        if options.offline:
            print('离线缓存清单；未检查线上更新')
        if options.action == 'catalog':
            print(provider.root / 'catalog.json')
        elif options.action == 'masterdata':
            result = provider.download('Tables/master_data.s2b', offline=options.offline)
            decoded = prepare_production_masterdata(result, provider.root / 'prepared/master_data.s2b')
            print(decoded['decoded_path'])
        else:
            if not options.keys:
                raise ValueError('download 需要明确的清单资源路径')
            for key in options.keys:
                result = provider.download(key, offline=options.offline)
                print(f"{'缓存' if result['cache_hit'] else '下载'}: {result['path']}")
        return True
    except (OSError, ValueError, zlib.error, msgpack.UnpackException) as error:
        print(f'[!] 正式资源操作失败: {error}')
        return False
