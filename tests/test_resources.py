import io
import json
import tempfile
import unittest
import zlib
from pathlib import Path

import msgpack

from toolkit.resources import (ProdManifestProvider, parse_manifest, inflate_raw,
                               validate_key, prepare_production_masterdata, sha256, MANIFEST_KEY)


def deflate(data):
    encoder = zlib.compressobj(wbits=-15)
    return encoder.compress(data) + encoder.flush()


def manifest(rows):
    return deflate(msgpack.packb([rows], use_bin_type=True))


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, url, length=None):
        super().__init__(data)
        self.url = url
        self.headers = {'Content-Length': str(len(data) if length is None else length)}

    def geturl(self):
        return self.url


class ResourcesTests(unittest.TestCase):
    def test_empty_offline_cache_explains_recovery_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            def no_network(*args, **kwargs):
                self.fail('offline cache recovery must not start a network request')
            provider = ProdManifestProvider(directory, opener=no_network)
            with self.assertRaisesRegex(FileNotFoundError, '没有正式资源清单.*正式服在线'):
                provider.refresh(offline=True)

    def test_manifest_keeps_unknown_categories_and_raw_metadata(self):
        row = ['master_data.s2b', 4597, 2, 0, 2.0, None, False]
        resources, unknown = parse_manifest(manifest([row, ['new.s2bscore', 1, 8, 0, 0.2]]))
        self.assertEqual('Tables/master_data.s2b', resources[0].key)
        self.assertEqual(row, resources[0].metadata)
        self.assertEqual(8, unknown[0]['record'][2])

    def test_untrusted_paths_and_duplicate_keys_are_rejected(self):
        for key in ['../x', '/absolute', 'a/../b', 'a\\b', 'file:stream', 'x?query',
                    'x%2Fy', 'NUL.txt', 'a/COM1', 'a.', 'a//b']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_key(key)
        with self.assertRaises(ValueError):
            parse_manifest(manifest([['a', 1, 2, 0, 1], ['a', 2, 2, 0, 1]]))
        with self.assertRaises(ValueError):
            parse_manifest(manifest([['short']]))

    def test_deflate_rejects_truncation_trailing_data_and_expansion(self):
        raw = deflate(b'x' * 500)
        for data, limit in [(raw[:-1], 1000), (raw + b'junk', 1000), (raw, 10)]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                inflate_raw(data, limit)

    def test_cache_invalidation_corruption_offline_and_failed_download(self):
        row = ['a.acb', 1, 5, 0, 1]
        current = {'manifest': manifest([row]), 'body': b'first', 'length': None}
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            body = current['manifest'] if request.full_url.endswith(MANIFEST_KEY) else current['body']
            return Response(body, request.full_url,
                            None if request.full_url.endswith(MANIFEST_KEY) else current['length'])
        with tempfile.TemporaryDirectory() as directory:
            provider = ProdManifestProvider(directory, opener=opener)
            provider.refresh()
            first = provider.download('Musics/a.acb')
            self.assertFalse(first['cache_hit'])
            self.assertTrue(provider.download('Musics/a.acb')['cache_hit'])
            self.assertEqual(2, len(calls))
            provider.refresh(offline=True)
            self.assertTrue(provider.download('Musics/a.acb', offline=True)['cache_hit'])
            row[1] = 2
            current['manifest'] = manifest([row])
            provider.refresh()
            with self.assertRaises(ValueError):
                provider.download('Musics/a.acb', offline=True)
            current.update(body=b'incomplete', length=30)
            with self.assertRaises(ValueError):
                provider.download('Musics/a.acb')
            self.assertEqual(b'first', Path(first['path']).read_bytes())
            current.update(body=b'second', length=None)
            second = provider.download('Musics/a.acb')
            self.assertFalse(second['cache_hit'])
            Path(second['path']).write_bytes(b'broken')
            with self.assertRaises(ValueError):
                provider.download('Musics/a.acb', offline=True)
            self.assertFalse(provider.download('Musics/a.acb')['cache_hit'])
            with self.assertRaises(ValueError):
                provider.download('Musics/unlisted.acb')

    def test_bad_refresh_and_cancellation_preserve_valid_manifest(self):
        good = manifest([['a', 1, 2, 0, 1]])
        state = {'body': good}
        def opener(request, timeout):
            return Response(state['body'], request.full_url)
        with tempfile.TemporaryDirectory() as directory:
            provider = ProdManifestProvider(directory, opener=opener)
            provider.refresh()
            state['body'] = b'not-deflate'
            with self.assertRaises((ValueError, zlib.error)):
                provider.refresh()
            self.assertEqual(good, (provider.root / 'manifest.bin').read_bytes())
            with self.assertRaises(InterruptedError):
                provider.refresh(cancelled=lambda: True)

    def test_case_sensitive_remote_keys_have_distinct_windows_cache_paths(self):
        raw = manifest([['Name.acb', 1, 5, 0, 1], ['name.acb', 2, 5, 0, 1]])
        def opener(request, timeout):
            return Response(raw if request.full_url.endswith(MANIFEST_KEY) else request.full_url.encode(),
                            request.full_url)
        with tempfile.TemporaryDirectory() as directory:
            provider = ProdManifestProvider(directory, opener=opener)
            catalog = provider.refresh()
            self.assertEqual(1, len(catalog['case_collisions']))
            a = provider.download('Musics/Name.acb')
            b = provider.download('Musics/name.acb')
            self.assertNotEqual(a['path'].casefold(), b['path'].casefold())
            self.assertNotEqual(Path(a['path']).read_bytes(), Path(b['path']).read_bytes())

    def test_masterdata_adapter_validates_before_replacing_destination(self):
        data = msgpack.packb({'mst_test': [0, 0]}) + msgpack.packb([{'Id': 1}])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw.bin'
            raw.write_bytes(deflate(data))
            destination = root / 'prepared.s2b'
            download = {'path': str(raw), 'sha256': sha256(raw.read_bytes())}
            provenance = prepare_production_masterdata(download, destination)
            self.assertEqual(data, destination.read_bytes())
            self.assertEqual(sha256(data), provenance['decoded_sha256'])
            raw.write_bytes(deflate(msgpack.packb([])))
            download['sha256'] = sha256(raw.read_bytes())
            with self.assertRaises(ValueError):
                prepare_production_masterdata(download, destination)
            self.assertEqual(data, destination.read_bytes())


if __name__ == '__main__':
    unittest.main()
