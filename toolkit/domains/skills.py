"""技能分类与索引：SP 六大类 × 细分效果、自动技能（含图标与资源包）、逐卡技能标签与新机制漂移监控。

本域只读 masterdata，零额外下载，不修改任何现有 cards_data.xlsx 列序与文案。
"""
from __future__ import annotations

from collections import defaultdict
import html
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries

from ..core.data import ATTRIBUTE_MAP, PIECE_MAP, RARITY_MAP
from ..core.exporter import audit_path, save_workbook_safely, xlsx_path
from ..core.output import record_warning
from ..core.scanner import save_json
from ..core.skill_taxonomy import (
    AUTO_EFFECTS,
    LEADER_EFFECTS,
    PANDORA_BOX_CLIENT_VERSION,
    PANDORA_BOX_POOL,
    PANDORA_BOX_TOTAL_WEIGHT,
    SHOWER_LEGACY_TABLE,
    SP_EFFECTS,
    expand_sp_tag,
    format_sp_categories,
    legacy_percentage_note,
)
from ..core.skill_text import SkillTextRenderer

NOTICE_SKILL_RE = re.compile(
    r'SHOWER|シャワー|スキル|出現確率|バランス調整|オートスキル|SPスキル',
    re.IGNORECASE,
)


def _active(rows):
    return [row for row in rows if isinstance(row, dict) and row.get('IsActive', True)]


def _plain_html(text: str) -> str:
    cleaned = html.unescape(re.sub(r'<[^>]+>', ' ', str(text or '')))
    return re.sub(r'\s+', ' ', cleaned).strip()


