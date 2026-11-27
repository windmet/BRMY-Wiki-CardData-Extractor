"""Refresh or incrementally extend the user-maintained V2 template from a story snapshot."""
import argparse
import json
import re
from collections import defaultdict
from copy import copy
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook


def _default_row_formulas(pos):
    return {
        9: (f'=IF(COUNTIF(熟肉链接库!$A$3:$A$1000,M{pos})=0,"待补充",'
            f'IF(COUNTIF(熟肉链接库!$A$3:$A$1000,M{pos})>1,"多条("&COUNTIF(熟肉链接库!$A$3:$A$1000,M{pos})&")",'
            f'IF(ISNUMBER(SEARCH("合集",INDEX(熟肉链接库!$C$3:$C$1000,MATCH(M{pos},熟肉链接库!$A$3:$A$1000,0)))),"合集","已有")))'),
        10: (f'=IF(COUNTIF(熟肉链接库!$A$3:$A$1000,M{pos})=0,"",'
             f'HYPERLINK(INDEX(熟肉链接库!$E$3:$E$1000,MATCH(M{pos},熟肉链接库!$A$3:$A$1000,0)),'
             f'INDEX(熟肉链接库!$E$3:$E$1000,MATCH(M{pos},熟肉链接库!$A$3:$A$1000,0))))'),
        11: f'=IF(COUNTIF(熟肉链接库!$A$3:$A$1000,M{pos})=0,"",INDEX(熟肉链接库!$F$3:$F$1000,MATCH(M{pos},熟肉链接库!$A$3:$A$1000,0)))',
    }


def _rewrite_catalog_refs(sheet, old_last, new_last):
    pattern = re.compile(rf'(剧情总表!\$[A-Z]+\$3:\$[A-Z]+\$){old_last}\b')
    for row in sheet.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith('='):
                updated = pattern.sub(rf'\g<1>{new_last}', cell.value)
                if updated != cell.value:
                    cell.value = updated


def _extend_conditional_formatting(catalog, old_last, new_last):
    pattern = re.compile(rf'([A-Z]+\d+:[A-Z]+){old_last}\b')
    saved = [(str(cf.sqref), list(cf.rules)) for cf in list(catalog.conditional_formatting)]
    catalog.conditional_formatting._cf_rules.clear()
    for sqref, rules in saved:
        updated = ' '.join(pattern.sub(rf'\g<1>{new_last}', part) for part in sqref.split())
        for rule in rules:
            catalog.conditional_formatting.add(updated, rule)


