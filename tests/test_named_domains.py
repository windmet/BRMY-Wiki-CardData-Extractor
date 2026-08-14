import json
import os
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from toolkit.core.session import MasterDataSession
from toolkit.domains import items, missions, music


class NamedDomainTests(unittest.TestCase):
    def test_named_tables_ignore_field_collision_decoys(self):
        names_and_rows = [
            ("decoy_music", [{"MusicId": 999, "DisplayName": "Wrong"}]),
            ("mst_music", [{
                "MusicId": 1,
                "DisplayName": "Right Song",
                "ArtistName": "Right Artist",
                "IsActive": True,
            }]),
            ("decoy_item", [{"ItemId": 999, "ItemTypeCode": 1}]),
            ("mst_item", [{
                "ItemId": 1,
                "ItemName": "Right Item",
                "ItemTypeCode": 1,
                "ItemRarityCode": 1,
                "ItemAttributeCode": 0,
                "ItemDisplayTab": 0,
                "ItemFileName": "item_1",
                "ItemDescription1": "Description",
                "IsActive": True,
            }]),
            ("mst_mission", [{
                "MissionId": 1,
                "Description": "Do # things",
                "MissionType": "sample",
                "IsActive": True,
            }]),
            ("mst_mission_sequence", [{
                "MissionId": 1,
                "MissionSequenceNo": 1,
                "Border": 5,
                "IsHidden": True,
                "IsActive": True,
            }]),
            ("decoy_mission", [{"MissionId": 999, "Description": "Wrong #"}]),
            ("decoy_sequence", [{"MissionId": 999, "IsHidden": True}]),
        ]
        data = [
            {name: [0, 0] for name, _ in names_and_rows},
            *(rows for _, rows in names_and_rows),
        ]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            masterdata = root / "master_data.json"
            masterdata.write_text(json.dumps(data), encoding="utf-8")
            session = MasterDataSession.open(masterdata, required_schema={})
            previous = os.getcwd()
            os.chdir(root)
            try:
                music_result = music.extract(session=session)
                items.run(session=session)
                missions.run(session=session)
            finally:
                os.chdir(previous)

            self.assertEqual([1], list(music_result))
            self.assertEqual("Right Song", music_result[1]["DisplayName"])

            item_book = load_workbook(root / "xlsx_output" / "items_catalog.xlsx")
            item_sheet = item_book.active
            self.assertEqual(2, item_sheet.max_row)
            self.assertEqual(1, item_sheet["A2"].value)
            self.assertEqual("Right Item", item_sheet["B2"].value)

            mission_book = load_workbook(root / "xlsx_output" / "hidden_missions.xlsx")
            mission_sheet = mission_book.active
            self.assertEqual(2, mission_sheet.max_row)
            self.assertEqual(1, mission_sheet["A2"].value)
            self.assertEqual("Do 5 things", mission_sheet["F2"].value)


if __name__ == "__main__":
    unittest.main()
