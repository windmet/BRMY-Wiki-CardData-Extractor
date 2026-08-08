import json
from openpyxl import Workbook

def extract_music_data(json_file_path="Music_Database.json", output_xlsx_path="music_data.xlsx"):
    print(f"[*] 正在读取 {json_file_path} ...")
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] 无法加载JSON文件: {e}")
        return
        
    headers = [
        "歌曲编号", "曲目名", "作者/歌手", 
        "音频文件名", "封面文件名", "歌曲长度"
    ]
    
    rows = []
    
    for mid, m_info in data.items():
        row = [
            m_info.get("MusicId", ""),
            m_info.get("DisplayName", ""),
            m_info.get("ArtistName", ""),
            m_info.get("AudioFileName", ""),
            m_info.get("JacketFileName", ""),
            m_info.get("DurationStr", "")
        ]
        rows.append(row)
        
    # 构建 Excel
    print("[*] 正在写入 Excel ...")
    wb = Workbook()
    ws = wb.active
    ws.title = "Music_Data"
    ws.append(headers)
    
    for row in rows:
        cleaned_row = []
        for item in row:
            if isinstance(item, str) and item.isdigit():
                cleaned_row.append(int(item)) # 转化为纯数字，方便后续Excel排序
            else:
                cleaned_row.append(item)
        ws.append(cleaned_row)
        
    # 稍微调整一下列宽让表好看点
    column_widths = {'A': 12, 'B': 35, 'C': 35, 'D': 30, 'E': 35, 'F': 12}
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width
        
    wb.save(output_xlsx_path)
    print(f"[+] 音乐对照表 (.xlsx) 已成功生成至: {output_xlsx_path}")

def main():
    extract_music_data()

if __name__ == "__main__":
    main()