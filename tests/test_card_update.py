import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment

from scripts.compare_exports import compare_xlsx
from toolkit.domains.card_update import merge_card_workbook


HEADERS = ["卡牌", "卡牌编号", "卡牌名", "卡牌译名", "卡牌语音①C"]


def make_old_workbook(path, duplicate=False):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "cards_data"
    sheet.append(HEADERS + ["人工备注"])
    sheet.append(["card_1", 1, "Old Name", "译名一", "语音翻译", "=1+1"])
    sheet["D2"].number_format = "@"
    sheet["D2"].comment = Comment("keep me", "wiki")
    sheet.append(["card_2", 2, "Removed", "译名二", "", "旧卡"])
    if duplicate:
        sheet.append(["card_1_copy", "001", "Duplicate", "", "", ""])
    workbook.save(path)


class CardUpdateTests(unittest.TestCase):
    def test_preserves_manual_and_custom_columns_and_builds_diff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_path = root / "old.xlsx"
            updated_path = root / "updated.xlsx"
            changes_path = root / "changes.xlsx"
            audit_path = root / "audit.json"
            make_old_workbook(old_path)

            audit = merge_card_workbook(
                old_path,
                HEADERS,
                [
                    ["card_1", "001", "New Name", "", ""],
                    ["card_3", "3", "Added", "", ""],
                ],
                updated_path=updated_path,
                changes_path=changes_path,
                audit_path=audit_path,
            )

            updated = load_workbook(updated_path, data_only=False)["cards_data"]
            changes = load_workbook(changes_path, data_only=False)
            old = load_workbook(old_path, data_only=False)["cards_data"]
            saved_audit = json.loads(audit_path.read_text(encoding="utf-8"))

        headers = [cell.value for cell in updated[1]]
        indexes = {header: index + 1 for index, header in enumerate(headers)}
        self.assertEqual(1, updated.cell(2, indexes["卡牌编号"]).value)
        self.assertEqual("New Name", updated.cell(2, indexes["卡牌名"]).value)
        self.assertEqual("译名一", updated.cell(2, indexes["卡牌译名"]).value)
        self.assertEqual("语音翻译", updated.cell(2, indexes["卡牌语音①C"]).value)
        self.assertEqual("=1+1", updated.cell(2, indexes["人工备注"]).value)
        self.assertEqual("f", updated.cell(2, indexes["人工备注"]).data_type)
        self.assertEqual("@", updated.cell(2, indexes["卡牌译名"]).number_format)
        self.assertEqual("keep me", updated.cell(2, indexes["卡牌译名"]).comment.text)
        self.assertIsNone(updated.cell(3, indexes["卡牌译名"]).value)
        self.assertEqual(["Summary", "Added", "Modified", "Removed"], changes.sheetnames)
        self.assertEqual(3, changes["Added"]["B2"].value)
        self.assertEqual("卡牌名", changes["Modified"]["B2"].value)
        self.assertEqual(2, changes["Removed"]["B2"].value)
        self.assertEqual("Old Name", old["C2"].value)
        self.assertEqual(audit, saved_audit)
        self.assertEqual(1, audit["Counts"]["AddedCards"])
        self.assertEqual(1, audit["Counts"]["ModifiedCards"])
        self.assertEqual(1, audit["Counts"]["RemovedCards"])
        self.assertEqual(1, audit["Counts"]["PreservedFormulaCells"])
        self.assertEqual(["人工备注"], audit["CustomColumns"])

    def test_duplicate_card_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_path = root / "old.xlsx"
            make_old_workbook(old_path, duplicate=True)

            with self.assertRaisesRegex(ValueError, "重复卡牌编号"):
                merge_card_workbook(
                    old_path,
                    HEADERS,
                    [["card_1", 1, "Name", "", ""]],
                    updated_path=root / "updated.xlsx",
                    changes_path=root / "changes.xlsx",
                    audit_path=root / "audit.json",
                )

            self.assertFalse((root / "updated.xlsx").exists())

    def test_noop_merge_preserves_blank_cell_types(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_path = root / "old.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "cards_data"
            sheet.append(HEADERS)
            sheet.append(["card_1", 1, "Name", "", ""])
            workbook.save(old_path)

            updated_path = root / "updated.xlsx"
            audit = merge_card_workbook(
                old_path,
                HEADERS,
                [["card_1", "1", "Name", "", ""]],
                updated_path=updated_path,
                changes_path=root / "changes.xlsx",
                audit_path=root / "audit.json",
            )

            difference = compare_xlsx(old_path, updated_path)

        self.assertIsNone(difference)
        self.assertEqual(0, audit["Counts"]["ModifiedCards"])


if __name__ == "__main__":
    unittest.main()