def extract(session):
    tables = session.tables
    renderer = SkillTextRenderer(tables, piece_labels=PIECE_MAP)

    characters = {
        row['CharacterId']: row.get('CharacterNameJpn', f"角色{row['CharacterId']}")
        for row in tables.rows('mst_character') + tables.rows('mst_character_collaboration')
        if 'CharacterId' in row
    }
    cards = {
        row['CharacterCardId']: row
        for row in _active(tables.require('mst_character_card'))
        if 'CharacterCardId' in row
    }

    sp_effects = {
        row['SpSkillEffectId']: row
        for row in tables.require('mst_sp_skill_effect')
        if 'SpSkillEffectId' in row
    }
    auto_effects = {
        row['AutoSkillEffectId']: row
        for row in tables.require('mst_auto_skill_effect')
        if 'AutoSkillEffectId' in row
    }
    leader_effects = {
        row['LeaderSkillEffectId']: row
        for row in tables.require('mst_leader_skill_effect')
        if 'LeaderSkillEffectId' in row
    }

    sp_by_card = defaultdict(dict)
    for row in _active(tables.require('mst_character_card_sp_skill_level')):
        cid = row.get('CharacterCardId')
        lv = row.get('SpSkillLevel')
        if cid in cards and lv is not None:
            sp_by_card[cid][int(lv)] = row

    combi_by_card = {}
    for row in _active(tables.rows('mst_character_card_sp_skill_with_combi')):
        cid = row.get('CharacterCardId')
        if cid in cards:
            combi_by_card[cid] = row

    auto_by_card = defaultdict(dict)
    for row in _active(tables.require('mst_character_card_auto_skill_level')):
        cid = row.get('CharacterCardId')
        lv = row.get('AutoSkillLevel')
        if cid in cards and lv is not None:
            auto_by_card[cid][int(lv)] = row

    leader_by_card = {}
    for row in _active(tables.rows('mst_character_card_leader_skill')):
        cid = row.get('CharacterCardId')
        if cid in cards:
            leader_by_card[cid] = row

    # Usage tracking & drift detection
    sp_base_cards = defaultdict(list)
    sp_combi_cards = defaultdict(list)
    auto_cards = defaultdict(list)
    leader_cards = defaultdict(list)
    issues = []

    card_index = []
    for cid in sorted(cards):
        card = cards[cid]
        sp_levels = sp_by_card.get(cid, {})
        sp_lv1 = sp_levels.get(1) or (sp_levels[min(sp_levels)] if sp_levels else None)
        sp_max = sp_levels[max(sp_levels)] if sp_levels else None
        combi = combi_by_card.get(cid)
        auto_levels = auto_by_card.get(cid, {})
        auto_lv1 = auto_levels.get(1) or (auto_levels[min(auto_levels)] if auto_levels else None)
        auto_max = auto_levels[max(auto_levels)] if auto_levels else None
        ldr = leader_by_card.get(cid)

        sp_id = sp_lv1.get('SpSkillEffectId') if sp_lv1 else None
        sp_meta = sp_effects.get(sp_id, {}) if sp_id is not None else {}
        sp_cats_zh, sp_cats_ids, sp_cats_enum = format_sp_categories(sp_meta.get('SpSkillCategoryCodeList'))
        sp_sub = SP_EFFECTS[sp_id][1] if sp_id in SP_EFFECTS else (f'未收录SP效果({sp_id})' if sp_id is not None else '')
        sp_expanded = expand_sp_tag(sp_id, sp_lv1) if sp_lv1 else ''
        sp_lv1_desc = renderer.wiki_text(sp_lv1.get('SkillDescription', ''), sp_lv1).replace('\n', '') if sp_lv1 else ''
        sp_max_desc = renderer.wiki_text(sp_max.get('SkillDescription', ''), sp_max).replace('\n', '') if sp_max else ''
        if sp_id is not None:
            sp_base_cards[sp_id].append(cid)

        combi_id = combi.get('SpSkillEffectId') if combi else None
        combi_meta = sp_effects.get(combi_id, {}) if combi_id is not None else {}
        combi_cats_zh, _, _ = format_sp_categories(combi_meta.get('SpSkillCategoryCodeList'))
        combi_sub = SP_EFFECTS[combi_id][1] if combi_id in SP_EFFECTS else (f'未收录SP效果({combi_id})' if combi_id is not None else '')
        combi_expanded = expand_sp_tag(combi_id, combi) if combi else ''
        combi_desc = renderer.wiki_text(combi.get('SkillDescription', ''), combi).replace('\n', '') if combi else ''
        if combi_id is not None:
            sp_combi_cards[combi_id].append(cid)

        auto_id = auto_lv1.get('AutoSkillEffectId') if auto_lv1 else None
        auto_meta = auto_effects.get(auto_id, {}) if auto_id is not None else {}
        auto_name = auto_meta.get('SkillName', '')
        auto_lv1_desc = renderer.wiki_text(auto_meta.get('SkillDescription', ''), auto_lv1).replace('\n', '') if auto_lv1 else ''
        auto_max_desc = renderer.wiki_text(auto_meta.get('SkillDescription', ''), auto_max).replace('\n', '') if auto_max else ''
        auto_legacy = legacy_percentage_note(auto_lv1_desc) or legacy_percentage_note(auto_max_desc)
        if auto_id is not None:
            auto_cards[auto_id].append(cid)

        ldr_id = ldr.get('LeaderSkillEffectId') if ldr else None
        ldr_meta = leader_effects.get(ldr_id, {}) if ldr_id is not None else {}
        ldr_label = LEADER_EFFECTS.get(ldr_id, f'未收录队长效果({ldr_id})' if ldr_id is not None else '')
        ldr_desc = renderer.wiki_text(ldr_meta.get('SkillDescription', ''), ldr).replace('\n', '') if ldr else ''
        if ldr_id is not None:
            leader_cards[ldr_id].append(cid)

        combi_char_id = card.get('CombiCharacterId') or 0
        card_index.append({
            'card_id': cid,
            'char_name': characters.get(card.get('CharacterId'), ''),
            'card_name': card.get('CharacterCardName', ''),
            'rarity': RARITY_MAP.get(card.get('CardRarityCode'), card.get('CardRarityCode')),
            'attribute': ATTRIBUTE_MAP.get(card.get('CardAttributeCode'), card.get('CardAttributeCode')),
            'sp_name': card.get('SpSkillName', ''),
            'sp_effect_id': sp_id,
            'sp_skill_effect': sp_meta.get('SkillEffect', ''),
            'sp_categories_zh': sp_cats_zh,
            'sp_subtype': sp_sub,
            'sp_expanded_tag': sp_expanded,
            'sp_lv1_cost': sp_lv1.get('SkillCost') if sp_lv1 else None,
            'sp_max_cost': sp_max.get('SkillCost') if sp_max else None,
            'sp_lv1_desc': sp_lv1_desc,
            'sp_max_desc': sp_max_desc,
            'combi_char': characters.get(combi_char_id, '') if combi_char_id else '',
            'combi_effect_id': combi_id,
            'combi_categories_zh': combi_cats_zh,
            'combi_subtype': combi_sub,
            'combi_expanded_tag': combi_expanded,
            'combi_desc': combi_desc,
            'auto_effect_id': auto_id,
            'auto_name': auto_name,
            'auto_icon': auto_meta.get('IconFileName', ''),
            'auto_lv1_desc': auto_lv1_desc,
            'auto_max_desc': auto_max_desc,
            'auto_legacy_note': auto_legacy,
            'leader_effect_id': ldr_id,
            'leader_label': ldr_label,
            'leader_desc': ldr_desc,
        })

    # Build SP taxonomy summary (active effects sorted by category list, effect ID)
    active_sp_ids = sorted(set(sp_base_cards) | set(sp_combi_cards))
    sp_summary = []
    for eid in active_sp_ids:
        meta = sp_effects.get(eid, {})
        cats = meta.get('SpSkillCategoryCodeList') or []
        cats_zh, cats_ids, cats_enum = format_sp_categories(cats)
        known = SP_EFFECTS.get(eid)
        if known is None:
            issues.append({
                'Kind': 'unmapped_sp_effect',
                'EffectId': eid,
                'SkillEffect': meta.get('SkillEffect', ''),
                'CategoryCodes': cats,
                'SampleCards': (sp_base_cards[eid] or sp_combi_cards[eid])[:5],
            })
        sp_summary.append({
            'effect_id': eid,
            'categories_raw': cats,
            'categories_zh': cats_zh,
            'categories_ids': cats_ids,
            'categories_enum': cats_enum,
            'wiki_label': known[1] if known else f'未收录SP效果({eid})',
            'enum_name': known[0] if known else '',
            'skill_effect': meta.get('SkillEffect', ''),
            'base_count': len(sp_base_cards[eid]),
            'combi_count': len(sp_combi_cards[eid]),
            'sample_cards': ', '.join(str(c) for c in (sp_base_cards[eid] or sp_combi_cards[eid])[:6]),
            'note': known[2] if known else '新版本新增效果，待补充 Wiki 中文小类名',
        })
    sp_summary.sort(key=lambda r: (r['categories_raw'], r['effect_id']))

    # Build Auto skill summary
    auto_summary = []
    for eid in sorted(auto_cards):
        meta = auto_effects.get(eid, {})
        known = AUTO_EFFECTS.get(eid)
        if known is None:
            issues.append({
                'Kind': 'unmapped_auto_effect',
                'EffectId': eid,
                'SkillName': meta.get('SkillName', ''),
                'IconFileName': meta.get('IconFileName', ''),
                'SampleCards': auto_cards[eid][:5],
            })
        icon = meta.get('IconFileName', '') or ''
        auto_summary.append({
            'effect_id': eid,
            'name': meta.get('SkillName', ''),
            'wiki_summary': known[0] if known else '未收录自动技能，待补充说明',
            'card_count': len(auto_cards[eid]),
            'icon_file': f'{icon}.png' if icon else '',
            'asset_bundle': f'Files/Android/{icon}' if icon else '',
            'raw_desc': str(meta.get('SkillDescription', '')).replace('\n', ''),
            'note': known[1] if known else '新版本新增自动技能',
            'cards': '、'.join(str(c) for c in auto_cards[eid]),
        })

    # Detect unmapped Leader effects
    for eid in sorted(leader_cards):
        if eid not in LEADER_EFFECTS:
            meta = leader_effects.get(eid, {})
            issues.append({
                'Kind': 'unmapped_leader_effect',
                'EffectId': eid,
                'SkillEffect': meta.get('SkillEffect', ''),
                'SampleCards': leader_cards[eid][:5],
            })

    # Collect skill-related notices from mst_notice (optional table)
    skill_notices = []
    for row in sorted(tables.rows('mst_notice'), key=lambda r: r.get('NoticeId', 0)):
        title = str(row.get('TitleName') or '')
        body = _plain_html(row.get('FileDesc', ''))
        if NOTICE_SKILL_RE.search(title) or ('SHOWER' in body and '説明文' in title):
            skill_notices.append({
                'notice_id': row.get('NoticeId'),
                'start_time': str(row.get('StartTime') or row.get('DisplayStartTime') or '')[:10],
                'title': title,
                'excerpt': body[:240],
            })

    return {
        'SpSummary': sp_summary,
        'AutoSummary': auto_summary,
        'CardIndex': card_index,
        'SkillNotices': skill_notices,
        'Issues': issues,
        'Stats': {
            'ActiveCards': len(cards),
            'ActiveSpEffects': len(sp_summary),
            'DualCategorySpEffects': sum('＋' in r['categories_zh'] for r in sp_summary),
            'ActiveAutoEffects': len(auto_summary),
            'ActiveLeaderEffects': len(leader_cards),
            'UnmappedIssues': len(issues),
        },
    }


