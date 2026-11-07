import unittest

from toolkit.core.tables import TableCatalog


class TableCatalogTests(unittest.TestCase):
    def test_resolves_tables_in_directory_order(self):
        data = [
            {"mst_first": 0, "mst_second": 0},
            [{"Id": 1, "IsActive": True}, {"Id": 2, "IsActive": False}],
            [{"Group": 7, "Value": "a"}, {"Group": 7, "Value": "b"}],
        ]
        catalog = TableCatalog(data)

        self.assertEqual(("mst_first", "mst_second"), catalog.names)
        self.assertEqual([1], [row["Id"] for row in catalog.rows("mst_first", active_only=True)])
        self.assertEqual(2, len(catalog.group_by("mst_second", "Group")[7]))

    def test_optional_and_required_tables_are_distinct(self):
        catalog = TableCatalog([{"mst_present": 0}, []])

        self.assertEqual([], catalog.rows("mst_missing"))
        with self.assertRaisesRegex(KeyError, "mst_missing"):
            catalog.require("mst_missing")
        self.assertEqual({}, catalog.by_id("mst_missing", "Id", required=False))
        self.assertEqual({}, catalog.group_by("mst_missing", "Id", required=False))

    def test_rejects_truncated_payload(self):
        with self.assertRaisesRegex(ValueError, "declares 2 tables"):
            TableCatalog([{"a": 0, "b": 0}, []])


if __name__ == "__main__":
    unittest.main()
