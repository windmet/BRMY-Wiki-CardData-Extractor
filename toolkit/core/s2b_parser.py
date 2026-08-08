"""s2b 文件解析公共逻辑 —— 处理 MsgPack + LZ4 压缩（ext type 99）。"""
import json
import lz4.block
import msgpack
from datetime import datetime


def ext_hook(code, data):
    """MsgPack 扩展类型 99 (LZ4 压缩块)。"""
    if code == 99:
        decompressed_size = msgpack.unpackb(data[:5], strict_map_key=False)
        try:
            decompressed = lz4.block.decompress(data[5:], uncompressed_size=decompressed_size)
            return msgpack.unpackb(decompressed, strict_map_key=False)
        except Exception as e:
            print(f"  [!] LZ4 decompress error: {e}")
            return None
    return msgpack.ExtType(code, data)


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


def parse_s2b_file(file_path):
    """解析单个 .s2b* 文件，返回清洗后的 JSON 数据。"""
    with open(file_path, "rb") as f:
        unpacker = msgpack.Unpacker(f, raw=False, ext_hook=ext_hook, strict_map_key=False)
        raw = [i for i in unpacker]
    return clean_data(raw)


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
