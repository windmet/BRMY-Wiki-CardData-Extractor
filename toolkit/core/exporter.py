"""通用导出：XLSX + 输出目录管理。"""
import os

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment
    OPENPYXL = True
except ImportError:
    OPENPYXL = False

JSON_DIR = 'json_output'
XLSX_DIR = 'xlsx_output'


def ensure_dirs():
    os.makedirs(JSON_DIR, exist_ok=True)
    os.makedirs(XLSX_DIR, exist_ok=True)


def json_path(filename):
    ensure_dirs()
    return os.path.join(JSON_DIR, filename)


def xlsx_path(filename):
    ensure_dirs()
    return os.path.join(XLSX_DIR, filename)


def write_xlsx(rows, path, headers=None, sheet_title="Sheet1", col_widths=None, wrap_cols=None):
    if not OPENPYXL:
        print("  [!] openpyxl 未安装，跳过 xlsx 生成")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title

    if headers:
        ws.append(headers)

    for row in rows:
        cleaned = []
        for item in row:
            if isinstance(item, str) and item.isdigit():
                cleaned.append(int(item))
            else:
                cleaned.append(item)
        ws.append(cleaned)

    if col_widths:
        for col_letter, width in col_widths.items():
            ws.column_dimensions[col_letter].width = width

    if wrap_cols:
        for r_idx in range(2, ws.max_row + 1):
            for c_idx in wrap_cols:
                cell = ws.cell(row=r_idx, column=c_idx + 1)
                if cell.value and isinstance(cell.value, str) and '<br>' in str(cell.value):
                    cell.alignment = Alignment(wrap_text=True, vertical='center')

    wb.save(path)
    print(f"  [xlsx] {path}")
