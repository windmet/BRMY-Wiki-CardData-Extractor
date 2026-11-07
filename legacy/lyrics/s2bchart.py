import os
import json
import lz4.block
import msgpack

def ext_hook(code, data):
    """
    处理 MsgPack 扩展类型 99 (LZ4 压缩块)
    不管是 C7 (ext 8) 还是 C8 (ext 16)，解密逻辑在这里完全一致
    """
    if code == 99:
        # 读取前 5 字节获取解压后的原始大小
        decompressed_size = msgpack.unpackb(data[:5], strict_map_key=False)
        try:
            # 使用 lz4 还原数据
            decompressed_data = lz4.block.decompress(data[5:], uncompressed_size=decompressed_size)
            return msgpack.unpackb(decompressed_data, strict_map_key=False)
        except Exception as e:
            print(f"Decompression error: {e}")
            return None
    else:
        return msgpack.ExtType(code, data)

def clean_data(obj):
    """
    递归清洗解包后的数据，使其完全兼容 JSON 格式
    """
    if isinstance(obj, dict):
        return {str(clean_data(k)): clean_data(v) for k, v in obj.items()}
    elif isinstance(obj, list) or isinstance(obj, tuple):
        return [clean_data(i) for i in obj]
    elif isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return f"<hex:{obj.hex()}>"
    else:
        return obj

def process_chart_files(input_folder, output_folder):
    for filename in os.listdir(input_folder):
        if filename.endswith(".s2bchart"):
            file_path = os.path.join(input_folder, filename)
            try:
                with open(file_path, "rb") as f:
                    # 使用 Unpacker 自动识别 C7/C8 外壳并解析
                    unpacker = msgpack.Unpacker(f, raw=False, ext_hook=ext_hook, strict_map_key=False)
                    raw_data = [i for i in unpacker]
                    
                    # 递归清理无法被 JSON 序列化的特殊对象
                    clean_json_data = clean_data(raw_data)
                    
                    # 导出为 JSON
                    json_name = f"{filename}.json"
                    json_path = os.path.join(output_folder, json_name)
                    with open(json_path, "w", encoding="utf-8") as out_f:
                        json.dump(clean_json_data, out_f, ensure_ascii=False, indent=4)
                    
                    print(f"[+] 成功解密: '{filename}' -> 已导出为 JSON。")
                        
            except Exception as e:
                print(f"[-] 处理 {filename} 时发生错误: {e}")

def main():
    script_folder = os.path.dirname(os.path.abspath(__file__))
    input_folder = script_folder
    output_folder = os.path.join(script_folder, "extracted_charts")
    
    os.makedirs(output_folder, exist_ok=True)
    print("正在扫描并解密 .s2bchart 谱面文件...")
    process_chart_files(input_folder, output_folder)
    print("解密完成！")

if __name__ == "__main__":
    main()