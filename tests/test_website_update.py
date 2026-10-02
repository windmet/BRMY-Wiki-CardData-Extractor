import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from toolkit.resources import Resource
from toolkit.website.service import check, export_sources, prepare


class WebsiteUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def provider(self):
        value = SimpleNamespace(resources={'Tables/master_data.s2b': Resource('Tables/master_data.s2b', 2, [], 'b'*64)})
        value.refresh = lambda **kwargs: {'manifest_sha256': 'a'*64, 'unknown_records': []}
        return value

    def test_online_check_is_not_a_download_or_publication(self):
        report = check(self.provider(), self.root)
        self.assertTrue(report['onlineFreshnessChecked'])
        self.assertEqual('checked', report['status'])
        self.assertEqual(['check.json'], [p.name for p in self.root.iterdir()])

    def test_offline_check_never_claims_freshness(self):
        self.assertFalse(check(self.provider(), self.root, offline=True)['onlineFreshnessChecked'])

    def test_missing_masterdata_stops_check(self):
        provider = self.provider()
        provider.resources = {}
        with self.assertRaisesRegex(ValueError, 'no masterdata'):
            check(provider, self.root)
        self.assertFalse((self.root / 'check.json').exists())

    def test_changed_catalog_cannot_prepare_a_different_snapshot(self):
        with self.assertRaisesRegex(ValueError, 'Manifest changed'):
            prepare(self.provider(), self.root, self.root / 'cache', 'c'*64)

    def test_failed_toolkit_run_blocks_native_exports(self):
        with patch('toolkit.website.service.synchronize', return_value={'status': 'FAIL', 'errors': ['drift']}):
            with self.assertRaisesRegex(ValueError, 'generation failed'):
                prepare(self.provider(), self.root, self.root / 'cache', 'a'*64)
        self.assertFalse((self.root / 'website_receipt.json').exists())

    def test_missing_required_tables_fail_before_any_source_is_written(self):
        master = self.root / 'input.json'
        master.write_text(json.dumps([{'placeholder': 0}, []]), 'utf-8')
        with self.assertRaises((ValueError, KeyError)):
            export_sources(master, self.root / 'output')
        self.assertFalse((self.root / 'output').exists())


if __name__ == '__main__':
    unittest.main()