def _style_merged(ws, cell_range, *, font=None, fill=None, alignment=None, border=None):
    min_col, min_row, max_col, max_row = range_boundaries(cell_range)
    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        for cell in row:
            if font:
                cell.font = font
            if fill:
                cell.fill = fill
            if alignment:
                cell.alignment = alignment
            if border:
                cell.border = border


def _setup_sheet(ws, title_text, headers, col_widths):
    navy, banner_bg, border_clr = '1F4E79', '163A59', 'D6DEE6'
    font_name = 'Microsoft YaHei'
    thin = Side(style='thin', color=border_clr)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    end_col = get_column_letter(len(headers))
    ws.merge_cells(f'A1:{end_col}1')
    ws['A1'] = title_text
    _style_merged(
        ws, f'A1:{end_col}1',
        font=Font(name=font_name, size=12, bold=True, color='FFFFFF'),
        fill=PatternFill('solid', fgColor=banner_bg),
        alignment=Alignment(horizontal='left', vertical='center', indent=1),
    )
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 24
    for idx, text in enumerate(headers, 1):
        c = ws.cell(2, idx, text)
        c.font = Font(name=font_name, size=10, bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor=navy)
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border
    for idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.freeze_panes = 'A3'
    return border


def _write_rows(ws, rows, border, *, right_cols=(), center_cols=(), wrap_cols=()):
    font_name = 'Microsoft YaHei'
    f_body = Font(name=font_name, size=10, color='1E293B')
    fill_alt = PatternFill('solid', fgColor='F4F7FA')
    for r_idx, row in enumerate(rows, start=3):
        is_alt = r_idx % 2 == 0
        for c_idx, val in enumerate(row, 1):
            c = ws.cell(r_idx, c_idx, val)
            c.font = f_body
            c.border = border
            if is_alt:
                c.fill = fill_alt
            h_align = 'right' if c_idx in right_cols else ('center' if c_idx in center_cols else 'left')
            c.alignment = Alignment(horizontal=h_align, vertical='center', wrap_text=c_idx in wrap_cols)
        ws.row_dimensions[r_idx].height = 22
    end_col = get_column_letter(ws.max_column)
    ws.auto_filter.ref = f'A2:{end_col}{max(2, ws.max_row)}'


