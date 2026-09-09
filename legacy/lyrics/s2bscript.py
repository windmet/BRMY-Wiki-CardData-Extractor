import os
import json
import lz4.block
import msgpack
from datetime import datetime

def ext_hook(code, data):
    """
    处理 MsgPack 的扩展类型。
    对应 s2bscript 中的 type 99 (LZ4 压缩块)。
    """
    if code == 99:
        # 前 5 个字节解出原始大小
        decompressed_size = msgpack.unpackb(data[:5], strict_map_key=False)
        try:
            # 使用 lz4 解压后面的数据
            decompressed_data = lz4.block.decompress(data[5:], uncompressed_size=decompressed_size)
            # 解压出来的依然是 msgpack，再次解析
            return msgpack.unpackb(decompressed_data, strict_map_key=False)
        except Exception as decompress_error:
            print(f"Decompression error: {decompress_error}")
            return None
    else:
        return msgpack.ExtType(code, data)

def clean_data(obj):
    """
    递归处理解包后的数据，将不能直接转为 JSON 的类型（如 bytes, datetime, Msgpack ExtType）
    转换为字符串，防止 json.dump 报错。
    """
    if isinstance(obj, dict):
        # JSON 的 key 必须是字符串，所以这里强制 str(k)
        return {str(clean_data(k)): clean_data(v) for k, v in obj.items()}
    elif isinstance(obj, list) or isinstance(obj, tuple):
        return [clean_data(i) for i in obj]
    elif isinstance(obj, bytes):
        try:
            # 尝试按 UTF-8 解码字符串
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            # 解码失败说明是纯二进制数据，转为十六进制文本
            return f"<hex:{obj.hex()}>"
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, msgpack.ext.Timestamp):
        return obj.to_datetime().isoformat()
    elif isinstance(obj, msgpack.ExtType):
        return f"<ExtType code:{obj.code} data:{obj.data.hex()}>"
    else:
        return obj

def process_files(input_folder, output_folder):
    for filename in os.listdir(input_folder):
        if filename.endswith(".s2bscript"):
            file_path = os.path.join(input_folder, filename)
            try:
                with open(file_path, "rb") as f:
                    # 使用 ext_hook 处理压缩块
                    obj = msgpack.Unpacker(f, raw=False, ext_hook=ext_hook, strict_map_key=False)
                    
                    # 读取所有解析出来的对象
                    raw_data = [i for i in obj]
                    
                    # 清洗数据，确保 100% 兼容 JSON
                    clean_json_data = clean_data(raw_data)

                    # 导出为完整 JSON
                    json_output_path = os.path.join(output_folder, f"{filename}.json")
                    with open(json_output_path, "w", encoding="utf-8") as out_f:
                        # indent=4 保证输出的 JSON 格式美观且易于阅读
                        json.dump(clean_json_data, out_f, ensure_ascii=False, indent=4)

                    print(f"[成功] 提取并保存: {filename}.json")
            except Exception as e:
                print(f"[错误] 处理 {filename} 失败: {str(e)}")

def main():
    script_folder = os.path.dirname(os.path.abspath(__file__))
    input_folder = script_folder  # 当前目录作为输入目录
    output_folder = os.path.join(script_folder, "json_output") # 输出到一个新文件夹
    
    os.makedirs(output_folder, exist_ok=True)
    print("开始提取完整 JSON 数据...")
    process_files(input_folder, output_folder)
    print("处理完毕！")

if __name__ == "__main__":
    main()