def export(template, snapshot, output):
    if output.resolve() == template.resolve():
        raise ValueError('请另存成品，不覆盖维护模板')
    data = json.loads(snapshot.read_text(encoding='utf-8'))
    book = load_workbook(template)
    catalog = book['剧情总表']
    cast = book['角色出场汇总']
    if '角色别名映射' in book.sheetnames:
        del book['角色别名映射']

    stories = {row[0]: row for row in data['剧情总表'][1:]}
    old_last = catalog.max_row
    while old_last >= 3 and not catalog.cell(old_last, 13).value:
        old_last -= 1
    ids = [catalog.cell(pos, 13).value for pos in range(3, old_last + 1)]
    missing = [sid for sid in ids if sid not in stories]
    if missing:
        raise ValueError(f'快照缺少模板中已有的剧情 ID（共 {len(missing)} 条，例如 {missing[:5]}）')

    owner_names = {}
    for pos, sid in enumerate(ids, 3):
        person = stories[sid][5]
        existing_owner = catalog.cell(pos, 5).value
        if person and existing_owner:
            owner_names.setdefault(person, existing_owner)
    for row in data['剧情总表'][1:]:
        if row[1] == '个人' and row[5] and row[2]:
            owner_names.setdefault(row[5], row[2].split(' / ')[0])
    for _, _, person, name, identity, _, _, _, _ in data['出场证据'][1:]:
        if person and identity == '角色':
            owner_names.setdefault(person, ''.join(name.split()))

    existing_set = set(ids)
    new_ids = [row[0] for row in data['剧情总表'][1:] if row[0] not in existing_set]

    if new_ids:
        ref_row = old_last if old_last >= 3 else 3
        ref_styles = [copy(catalog.cell(ref_row, col)._style) for col in range(1, 14)]
        ref_height = catalog.row_dimensions[ref_row].height
        ref_formulas = {}
        for col in (9, 10, 11):
            val = catalog.cell(ref_row, col).value
            if isinstance(val, str) and val.startswith('='):
                ref_formulas[col] = val
        ref_token = re.compile(rf'\bM{ref_row}\b')

        for offset, sid in enumerate(new_ids, 1):
            pos = old_last + offset
            defaults = _default_row_formulas(pos)
            for col in range(1, 14):
                cell = catalog.cell(pos, col)
                cell._style = copy(ref_styles[col - 1])
            if ref_height is not None:
                catalog.row_dimensions[pos].height = ref_height
            catalog.cell(pos, 13).value = sid
            person = stories[sid][5]
            if person and person in owner_names:
                catalog.cell(pos, 5).value = owner_names[person]
            for col in (9, 10, 11):
                tpl = ref_formulas.get(col)
                catalog.cell(pos, col).value = ref_token.sub(f'M{pos}', tpl) if tpl else defaults[col]

    all_ids = ids + new_ids
    new_last = 2 + len(all_ids)

    entrances = {row[1]: row[6].split(',') for row in data['章节'][1:]}
    speakers = defaultdict(dict)
    for sid, episode, person, name, identity, _, entry, _, count in data['出场证据'][1:]:
        preferred = episode if episode in entrances[episode] else entrances[episode][0]
        if entry != preferred or identity == '玩家':
            continue
        label = ''.join(name.split()) if person else name
        bucket = speakers[sid].setdefault((label, bool(person)), {})
        bucket[episode] = bucket.get(episode, 0) + count

    catalog['H2'] = '出场角色（按剧本署名）'
    cast['A1'] = '角色出场汇总｜按剧情与剧本署名统计，同一话的重读版不重复计数'
    styles = [copy(cell._style) for cell in cast[3]]
    if cast.max_row >= 3:
        cast.delete_rows(3, cast.max_row - 2)

    for pos, sid in enumerate(all_ids, 3):
        row = stories[sid]
        ordered = sorted(speakers[sid].items(), key=lambda pair: (-sum(pair[1].values()), pair[0]))
        series = '部门箱活（banner） / ' + row[4] if row[15] == '部门箱活（banner）' else row[4]
        title = row[2] or row[4]
        release_date = datetime.fromisoformat(row[9][:10]) if row[9] else None
        episode_count = row[11]
        cast_summary = '、'.join(key[0] for key, _ in ordered)
        updates = [
            (1, row[1]),
            (2, series or None),
            (3, title or None),
            (6, release_date),
            (7, episode_count if episode_count not in ('', None) else None),
            (8, cast_summary or None),
        ]
        for column, value in updates:
            catalog.cell(pos, column).value = value
        if not catalog.cell(pos, 5).value and row[5] in owner_names:
            catalog.cell(pos, 5).value = owner_names[row[5]]
        for (name, known), episodes in ordered:
            cast.append([row[1], title, name, '主要角色' if known else '其他署名', len(episodes), sum(episodes.values()), sid])
            for cell, style in zip(cast[cast.max_row], styles):
                cell._style = copy(style)

    catalog.auto_filter.ref = f'A2:M{new_last}'
    cast.auto_filter.ref = f'A2:G{max(2, cast.max_row)}'
    if new_last != old_last and old_last >= 3:
        _extend_conditional_formatting(catalog, old_last, new_last)
        for sheet_name in ('熟肉链接库', '进度看板与待处理'):
            if sheet_name in book.sheetnames:
                _rewrite_catalog_refs(book[sheet_name], old_last, new_last)

    output.parent.mkdir(parents=True, exist_ok=True)
    book.save(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('template', 'snapshot', 'output'):
        parser.add_argument(argument, type=Path)
    export(**vars(parser.parse_args()))