def export(data):
    wb = Workbook()

    # Sheet 1: SP技能分类
    ws1 = wb.active
    ws1.title = 'SP技能分类'
    h1 = ['官方大类', '大类编号', '大类英文枚举（SpSkillCategoryCode）', '效果 ID', 'Wiki 中文小类',
          '客户端英文枚举（SpSkillType）', '主数据英文键（SkillEffect）', '基础SP卡数', '协作追加卡数', '示例卡编号', '说明']
    b1 = _setup_sheet(
        ws1,
        f"SP 技能分类对照表  ｜  官方 6 大类 × {data['Stats']['ActiveSpEffects']} 种已用效果（其中 {data['Stats']['DualCategorySpEffects']} 种双重归属）",
        h1, [16, 11, 28, 10, 34, 28, 28, 12, 12, 22, 34],
    )
    _write_rows(
        ws1,
        [[r['categories_zh'], r['categories_ids'], r['categories_enum'], r['effect_id'], r['wiki_label'],
          r['enum_name'], r['skill_effect'], r['base_count'], r['combi_count'], r['sample_cards'], r['note']]
         for r in data['SpSummary']],
        b1, right_cols=(4, 8, 9), center_cols=(1, 2), wrap_cols=(11,),
    )

    # Sheet 2: 自动技能分类
    ws2 = wb.create_sheet('自动技能分类')
    h2 = ['效果 ID', '自动技能名', 'Wiki 中文说明', '卡数', '图标文件名', 'Android 资源包路径', '主数据原文模板', '备注', '持有卡编号']
    b2 = _setup_sheet(
        ws2,
        f"自动技能分类对照表  ｜  共 {data['Stats']['ActiveAutoEffects']} 类（含 ASSIST 等全部有效配置）",
        h2, [10, 16, 30, 8, 18, 28, 38, 32, 46],
    )
    _write_rows(
        ws2,
        [[r['effect_id'], r['name'], r['wiki_summary'], r['card_count'], r['icon_file'],
          r['asset_bundle'], r['raw_desc'], r['note'], r['cards']]
         for r in data['AutoSummary']],
        b2, right_cols=(1, 4), center_cols=(2,), wrap_cols=(7, 8, 9),
    )

    # Sheet 3: 卡牌技能标签索引
    ws3 = wb.create_sheet('卡牌技能标签索引')
    h3 = ['卡牌编号', '角色', '卡牌名', '稀有度', '属性', 'SP技能名', 'SP官方大类', '基础SP细分', '基础SP展开标签',
          'Lv1 COST', '满级 COST', '协作对象', '协作SP细分', '协作SP展开标签', '自动技能分类', '自动技能原文(Lv1)',
          '旧版表记参考', '队长技能类型', '基础SP原文(Lv1)']
    b3 = _setup_sheet(
        ws3,
        f"卡牌技能标签索引  ｜  共 {data['Stats']['ActiveCards']} 张有效卡（基础 SP 与协作追加分列，保留原表日文不覆盖）",
        h3, [10, 11, 24, 8, 8, 18, 14, 28, 28, 10, 10, 11, 24, 24, 15, 36, 24, 18, 36],
    )
    _write_rows(
        ws3,
        [[r['card_id'], r['char_name'], r['card_name'], r['rarity'], r['attribute'], r['sp_name'],
          r['sp_categories_zh'], r['sp_subtype'], r['sp_expanded_tag'], r['sp_lv1_cost'], r['sp_max_cost'],
          r['combi_char'], r['combi_subtype'], r['combi_expanded_tag'], r['auto_name'], r['auto_lv1_desc'],
          r['auto_legacy_note'], r['leader_label'], r['sp_lv1_desc']]
         for r in data['CardIndex']],
        b3, right_cols=(1, 10, 11), center_cols=(4, 5, 7, 15), wrap_cols=(16, 19),
    )

    # Sheet 4: 公告与漂移核对
    ws4 = wb.create_sheet('公告与漂移核对')
    h4 = ['类别', '编号', '日期 / 影响范围', '标题 / 键名', '详情摘录']
    b4 = _setup_sheet(
        ws4,
        f"新机制漂移监控与相关公告  ｜  未收录新效果 {data['Stats']['UnmappedIssues']} 项 · 检索到技能相关公告 {len(data['SkillNotices'])} 条",
        h4, [18, 10, 18, 36, 68],
    )
    audit_rows = [
        [issue['Kind'], issue['EffectId'], ', '.join(map(str, issue.get('SampleCards', []))),
         issue.get('SkillEffect') or issue.get('SkillName', ''), '待在 toolkit/core/skill_taxonomy.py 补充 Wiki 译名']
        for issue in data['Issues']
    ]
    for notice in data['SkillNotices']:
        audit_rows.append(['技能相关公告', notice['notice_id'], notice['start_time'], notice['title'], notice['excerpt']])
    _write_rows(ws4, audit_rows, b4, right_cols=(2,), center_cols=(1, 3), wrap_cols=(4, 5))

    # Sheet 5: 客户端机制附注
    ws5 = wb.create_sheet('客户端机制附注')
    h5 = ['专题', '内部标识', '机制说明 / 效果', '权重或旧表记', '单次概率或现行表记', '来源与版本边界']
    b5 = _setup_sheet(
        ws5,
        f"客户端硬编码机制附注  ｜  以下非 master_data 自动字段，来自客户端 {PANDORA_BOX_CLIENT_VERSION} 反编译与官方公告，大版本更新时需人工复核",
        h5, [18, 24, 38, 14, 18, 32],
    )
    ref_rows = [
        ['洗牌机制', 'ShuffleW (ID 30)', '普通打乱：PieceManager.Shuffle(avoidMatch=true)，重排后尽量避开即时匹配', '-', 'ピ—スをシャッフルする！', f'客户端 {PANDORA_BOX_CLIENT_VERSION} 反编译'],
        ['洗牌机制', 'ShuffleS (ID 29)', '强力打乱：PieceManager.Shuffle(avoidMatch=false)，允许重排直接形成匹配与消除', '-', '強烈にシャッフルする！', f'客户端 {PANDORA_BOX_CLIENT_VERSION} 反编译'],
    ]
    for old_label, new_label, src in SHOWER_LEGACY_TABLE:
        ref_rows.append(['SHOWER 五档对照', new_label, '实际效果因关卡掉落权重而异，非固定概率百分点', old_label, new_label, src])
    for key, desc, weight in PANDORA_BOX_POOL:
        ref_rows.append([
            '卡 214 潘多拉盒', key, desc, weight,
            f'{weight / PANDORA_BOX_TOTAL_WEIGHT:.2%}',
            f'客户端 {PANDORA_BOX_CLIENT_VERSION} 反编译（总权重 {PANDORA_BOX_TOTAL_WEIGHT}）',
        ])
    _write_rows(ws5, ref_rows, b5, center_cols=(1, 4, 5), wrap_cols=(3, 6))

    for sheet in wb:
        sheet.page_setup.orientation = 'landscape'
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0

    return save_workbook_safely(wb, xlsx_path('skills_catalog.xlsx'))


def run(session=None):
    data = extract(session)
    save_json(data, audit_path('skills_catalog.json'))
    if data['Issues']:
        record_warning(f"技能分类发现 {len(data['Issues'])} 个未收录的新技能效果 ID，详见 skills_catalog.json")
    return export(data)
