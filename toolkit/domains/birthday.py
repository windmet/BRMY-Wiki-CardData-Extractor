"""生日台词数据提取 + 导出。"""
from ..core.scanner import load_json, save_json
from ..core.exporter import write_xlsx, json_path, xlsx_path
from ..core.data import clean_text
from ..core.tables import TableCatalog

INPUT_JSON = 'master_data.json'


def _infer_cycle(characters, text_rows):
    years = sorted({row.get('Year') for row in text_rows if isinstance(row.get('Year'), int)})
    if not years:
        raise ValueError('生日台词表没有可用 Year')

    base_year = years[0]
    base_character_ids = {
        row.get('CharacterId') for row in text_rows if row.get('Year') == base_year
    }
    boundary_dates = [
        (info['Month'], info['Day'])
        for cid, info in characters.items()
        if cid in base_character_ids
    ]
    if not boundary_dates:
        raise ValueError('无法从最早生日数据推导周期边界')
    boundary = min(boundary_dates)

    cycle_start_years = []
    for row in text_rows:
        year = row.get('Year')
        info = characters.get(row.get('CharacterId'))
        if not isinstance(year, int) or not info:
            continue
        birthday = (info['Month'], info['Day'])
        cycle_start_years.append(year if birthday >= boundary else year - 1)
    if not cycle_start_years:
        raise ValueError('无法从生日台词与角色生日推导目标周期')

    start_year = max(cycle_start_years)
    return {
        'BaseYear': base_year,
        'StartYear': start_year,
        'Cycle': start_year - base_year + 1,
        'BoundaryMonth': boundary[0],
        'BoundaryDay': boundary[1],
    }


def _resolve_cycle(inferred, target_year=None, target_cycle=None):
    if target_year is not None:
        target_year = int(target_year)
    if target_cycle is not None:
        target_cycle = int(target_cycle)
        if target_cycle < 1:
            raise ValueError('--cycle 必须大于等于 1')

    if target_cycle is not None:
        cycle_year = inferred['BaseYear'] + target_cycle - 1
        if target_year is not None and target_year != cycle_year:
            raise ValueError(
                f'--year {target_year} 与 --cycle {target_cycle} 不一致；'
                f'该 cycle 对应 {cycle_year}'
            )
        target_year = cycle_year

    if target_year is not None and target_year < inferred['BaseYear']:
        raise ValueError(
            f'--year {target_year} 早于第一轮起始年 {inferred["BaseYear"]}'
        )

    start_year = inferred['StartYear'] if target_year is None else target_year
    return {
        **inferred,
        'StartYear': start_year,
        'Cycle': start_year - inferred['BaseYear'] + 1,
        'Selection': 'auto' if target_year is None else 'override',
    }


def _text_format(rows):
    if not rows:
        return 'missing'
    ordered = sorted(rows, key=lambda row: row['CharacterBirthdayTextNo'])
    numbers = [row['CharacterBirthdayTextNo'] for row in ordered]
    targets = [row.get('KeyTargetValue', 0) for row in ordered]
    local_numbers = list(range(1, len(ordered) + 1))
    if numbers == local_numbers and targets == local_numbers:
        return 'key_target_sequence'
    if numbers == local_numbers and not any(targets):
        return 'zero_target_local_numbers'
    if not any(targets):
        return 'zero_target_offset_numbers'
    return 'unknown'


def _same_text_rows(left, right):
    def values(rows):
        return [
            row.get('Text', '')
            for row in sorted(rows, key=lambda row: row['CharacterBirthdayTextNo'])
        ]

    return bool(left) and values(left) == values(right)


def _select_character_texts(raw_rows, character_id, target_year):
    selected = sorted(
        raw_rows.get(character_id, {}).get(target_year, []),
        key=lambda row: row['CharacterBirthdayTextNo'],
    )
    text_format = _text_format(selected)
    previous = raw_rows.get(character_id, {}).get(target_year - 1, [])
    matches_previous_year = _same_text_rows(selected, previous)

    metadata = {
        'TargetYear': target_year,
        'Format': text_format,
        'Status': 'available' if selected else 'not_released',
        'LineCount': len(selected),
        'OriginalTextNos': [row['CharacterBirthdayTextNo'] for row in selected],
        'KeyTargetValues': [row.get('KeyTargetValue', 0) for row in selected],
        'MatchesPreviousYear': matches_previous_year,
    }
    return {
        index: row.get('Text', '') for index, row in enumerate(selected, start=1)
    }, metadata


