import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from toolkit.core.domain_contracts import CONTRACTS, validate_domain_input
from toolkit.core.tables import TableCatalog
from toolkit.generate import generate


class DomainContractTests(unittest.TestCase):
    def test_empty_is_distinct_from_missing_and_fields_are_checked_per_row(self):
        tables = {name: [] for name in CONTRACTS['collections']}
        def catalog():
            return TableCatalog([dict.fromkeys(tables, []), *tables.values()])
        validate_domain_input('collections', catalog())
        tables['mst_honor'] = [{'HonorId': 1}, {}]
        with self.assertRaisesRegex(ValueError, r'mst_honor\[1\]'):
            validate_domain_input('collections', catalog())
        del tables['mst_honor']
        with self.assertRaisesRegex(ValueError, 'required table is missing'):
            validate_domain_input('collections', catalog())

    def test_missing_new_domain_table_stops_export_but_not_other_tasks(self):
        session = SimpleNamespace(tables=TableCatalog([{}]),
                                  assessment=SimpleNamespace(changes=[], errors=[]),
                                  write_audit=lambda *args, **kwargs: None)
        with tempfile.TemporaryDirectory() as root, \
             patch('toolkit.generate.MasterDataSession.open', return_value=session), \
             patch('toolkit.domains.collections.run') as broken, \
             patch('toolkit.domains.items.run') as other:
            result = generate(['collections', 'items'], root, masterdata='input.json')
        broken.assert_not_called()
        other.assert_called_once()
        self.assertEqual([{'name': 'collections', 'status': 'FAIL'}, {'name': 'items', 'status': 'PASS'}], result['domains'])
        self.assertEqual('collections', result['errors'][0]['domain'])
