"""s2b 文件解析公共逻辑 —— 处理 MsgPack + LZ4 压缩（ext type 99）。"""
import json
from .output import record_output
import lz4.block
import msgpack
from datetime import datetime


class S2BDecodeError(ValueError):
    """Raised when an S2B extension block cannot be decoded safely."""


def decode_ext99(data):
    """Decode one ext99 MsgPack + LZ4 block, failing closed on malformed data."""
    if len(data) < 6:
        raise S2BDecodeError("ext99 block is too short")
    try:
        decompressed_size = msgpack.unpackb(data[:5], strict_map_key=False)
    except Exception as exc:
        raise S2BDecodeError("ext99 size header is invalid") from exc
    if not isinstance(decompressed_size, int) or decompressed_size < 0:
        raise S2BDecodeError(f"ext99 size is invalid: {decompressed_size!r}")
    try:
        decompressed = lz4.block.decompress(
            data[5:], uncompressed_size=decompressed_size
        )
    except Exception as exc:
        raise S2BDecodeError("ext99 LZ4 decompression failed") from exc
    if len(decompressed) != decompressed_size:
        raise S2BDecodeError(
            f"ext99 size mismatch: expected {decompressed_size}, got {len(decompressed)}"
        )
    try:
        return msgpack.unpackb(decompressed, raw=False, strict_map_key=False)
    except Exception as exc:
        raise S2BDecodeError("ext99 payload is not valid MsgPack") from exc


def ext_hook(code, data):
    """MsgPack 扩展类型 99 (LZ4 压缩块)。"""
    if code == 99:
        return decode_ext99(data)
    return msgpack.ExtType(code, data)


def strict_ext_hook(code, data):
    if code == 99:
        return decode_ext99(data)
    raise S2BDecodeError(f"unsupported MsgPack extension type: {code}")


def clean_data(obj):
    """递归清洗，确保 JSON 兼容。"""
    if isinstance(obj, dict):
        return {str(clean_data(k)): clean_data(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [clean_data(i) for i in obj]
    elif isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return f"<hex:{obj.hex()}>"
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, msgpack.ext.Timestamp):
        return obj.to_datetime().isoformat()
    elif isinstance(obj, msgpack.ExtType):
        return f"<ExtType code:{obj.code} data:{obj.data.hex()}>"
    return obj


def parse_s2b_file(file_path, *, strict_extensions=False):
    """解析单个 .s2b* 文件，返回清洗后的 JSON 数据。"""
    hook = strict_ext_hook if strict_extensions else ext_hook
    with open(file_path, "rb") as f:
        unpacker = msgpack.Unpacker(f, raw=False, ext_hook=hook, strict_map_key=False)
        raw = [i for i in unpacker]
    return clean_data(raw)


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    record_output(path)
