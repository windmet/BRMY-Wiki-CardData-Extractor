import tempfile
import unittest
from pathlib import Path

from scripts.dump_schema import compare, parse_dump


DUMP = """// Namespace: Coly.S2BShared.Enums
public enum CardRarityCode // TypeDefIndex: 1
{
\t// Fields
\tpublic byte value__; // 0x0
\tpublic const CardRarityCode R = 1;
\tpublic const CardRarityCode CR = 102;
}

// Namespace: Coly.S2BShared.Master
[MessagePackObject(True)]
[MemoryTable("mst_character_card")]
public class MstCharacterCard : IMasterTable // TypeDefIndex: 2
{
\t// Fields
\t[CompilerGenerated]
\tprivate CharacterCardId <CharacterCardId>k__BackingField; // 0x10
\t[CompilerGenerated]
\tprivate CardRarityCode <CardRarityCode>k__BackingField; // 0x14
\t[CompilerGenerated]
\tprivate List<CardRarityCode> <AllowedRarities>k__BackingField; // 0x18

\t// Properties
\tpublic CharacterCardId CharacterCardId { get; set; }
}
"""


class DumpSchemaTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dump.cs"
            path.write_text(DUMP, encoding="utf-8")
            self.enums, self.tables = parse_dump(path)

    def test_parses_enums_and_memory_tables(self):
        self.assertEqual({"R": 1, "CR": 102}, self.enums["CardRarityCode"])
        self.assertEqual(
            {"CharacterCardId": "CharacterCardId", "CardRarityCode": "CardRarityCode",
             "AllowedRarities": "List<CardRarityCode>"},
            self.tables["mst_character_card"],
        )

    def test_reports_new_fields_and_undefined_codes(self):
        masterdata = [{"mst_character_card": None}, [
            {"CharacterCardId": 1, "CardRarityCode": 103, "AllowedRarities": [1, 104, 0], "NewField": 1},
        ]]

        report = compare(self.enums, self.tables, masterdata)

        self.assertEqual(["NewField"], report["Fields"]["mst_character_card"]["OnlyInMasterdata"])
        self.assertEqual([103], report["UnknownEnumValues"]["mst_character_card.CardRarityCode"]["Values"])
        self.assertEqual([104], report["UnknownEnumValues"]["mst_character_card.AllowedRarities"]["Values"])


if __name__ == "__main__":
    unittest.main()
