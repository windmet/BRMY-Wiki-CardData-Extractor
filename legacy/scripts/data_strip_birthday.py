import json
import csv
import re

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

INPUT_JSON = 'birthday_extract.json'
OUTPUT_CSV = 'birthday_lines.csv'

def clean_text(text):
    if not text:
        return ""
    # 替换各种换行符为 <br>
    text = text.replace('\\n', '<br>').replace('\n', '<br>')
    # 忽略大小写替换女主名字
    text = re.sub(r'heroine_?name', '衣都', text, flags=re.IGNORECASE)
    return text

def main():
    print(f"[*] 正在读取提取好的数据 {INPUT_JSON}...")
    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] 错误: {e}")
        return

    cycle = data.get("TargetCycle", 3)
    chars = data.get("Characters", {})
    texts = data.get("BirthdayTexts", {})

    # ==========================================
    # 1. 确定横向角色的排列顺序（以祠堂恭耶 05/14 为首）
    # ==========================================
    char_list = []
    for cid_str, info in chars.items():
        cid = int(cid_str)
        char_list.append({
            "id": cid,
            "name": info["Name"],
            "month": info["Month"],
            "day": info["Day"]
        })

    # 排序与周期偏移逻辑：
    # 祠堂恭耶 (5月14日) 起点。
    # - 5月14日 ~ 12月31日：偏移量 0 (Cycle 0)
    # - 1月1日 ~ 5月13日：偏移量 1 (Cycle 1)
    def get_cycle_sort_key(char):
        m, d = char["month"], char["day"]
        cycle_offset = 0 if (m > 5 or (m == 5 and d >= 14)) else 1
        return (cycle_offset, m, d)

    sorted_chars = sorted(char_list, key=get_cycle_sort_key)

    # ==========================================
    # 2. 构建纵向行数据 (二维数组构建表格)
    # ==========================================
    rows = []
    
    # 第1行：角色名称表头
    header_row = [""] + [char["name"] for char in sorted_chars]
    rows.append(header_row)

    # 第2行：日期 (根据周期偏移自动计算年份)
    # 三轮在 2026 年 5 月 14 日拉开帷幕：
    # - 5月14日 ~ 12月31日 生日的角色，年份为 2026
    # - 1月1日 ~ 5月13日 生日的角色，年份为 2027
    date_row = [""]
    for char in sorted_chars:
        cycle_offset = get_cycle_sort_key(char)[0]
        display_year = 2026 + cycle_offset
        date_row.append(f"{display_year}/{char['month']:02d}/{char['day']:02d}")
    rows.append(date_row)

    # 第3行：语音文件名占位
    voice_file_row = ["语音文件名"] + [""] * len(sorted_chars)
    rows.append(voice_file_row)

    # 第4~9行：庆典台词 ①/②/③ (J原文与C翻译占位)
    for i in range(1, 4):
        # 原文 J 行
        row_j = [f"庆典台词①J".replace('①', chr(0x2460 + i - 1))]
        for char in sorted_chars:
            cid_str = str(char["id"])
            raw_text = texts.get(cid_str, {}).get(str(i), "")
            row_j.append(clean_text(raw_text))
        rows.append(row_j)
        
        # 翻译 C 行 (留空)
        row_c = [f"庆典台词①C".replace('①', chr(0x2460 + i - 1))] + [""] * len(sorted_chars)
        rows.append(row_c)

    # 第10行往后：1~21号角色祝福语音占位
    # 确保左侧栏目的祝福人顺序严格按照 ID 1 -> 21 排序（即：皇坂逢 为首，麻波麗 为尾）
    blessing_chars_ordered = sorted(char_list, key=lambda x: x["id"])
    
    for bless_char in blessing_chars_ordered:
        bless_name = bless_char["name"]
        rows.append([f"{bless_name}语音J"] + [""] * len(sorted_chars))
        rows.append([f"{bless_name}语音C"] + [""] * len(sorted_chars))

    # ==========================================
    # 3. 输出保存
    # ==========================================
    
    # 导出 CSV
    with open(OUTPUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"[+] CSV表格已生成: {OUTPUT_CSV}")

    # 导出原生 Excel
    if OPENPYXL_AVAILABLE:
        output_xlsx = OUTPUT_CSV.replace('.csv', '.xlsx')
        wb = Workbook()
        ws = wb.active
        ws.title = "Birthday Lines"

        for r_idx, row_data in enumerate(rows, 1):
            for c_idx, cell_value in enumerate(row_data, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=cell_value)
                # 为含有 <br> 的文本开启自动换行并垂直居中
                if isinstance(cell_value, str) and "<br>" in cell_value:
                    cell.alignment = Alignment(wrap_text=True, vertical='center')

        # 调整首列宽度以便查看
        ws.column_dimensions['A'].width = 20
        wb.save(output_xlsx)
        print(f"[+] 原生Excel表已生成: {output_xlsx}")
    else:
        print("[!] 提示: 环境中未安装 openpyxl，跳过生成 .xlsx 文件。可使用 'pip install openpyxl' 安装。")

if __name__ == "__main__":
    main()