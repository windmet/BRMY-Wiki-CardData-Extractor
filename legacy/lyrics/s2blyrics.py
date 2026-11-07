import os
import json
import lz4.block
import msgpack

def ext_hook(code, data):
    """
    处理 MsgPack 扩展类型 99 (LZ4 压缩块)
    """
    if code == 99:
        # 解包前 5 字节获取解压后大小
        decompressed_size = msgpack.unpackb(data[:5], strict_map_key=False)
        try:
            # 执行 LZ4 解压
            decompressed_data = lz4.block.decompress(data[5:], uncompressed_size=decompressed_size)
            return msgpack.unpackb(decompressed_data, strict_map_key=False)
        except Exception as e:
            print(f"Decompression error: {e}")
            return None
    else:
        return msgpack.ExtType(code, data)

def clean_data(obj):
    """
    递归清洗数据，处理 bytes 类型，使其兼容 JSON
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

def format_to_lrc_time(seconds):
    """
    将浮点秒数转换为 LRC 标准格式 [分:秒.厘秒] (如 7.66 -> [00:07.66])
    """
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    # 取小数点后两位（厘秒）
    centiseconds = int(round((seconds - int(seconds)) * 100))
    
    # 边界进位处理
    if centiseconds == 100:
        secs += 1
        centiseconds = 0
    if secs >= 60:
        minutes += 1
        secs -= 60
        
    return f"[{minutes:02d}:{secs:02d}.{centiseconds:02d}]"

def convert_to_lrc(clean_json_data, lrc_output_path):
    """
    将解出来的 JSON 数据转换成标准的 LRC 歌词格式
    """
    try:
        # s2blyrics 的最内层歌词列表通常位于 data[0][0]
        lyrics_list = clean_json_data[0][0]
        lrc_lines = []
        
        for item in lyrics_list:
            if isinstance(item, list) and len(item) >= 3:
                # item[0]: 序号, item[1]: 时间戳(秒), item[2]: 歌词内容
                timestamp_sec = item[1]
                lyric_text = str(item[2]).strip() if item[2] else ""
                
                # 转换时间轴并拼接歌词
                lrc_time = format_to_lrc_time(timestamp_sec)
                lrc_lines.append(f"{lrc_time}{lyric_text}")
                
        # 写入带 UTF-8 BOM 的歌词文件，兼容性最好
        with open(lrc_output_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(lrc_lines))
        return True
    except Exception as e:
        print(f"[-] 转换为 LRC 失败: {e}")
        return False

def process_lyrics_files(input_folder, output_folder):
    for filename in os.listdir(input_folder):
        if filename.endswith(".s2blyrics"):
            file_path = os.path.join(input_folder, filename)
            try:
                with open(file_path, "rb") as f:
                    unpacker = msgpack.Unpacker(f, raw=False, ext_hook=ext_hook, strict_map_key=False)
                    raw_data = [i for i in unpacker]
                    
                    # 递归清理
                    clean_json_data = clean_data(raw_data)
                    
                    # 1. 保存为完整 JSON
                    json_name = f"{filename}.json"
                    json_path = os.path.join(output_folder, json_name)
                    with open(json_path, "w", encoding="utf-8") as out_f:
                        json.dump(clean_json_data, out_f, ensure_ascii=False, indent=4)
                    
                    # 2. 保存为 LRC 歌词
                    lrc_name = f"{os.path.splitext(filename)[0]}.lrc"
                    lrc_path = os.path.join(output_folder, lrc_name)
                    
                    lrc_ok = convert_to_lrc(clean_json_data, lrc_path)
                    
                    if lrc_ok:
                        print(f"[+] 成功解析: '{filename}' -> 导出 JSON 及 LRC 字幕成功！")
                    else:
                        print(f"[!] 成功解析: '{filename}' 仅导出 JSON（LRC 转换失败）。")
                        
            except Exception as e:
                print(f"[-] 处理 {filename} 时发生错误: {e}")

def main():
    script_folder = os.path.dirname(os.path.abspath(__file__))
    input_folder = script_folder
    output_folder = os.path.join(script_folder, "extracted_lyrics")
    
    os.makedirs(output_folder, exist_ok=True)
    print("开始解析 .s2blyrics 歌词文件...")
    process_lyrics_files(input_folder, output_folder)
    print("全部处理完成！")

if __name__ == "__main__":
    main()