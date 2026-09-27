import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lz4.block
import msgpack

from toolkit.core.masterdata import ensure_masterdata_json, sha256_file
from toolkit.core.s2b_parser import S2BDecodeError


def _ext99_object(value):
    payload = msgpack.packb(value, use_bin_type=True)
    size_header = b"\xce" + struct.pack(">I", len(payload))
    compressed = lz4.block.compress(payload, store_size=False)
    return msgpack.packb(
        msgpack.ExtType(99, size_header + compressed), use_bin_type=True
    )


def _write_masterdata(path, card_id):
    data = [
        {"mst_character_card": 0},
        [{"CharacterCardId": card_id, "CharacterCardName": f"Card {card_id}"}],
    ]
    path.write_bytes(b"".join(_ext99_object(value) for value in data))


class MasterDataCacheTests(unittest.TestCase):
    def test_status_logging_does_not_fail_on_cp1252_console(self):
        class Cp1252Stream(io.StringIO):
            @property
            def encoding(self):
                return "cp1252"

            def write(self, value):
                value.encode(self.encoding)
                return super().write(value)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "master_data.s2b"
            _write_masterdata(source, 1)
            stream = Cp1252Stream()

            with patch("sys.stdout", stream):
                result = ensure_masterdata_json(source, root)

            self.assertFalse(result.reused)
            self.assertIn("master_data.json", stream.getvalue())

    def test_cache_is_reused_only_for_the_same_source_and_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "master_data.s2b"
            _write_masterdata(source, 1)

            first = ensure_masterdata_json(source, root)
            second = ensure_masterdata_json(source, root)

            self.assertFalse(first.reused)
            self.assertTrue(second.reused)
            self.assertEqual(first.source_sha256, second.source_sha256)

            manifest_path = Path(second.manifest_path)
            stale_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            stale_manifest["parser_version"] = 0
            manifest_path.write_text(
                json.dumps(stale_manifest), encoding="utf-8"
            )
            parser_refresh = ensure_masterdata_json(source, root)
            self.assertFalse(parser_refresh.reused)

            _write_masterdata(source, 2)
            third = ensure_masterdata_json(source, root)
            decoded = json.loads(Path(third.json_path).read_text(encoding="utf-8"))

            self.assertFalse(third.reused)
            self.assertNotEqual(first.source_sha256, third.source_sha256)
            self.assertEqual(2, decoded[1][0]["CharacterCardId"])

            manifest = json.loads(
                Path(third.manifest_path).read_text(encoding="utf-8")
            )
            self.assertEqual(third.source_sha256, manifest["source"]["sha256"])
            self.assertEqual(
                sha256_file(third.json_path), manifest["output"]["sha256"]
            )

    def test_decode_failure_does_not_replace_last_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "master_data.s2b"
            _write_masterdata(source, 7)
            valid = ensure_masterdata_json(source, root)
            original_json = Path(valid.json_path).read_bytes()
            original_manifest = Path(valid.manifest_path).read_bytes()

            source.write_bytes(
                msgpack.packb(msgpack.ExtType(99, b"broken"), use_bin_type=True)
            )

            with self.assertRaises(S2BDecodeError):
                ensure_masterdata_json(source, root)

            self.assertEqual(original_json, Path(valid.json_path).read_bytes())
            self.assertEqual(original_manifest, Path(valid.manifest_path).read_bytes())

    def test_unknown_extension_is_rejected_for_masterdata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "master_data.s2b"
            source.write_bytes(
                msgpack.packb(msgpack.ExtType(42, b"unknown"), use_bin_type=True)
            )

            with self.assertRaisesRegex(S2BDecodeError, "extension type: 42"):
                ensure_masterdata_json(source, root)


if __name__ == "__main__":
    unittest.main()
