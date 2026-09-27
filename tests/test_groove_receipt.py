import json
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace

from toolkit.core.output import OutputContext
from toolkit.resources import sha256
from toolkit.groove_receipt import build_receipt, write_receipt


class GrooveReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        decoded = b'verified decoded fixture'
        encoder = zlib.compressobj(wbits=-15)
        raw = encoder.compress(decoded) + encoder.flush()
        for name, data in [('raw', raw), ('decoded', decoded), ('input.json', b'[]')]:
            (root / name).write_bytes(data)
        self.context = OutputContext(root, domain='groove')
        self.context.results.append({'name': 'groove', 'status': 'PASS'})
        self.target = root / 'audit_output/Groove_Optimizer_Source.json'
        self.target.parent.mkdir()
        self.target.write_text('{"Issues": []}', encoding='utf-8')
        self.context.record(self.target)
        self.session = SimpleNamespace(source={'sha256': sha256(decoded)},
                                       json_path=root / 'input.json', json_sha256=sha256(b'[]'))
        self.source = dict(key='Tables/master_data.s2b', provider='production',
                           envelope='raw-deflate', path=str(root / 'raw'),
                           decoded_path=str(root / 'decoded'), sha256=sha256(raw),
                           decoded_sha256=sha256(decoded), manifest_sha256='a' * 64,
                           fingerprint='b' * 64, retrieved_at='2026-09-21T06:42:06+00:00',
                           http={'Last-Modified': 'Mon, 21 Sep 2026 03:12:44 GMT'})
        self.manifest = {'downloads': [self.source]}

    def test_public_receipt_is_bound_and_has_no_private_fields(self):
        receipt = build_receipt(self.context, self.session, self.manifest)
        self.assertEqual(sha256(self.target.read_bytes()), receipt['exportSha256'])
        self.assertEqual('2026-09-21T03:12:44+00:00', receipt['provenance']['sourceLastModified'])
        self.assertEqual(6, len(receipt['provenance']))
        self.assertNotIn(str(self.context.root), json.dumps(receipt))
        self.source['http'] = {}
        self.assertNotIn('sourceLastModified', build_receipt(self.context, self.session, self.manifest)['provenance'])

    def test_each_input_link_and_export_are_checked(self):
        for path in [self.source['path'], self.source['decoded_path'], self.session.json_path, self.target]:
            with self.subTest(path=path):
                path = Path(path)
                original = path.read_bytes()
                path.write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    build_receipt(self.context, self.session, self.manifest)
                path.write_bytes(original)
        self.session.source = {}
        with self.assertRaises(ValueError):
            build_receipt(self.context, self.session, self.manifest)

    def test_failed_run_cannot_issue_receipt_and_filename_is_run_bound(self):
        write_receipt(self.context, self.session, self.manifest)
        receipt = self.context.root / f'audit_output/groove_export_receipt_{self.context.run_id}.json'
        self.assertTrue(receipt.is_file())
        self.context.errors.append({'error': 'failed'})
        with self.assertRaises(ValueError):
            write_receipt(self.context, self.session, self.manifest)

    def test_invalid_time_and_hash_fail_closed(self):
        for key, bad in [('retrieved_at', '2026-09-21T06:00:00'), ('fingerprint', 'invalid')]:
            with self.subTest(key=key):
                original = self.source[key]
                self.source[key] = bad
                with self.assertRaises(ValueError):
                    build_receipt(self.context, self.session, self.manifest)
                self.source[key] = original

    def test_stale_export_and_export_issues_are_rejected(self):
        self.context.artifacts.clear()
        with self.assertRaises(ValueError):
            build_receipt(self.context, self.session, self.manifest)
        self.target.write_text('{"Issues": ["missing foreign key"]}', encoding='utf-8')
        self.context.record(self.target)
        with self.assertRaises(ValueError):
            build_receipt(self.context, self.session, self.manifest)