def extract(session=None, target_year=None, target_cycle=None):
    tables = session.tables if session else TableCatalog(load_json(INPUT_JSON))
    characters = {}
    raw_text_rows = {}

    for obj in tables.require('mst_character'):
        cid = obj['CharacterId']
        if 1 <= cid <= 21:
            characters[cid] = {
                "Name": obj['CharacterNameJpn'],
                "Month": obj['BirthMonth'],
                "Day": obj['BirthDay'],
            }
    text_rows = tables.require('mst_character_birthday_mini_game_text')
    for obj in text_rows:
        cid = obj.get('CharacterId')
        year = obj.get('Year')
        text_no = obj.get('CharacterBirthdayTextNo')
        if cid and year and text_no:
            raw_text_rows.setdefault(cid, {}).setdefault(year, []).append(obj)

    cycle = _resolve_cycle(
        _infer_cycle(characters, text_rows),
        target_year=target_year,
        target_cycle=target_cycle,
    )
    boundary = (cycle['BoundaryMonth'], cycle['BoundaryDay'])
    bday_texts = {}
    text_metadata = {}
    for cid, info in characters.items():
        month, day = info["Month"], info["Day"]
        character_year = cycle['StartYear'] if (month, day) >= boundary else cycle['StartYear'] + 1
        bday_texts[cid], text_metadata[cid] = _select_character_texts(
            raw_text_rows, cid, character_year
        )

    out = json_path('birthday_extract.json')
    save_json({
        "TargetCycle": cycle['Cycle'],
        "CycleStartYear": cycle['StartYear'],
        "CycleBoundary": {
            "Month": cycle['BoundaryMonth'],
            "Day": cycle['BoundaryDay'],
        },
        "CycleSelection": cycle['Selection'],
        "Characters": characters,
        "BirthdayTexts": bday_texts,
        "BirthdayTextMeta": text_metadata,
    }, out)
    print(
        f"[+] 提取 {len(characters)} 个角色生日数据 "
        f"(Cycle {cycle['Cycle']}, {cycle['StartYear']}, {cycle['Selection']}) → {out}"
    )
    return characters, bday_texts


def export():
    data = load_json(json_path('birthday_extract.json'))
    chars = data.get("Characters", {})
    texts = data.get("BirthdayTexts", {})
    cycle_start_year = data.get("CycleStartYear", 2023 + int(data.get("TargetCycle", 3)))
    boundary_data = data.get("CycleBoundary", {"Month": 5, "Day": 14})
    boundary = (boundary_data["Month"], boundary_data["Day"])

    char_list = []
    for cid_str, info in chars.items():
        cid = int(cid_str)
        char_list.append({"id": cid, "name": info["Name"], "month": info["Month"], "day": info["Day"]})

    def sort_key(c):
        m, d = c["month"], c["day"]
        return (0 if (m, d) >= boundary else 1, m, d)

    sorted_chars = sorted(char_list, key=sort_key)

    rows = []
    rows.append([""] + [c["name"] for c in sorted_chars])
    date_row = [""]
    for c in sorted_chars:
        year = cycle_start_year + sort_key(c)[0]
        date_row.append(f"{year}/{c['month']:02d}/{c['day']:02d}")
    rows.append(date_row)
    rows.append(["语音文件名"] + [""] * len(sorted_chars))
    line_count = max(
        (
            int(number)
            for character_texts in texts.values()
            for number in character_texts.keys()
        ),
        default=3,
    )
    for i in range(1, line_count + 1):
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


def run(session=None, target_year=None, target_cycle=None):
    extract(session=session, target_year=target_year, target_cycle=target_cycle)
    export()
