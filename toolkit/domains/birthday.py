"""生日台词数据提取 + 导出。"""
from ..core.scanner import walk, load_json, save_json
from ..core.exporter import write_xlsx, json_path, xlsx_path
from ..core.data import clean_text

INPUT_JSON = 'master_data.json'
TARGET_CYCLE = 3


def extract():
    data = load_json(INPUT_JSON)
    characters = {}
    raw_texts = {}

    for obj in walk(data):
        if 'CharacterId' in obj and 'CharacterNameJpn' in obj and 'BirthMonth' in obj:
            cid = obj['CharacterId']
            if 1 <= cid <= 21:
                characters[cid] = {
                    "Name": obj['CharacterNameJpn'],
                    "Month": obj['BirthMonth'],
                    "Day": obj['BirthDay'],
                }
        if 'CharacterBirthdayTextNo' in obj and 'Text' in obj and 'Year' in obj:
            cid = obj.get('CharacterId')
            year = obj.get('Year')
            text_no = obj.get('CharacterBirthdayTextNo')
            if cid and year and text_no:
                raw_texts.setdefault(cid, {}).setdefault(year, {})[text_no] = obj['Text']

    bday_texts = {}
    for cid, info in characters.items():
        month, day = info["Month"], info["Day"]
        target_year = 2026 if (month > 5 or (month == 5 and day >= 14)) else 2027
        bday_texts[cid] = raw_texts.get(cid, {}).get(target_year, {})

    out = json_path('birthday_extract.json')
    save_json({"TargetCycle": TARGET_CYCLE, "Characters": characters, "BirthdayTexts": bday_texts}, out)
    print(f"[+] 提取 {len(characters)} 个角色生日数据 → {out}")
    return characters, bday_texts


def export():
    data = load_json(json_path('birthday_extract.json'))
    chars = data.get("Characters", {})
    texts = data.get("BirthdayTexts", {})

    char_list = []
    for cid_str, info in chars.items():
        cid = int(cid_str)
        char_list.append({"id": cid, "name": info["Name"], "month": info["Month"], "day": info["Day"]})

    def sort_key(c):
        m, d = c["month"], c["day"]
        return (0 if (m > 5 or (m == 5 and d >= 14)) else 1, m, d)

    sorted_chars = sorted(char_list, key=sort_key)

    rows = []
    rows.append([""] + [c["name"] for c in sorted_chars])
    date_row = [""]
    for c in sorted_chars:
        year = 2026 + sort_key(c)[0]
        date_row.append(f"{year}/{c['month']:02d}/{c['day']:02d}")
    rows.append(date_row)
    rows.append(["语音文件名"] + [""] * len(sorted_chars))
    for i in range(1, 4):
        label_j = f"庆典台词{chr(0x2460 + i - 1)}J"
        label_c = f"庆典台词{chr(0x2460 + i - 1)}C"
        rows.append([label_j] + [clean_text(texts.get(str(c["id"]), {}).get(str(i), "")) for c in sorted_chars])
        rows.append([label_c] + [""] * len(sorted_chars))
    for bless_char in sorted(char_list, key=lambda x: x["id"]):
        rows.append([f"{bless_char['name']}语音J"] + [""] * len(sorted_chars))
        rows.append([f"{bless_char['name']}语音C"] + [""] * len(sorted_chars))

    out = xlsx_path('birthday_lines.xlsx')
    write_xlsx(rows, out, sheet_title="Birthday Lines",
               col_widths={'A': 20}, wrap_cols={i for i in range(1, len(sorted_chars) + 1)})


def run():
    extract()
    export()
