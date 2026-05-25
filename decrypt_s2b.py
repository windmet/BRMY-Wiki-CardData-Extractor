import msgpack
import lz4.block
import zlib
import json
import lzma  # 新增：导入 LZMA 库
from datetime import datetime
from collections import Counter
import os

def try_decompress(data, tag="unknown"):
    """尝试多种解压方式，并打印诊断信息"""
    
    # 1. 尝试 lz4（带解压大小）
    try:
        size = msgpack.unpackb(data[:5])
        decompressed = lz4.block.decompress(data[5:], uncompressed_size=size)
        #print(f"[+] {tag}: lz4(带size) 解压成功, size={size}")
        return decompressed
    except Exception:
        pass

    # 2. 尝试 lz4（不带size）
    try:
        decompressed = lz4.block.decompress(data)
        print(f"[+] {tag}: lz4(无size) 解压成功, len={len(decompressed)}")
        return decompressed
    except Exception:
        pass

    # 3. 尝试 zlib
    try:
        decompressed = zlib.decompress(data)
        print(f"[+] {tag}: zlib 解压成功, len={len(decompressed)}")
        return decompressed
    except Exception:
        pass

    # 4. 尝试 raw inflate (wbits=-15)
    try:
        decompressed = zlib.decompress(data, wbits=-15)
        print(f"[+] {tag}: raw inflate 解压成功, len={len(decompressed)}")
        return decompressed
    except Exception:
        pass

    # ================= 新增：LZMA 解压逻辑 =================
    # 5. 尝试标准 LZMA
    try:
        decompressed = lzma.decompress(data)
        print(f"[+] {tag}: 标准 LZMA 解压成功, len={len(decompressed)}")
        return decompressed
    except Exception:
        pass

    # 6. 尝试 Unity 变种 LZMA (通常跳过前面 5 个或 13 个自定义头部字节)
    try:
        # 尝试跳过 5 字节
        decompressed = lzma.decompress(data[5:])
        print(f"[+] {tag}: 偏移5字节 LZMA 解压成功, len={len(decompressed)}")
        return decompressed
    except Exception:
        pass
        
    try:
        # 尝试跳过 13 字节 (Unity 常用)
        # 使用 RAW 格式并手动指定 filter
        filter_chain = [{"id": lzma.FILTER_LZMA1, "dict_size": 2**23}]
        decompressed = lzma.decompress(data[13:], format=lzma.FORMAT_RAW, filters=filter_chain)
        print(f"[+] {tag}: RAW LZMA (偏移13字节) 解压成功, len={len(decompressed)}")
        return decompressed
    except Exception:
        pass
    # ========================================================

    print(f"[!] {tag}: 所有解压方式都失败，保存原始数据以供分析")
    os.makedirs("debug_dump", exist_ok=True)
    # 用时间戳或哈希命名避免覆盖
    dump_name = f"debug_dump/{tag}_raw_{len(data)}.bin"
    with open(dump_name, "wb") as out:
        out.write(data)
    return data

def ext_hook(code, data):
    """处理 msgpack 扩展类型"""
    if code == 99:
        #print("[*] 遇到扩展类型 99 (疑似加密/压缩块), 尝试解压...")
        decompressed = try_decompress(data, tag="ext99")
        try:
            # 尝试把解压出来的东西再当做 msgpack 解析
            unpacked = msgpack.unpackb(decompressed, raw=False)
            #print("[+] 扩展类型 99 解压并解码 MsgPack 成功!")
            return unpacked
        except Exception as e:
            print("[-] 扩展类型 99 解码 MsgPack 失败 (可能是纯文本或其他格式):", e)
            # 如果不是 msgpack，尝试直接转成字符串
            try:
                return decompressed.decode('utf-8')
            except:
                return f"<Binary Data: {len(decompressed)} bytes>"
    else:
        return msgpack.ExtType(code, data)

def json_serial(obj):
    """处理时间戳序列化"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, msgpack.ext.Timestamp):
        return obj.to_datetime().isoformat()
    raise TypeError(f"Unsupported type: {type(obj)}")

def main(input_file="master_data.s2b", output_file="master_data.json"):
    print(f"[*] 开始解析 {input_file} ...")
    with open(input_file, "rb") as f:
        raw = f.read()

    unpacker = msgpack.Unpacker(ext_hook=ext_hook, raw=False)
    unpacker.feed(raw)

    objs = []
    for i, obj in enumerate(unpacker):
        objs.append(obj)

    print(f"[*] 成功解码总对象数: {len(objs)}")

    # 保存 JSON
    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(objs, out, default=json_serial, ensure_ascii=False, indent=2)
    print(f"[+] 已保存到 {output_file}")

if __name__ == "__main__":
    main()