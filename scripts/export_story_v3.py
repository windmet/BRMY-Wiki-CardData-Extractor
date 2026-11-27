"""Export the 5-sheet V3 community story workbook directly from story-index.json.

Sheets:
1. 剧情总表（1 行 = 1 篇，跨表公式自动带出熟肉状态、链接、UP 主）
2. 分话出场表（1 行 = 1 话，原样署名、保留全部 NPC，未实装标为「未公开」）
3. 分话角色明细（1 行 = 1 话 × 1 人物，按台词数降序）
4. 熟肉链接库（增补链接自动回填总表）
5. 进度看板与待处理（动态公式 + 堆叠柱状图 + 待处理异常清单）

Optionally pass ``--preserve <existing_v2_or_v3.xlsx>`` to keep manually filled
``中文标题``, ``备注``, and ``熟肉链接库`` rows during incremental refreshes.
"""
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.worksheet.datavalidation import DataValidation

TYPE_SORT_ORDER = {'主线': 1, '活动': 2, '个人': 3, '卡牌': 4, '其他': 5}
GARBAGE_SPEAKERS = frozenset({'・', '2'})
PLACEHOLDER_PREFIXES = ('2001-', '3001-', '9999-')


def _numeric_id_parts(story_id):
    return tuple(int(part) if part.isdigit() else 0 for part in str(story_id).split('-')[1:])


def _story_sort_key(story):
    stype = story['type']
    sid = story['story_id']
    nums = _numeric_id_parts(sid)
    dt = story['date'].isoformat() if story.get('date') else ''
    t_rank = TYPE_SORT_ORDER.get(stype, 99)
    if stype in ('主线', '个人'):
        return (t_rank, 0, '', nums, sid)
    if stype in ('活动', '卡牌'):
        return (t_rank, 0 if dt else 1, dt or '9999-99-99', nums, sid)
    kind_rank = 0 if sid.startswith('campaign-') else 1
    return (t_rank, 0 if dt else 1, dt or '9999-99-99', (kind_rank, *nums), sid)


def _display_width(text):
    return sum(1.85 if ord(ch) > 127 else 1.0 for ch in str(text or ''))


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


def _read_preserved(path):
    """Read human-maintained 中文标题, 备注, 归属角色, and 熟肉链接库 from an existing workbook."""
    manual_story = {}
    manual_links = []
    if not path:
        return manual_story, manual_links
    wb = load_workbook(path, data_only=False)
    if '剧情总表' in wb.sheetnames:
        ws = wb['剧情总表']
        for r in range(3, ws.max_row + 1):
            sid = ws.cell(r, 13).value
            if not sid:
                continue
            manual_story[str(sid)] = {
                'cn_title': ws.cell(r, 4).value,
                'owner_name': ws.cell(r, 5).value,
                'note': ws.cell(r, 12).value,
            }
    if '熟肉链接库' in wb.sheetnames:
        ws = wb['熟肉链接库']
        for r in range(3, ws.max_row + 1):
            sid = ws.cell(r, 1).value
            url = ws.cell(r, 5).value
            if not sid and not url:
                continue
            manual_links.append({
                'story_id': str(sid or '').strip(),
                'scope': ws.cell(r, 3).value or '',
                'platform': ws.cell(r, 4).value or '',
                'url': str(url or '').strip(),
                'uploader': ws.cell(r, 6).value or '',
                'trans_type': ws.cell(r, 7).value or '',
                'progress': ws.cell(r, 8).value or '',
                'status': ws.cell(r, 9).value,
            })
    return manual_story, manual_links


def export(snapshot, output, *, preserve=None, export_json=None):
    snapshot = Path(snapshot)
    output = Path(output)
    if preserve and output.resolve() == Path(preserve).resolve():
        raise ValueError('请另存成品，不覆盖维护模板')

    data = json.loads(snapshot.read_text(encoding='utf-8'))
    manual_story, manual_links = _read_preserved(preserve)

    # Resolve character owner names from personal stories, cast rows, and preserved sheet
    owner_names = {}
    for row in data['剧情总表'][1:]:
        sid, stype, title, _, _, owner_id = row[0], row[1], row[2], row[3], row[4], row[5]
        if owner_id is not None and sid in manual_story and manual_story[sid].get('owner_name'):
            owner_names.setdefault(owner_id, manual_story[sid]['owner_name'])
        if stype == '个人' and owner_id is not None and title:
            owner_names.setdefault(owner_id, str(title).split(' / ')[0].replace(' ', '').replace('\u3000', ''))
    for row in data['出场证据'][1:]:
        cid, name, identity = row[2], row[3], row[4]
        if cid is not None and identity in ('角色', 'NPC角色'):
            owner_names.setdefault(cid, re.sub(r'[\s\u3000]+', '', str(name or '')))

    stories = []
    story_by_id = {}
    for row in data['剧情总表'][1:]:
        sid = row[0]
        stype = row[1]
        raw_series = row[4] or ''
        banner = len(row) > 15 and row[15] == '部门箱活（banner）'
        series = f'部门箱活（banner） / {raw_series}' if banner and raw_series else ('部门箱活（banner）' if banner else raw_series)
        jp_title = row[2] or raw_series or sid
        owner_id = row[5]
        owner_name = (manual_story.get(sid, {}).get('owner_name')
                      or (owner_names.get(owner_id) if owner_id is not None else None))
        dt_str = str(row[9] or '').strip()
        dt = datetime.fromisoformat(dt_str[:10]).date() if dt_str and not dt_str.startswith(PLACEHOLDER_PREFIXES) else None
        rec = {
            'story_id': sid,
            'type': stype,
            'series': series or None,
            'jp_title': jp_title,
            'cn_title': manual_story.get(sid, {}).get('cn_title') or (row[3] or None),
            'owner_name': owner_name,
            'date': dt,
            'ep_count': int(row[11]) if row[11] not in ('', None) else 0,
            'note': manual_story.get(sid, {}).get('note'),
        }
        stories.append(rec)
        story_by_id[sid] = rec

    stories.sort(key=_story_sort_key)
    story_order = {s['story_id']: idx for idx, s in enumerate(stories)}

    entrances = {}
    episodes = []
    for row in data['章节'][1:]:
        sid, eid, seq, ep_title, orig_dt, _, axis = row[:7]
        if not sid or not eid or sid not in story_by_id:
            continue
        entrances[eid] = str(axis or '').split(',') if axis else []
        is_placeholder = str(orig_dt or '').startswith('3001-')
        episodes.append({
            'story_id': sid,
            'episode_id': eid,
            'seq': int(seq) if seq is not None else 0,
            'ep_title': str(ep_title or f'第{seq}話').strip(),
            'has_axis': bool(axis),
            'is_placeholder': is_placeholder,
            'sort_key': (story_order.get(sid, 999999), int(seq) if seq is not None else 0),
        })
    episodes.sort(key=lambda x: x['sort_key'])

    # Aggregate speakers per episode & per story (NO alias merging, ALL NPCs kept, NO prequel double-counting)
    ep_chars = defaultdict(lambda: defaultdict(lambda: {'lines': 0, 'is_playable': False}))
    story_chars = defaultdict(lambda: defaultdict(lambda: {'lines': 0, 'is_playable': False, 'episodes': set()}))
    for row in data['出场证据'][1:]:
        sid, eid, cid, raw_name, identity, _, entry, _, count = row[:9]
        ep_entrances = entrances.get(eid, [])
        if ep_entrances:
            preferred = eid if eid in ep_entrances else ep_entrances[0]
            if entry and entry != preferred:
                continue
        text = str(raw_name or '').strip()
        if not text or identity == '玩家' or '<Self' in text or text in GARBAGE_SPEAKERS:
            continue
        compact = re.sub(r'[\s\u3000]+', '', text)
        if not compact or compact in GARBAGE_SPEAKERS:
            continue
        if cid is not None:
            cname = owner_names.get(cid, compact)
            is_play = identity == '角色' if identity in ('角色', 'NPC角色') else (int(cid) <= 21)
        else:
            cname = compact if (' ' not in text or any(ord(c) > 127 for c in text)) else text
            is_play = False
        line_cnt = int(count or 0)
        if eid:
            e_ent = ep_chars[eid][cname]
            e_ent['lines'] += line_cnt
            if is_play:
                e_ent['is_playable'] = True
        if sid:
            s_ent = story_chars[sid][cname]
            if eid:
                s_ent['episodes'].add(eid)
            s_ent['lines'] += line_cnt
            if is_play:
                s_ent['is_playable'] = True

    # Build 熟肉链接库 & anomalies
    res_info = {}
    for row in data.get('熟肉资源', [])[1:]:
        if row[0]:
            res_info[row[0]] = {'platform': row[2], 'url': row[5]}

    linked_resources = []
    unmatched_anomalies = []
    if manual_links:
        for item in manual_links:
            linked_resources.append({**item, 'sort_key': story_order.get(item['story_id'], 999999)})
    for row in data.get('资源关联', [])[1:]:
        rid, sid, scope_hint, src_header, uploader, progress, match_basis = [str(v or '').strip() for v in row[:7]]
        rinfo = res_info.get(rid, {})
        url = str(rinfo.get('url') or '').strip()
        raw_plat = str(rinfo.get('platform') or '').strip()
        platform = 'B站合集' if raw_plat == 'space.bilibili.com' else ('B站' if raw_plat == 'Bilibili' else raw_plat)
        if not sid or sid not in story_by_id:
            clean_src = uploader or src_header
            m_num = re.match(r'^(\d{2})', scope_hint)
            if m_num and uploader and (m_num.group(1) + ':') in uploader:
                m_up = re.search(m_num.group(1) + r':([^/]+)', uploader)
                if m_up:
                    clean_src = m_up.group(1).strip() or src_header
            unmatched_anomalies.append({
                'kind': '熟肉未对齐剧情',
                'hint': scope_hint or rid,
                'source': clean_src,
                'url': url,
                'action': '核对剧情ID后移入《熟肉链接库》',
            })
            continue
        if manual_links:
            continue
        if match_basis == '合集标注范围':
            clean_scope = f"合集（{scope_hint.rstrip(':：')}）"
        elif re.match(r'^\d+[-~～]\d+[:：]?$', scope_hint):
            clean_scope = f"第{scope_hint.rstrip(':：')}话"
        else:
            clean_scope = '全篇'
        trans_type = '机翻' if '机翻' in progress else ('人工' if progress else '')
        clean_prog = progress.replace('机翻', '').strip() if progress else ''
        clean_uploader = uploader
        if '1-6' in scope_hint and '1-6：' in uploader:
            m = re.search(r'1-6：([^/]+)', uploader)
            if m:
                clean_uploader = m.group(1).strip()
        elif '7-10' in scope_hint and '7-10：' in uploader:
            m = re.search(r'7-10：([^/]+)', uploader)
            if m:
                clean_uploader = m.group(1).strip()
        linked_resources.append({
            'story_id': sid,
            'scope': clean_scope,
            'platform': platform,
            'url': url,
            'uploader': clean_uploader,
            'trans_type': trans_type,
            'progress': clean_prog,
            'status': None,
            'sort_key': story_order.get(sid, 999999),
        })

    linked_resources.sort(key=lambda x: x['sort_key'])

    for row in data.get('待核清单', [])[1:]:
        obj, issue, basis = [str(v or '').strip() for v in row[:3]]
        if issue == '无有效资源定位':
            unmatched_anomalies.append({
                'kind': '残缺链接',
                'hint': obj,
                'source': '原表导入',
                'url': basis,
                'action': '补全有效B站BV号或删除无效占位',
            })

    # ── Build styled 5-sheet V3 workbook ──
    wb = Workbook()
    navy, teal, slate, banner_bg = '1F4E79', '2E7D6F', '4A607A', '163A59'
    alt_row, input_bg, border_clr, muted_text, link_blue = 'F4F7FA', 'F9FCFB', 'D6DEE6', '6B7A8C', '1155CC'
    font_name = 'Microsoft YaHei'

    thin = Side(style='thin', color=border_clr)
    double_navy = Side(style='double', color=navy)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    f_banner = Font(name=font_name, size=13, bold=True, color='FFFFFF')
    f_header = Font(name=font_name, size=10, bold=True, color='FFFFFF')
    f_body = Font(name=font_name, size=10, color='1E293B')
    f_bold = Font(name=font_name, size=10, bold=True, color='1E293B')
    f_muted = Font(name=font_name, size=9, color=muted_text)
    f_link = Font(name=font_name, size=10, color=link_blue, underline='single')

    fill_banner = PatternFill('solid', fgColor=banner_bg)
    fill_navy = PatternFill('solid', fgColor=navy)
    fill_teal = PatternFill('solid', fgColor=teal)
    fill_slate = PatternFill('solid', fgColor=slate)
    fill_alt = PatternFill('solid', fgColor=alt_row)
    fill_input = PatternFill('solid', fgColor=input_bg)
    fill_kpi = PatternFill('solid', fgColor='EEF3F8')

    res_last_row = max(1000, len(linked_resources) + 200)
    json_stories = {}

    # Sheet 1: 剧情总表
    ws1 = wb.active
    ws1.title = '剧情总表'
    ws1.merge_cells('A1:M1')
    ws1['A1'] = 'Break My Case 剧情总表（V3·分话版）  ｜  深蓝=程序自动区  ·  青绿=人工填写区  ·  灰蓝=公式自动带出（请在《熟肉链接库》增补链接）'
    _style_merged(ws1, 'A1:M1', font=f_banner, fill=fill_banner, alignment=Alignment(horizontal='left', vertical='center', indent=1))
    ws1.row_dimensions[1].height = 30

    headers_s1 = [
        ('类型', fill_navy), ('系列 / 关联活动', fill_navy), ('日文标题', fill_navy), ('中文标题', fill_teal),
        ('归属角色', fill_navy), ('实装日期', fill_navy), ('话数', fill_navy), ('出场人物（含全部NPC·原样署名）', fill_navy),
        ('熟肉状态', fill_slate), ('熟肉链接', fill_slate), ('翻译 / UP主', fill_slate), ('备注', fill_teal), ('剧情ID', fill_navy),
    ]
    ws1.row_dimensions[2].height = 24
    for idx, (text, fill) in enumerate(headers_s1, 1):
        c = ws1.cell(2, idx, text)
        c.font = f_header
        c.fill = fill
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    rng_id = f"'熟肉链接库'!$A$3:$A${res_last_row}"
    rng_scope = f"'熟肉链接库'!$C$3:$C${res_last_row}"
    rng_url = f"'熟肉链接库'!$E$3:$E${res_last_row}"
    rng_up = f"'熟肉链接库'!$F$3:$F${res_last_row}"

    for r_idx, s in enumerate(stories, start=3):
        sid = s['story_id']
        cmap = story_chars.get(sid, {})
        sorted_chars = sorted(cmap.items(), key=lambda kv: (-kv[1]['lines'], 0 if kv[1]['is_playable'] else 1, kv[0]))
        char_str = '、'.join(name for name, _ in sorted_chars)
        json_stories[sid] = {
            'story_id': sid, 'type': s['type'], 'series_or_event': s['series'], 'jp_title': s['jp_title'],
            'cn_title': s['cn_title'], 'owner': s['owner_name'],
            'release_date': s['date'].isoformat() if s['date'] else None,
            'episode_count': s['ep_count'], 'speakers_all': [n for n, _ in sorted_chars], 'episodes': [],
        }
        id_ref = f'M{r_idx}'
        f_status = (f'=IF(COUNTIF({rng_id},{id_ref})=0,"待补充",'
                    f'IF(COUNTIF({rng_id},{id_ref})>1,"多条("&COUNTIF({rng_id},{id_ref})&")",'
                    f'IF(ISNUMBER(SEARCH("合集",INDEX({rng_scope},MATCH({id_ref},{rng_id},0)))),"合集","已有")))')
        f_url = (f'=IF(COUNTIF({rng_id},{id_ref})=0,"",'
                 f'HYPERLINK(INDEX({rng_url},MATCH({id_ref},{rng_id},0)),INDEX({rng_url},MATCH({id_ref},{rng_id},0))))')
        f_up = f'=IF(COUNTIF({rng_id},{id_ref})=0,"",INDEX({rng_up},MATCH({id_ref},{rng_id},0)))'

        vals = [s['type'], s['series'], s['jp_title'], s['cn_title'], s['owner_name'], s['date'],
                s['ep_count'], char_str or None, f_status, f_url, f_up, s['note'], sid]
        is_alt = r_idx % 2 == 0
        for col_idx, val in enumerate(vals, 1):
            c = ws1.cell(r_idx, col_idx, val)
            c.border = border
            c.font = f_muted if col_idx == 13 else (f_link if col_idx == 10 else f_body)
            if col_idx in (4, 12):
                c.fill = fill_input
            elif is_alt:
                c.fill = fill_alt
            if col_idx in (1, 5, 6, 9):
                c.alignment = Alignment(horizontal='center', vertical='center')
            elif col_idx == 7:
                c.alignment = Alignment(horizontal='right', vertical='center')
                c.number_format = '#,##0'
            elif col_idx == 8:
                c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            else:
                c.alignment = Alignment(horizontal='left', vertical='center')
            if col_idx == 6 and val is not None:
                c.number_format = 'YYYY-MM-DD'
        lines = max(1, int(_display_width(char_str) / 42) + 1) if char_str else 1
        ws1.row_dimensions[r_idx].height = max(22, min(lines * 18 + 10, 120))

    last_s1 = max(2, len(stories) + 2)
    ws1.freeze_panes = 'A3'
    ws1.auto_filter.ref = f'A2:M{last_s1}'
    if last_s1 >= 3:
        rng_stat = f'I3:I{last_s1}'
        ws1.conditional_formatting.add(rng_stat, CellIsRule(operator='equal', formula=['"已有"'], fill=PatternFill('solid', fgColor='D1E7DD'), font=Font(name=font_name, size=10, bold=True, color='0F5132')))
        ws1.conditional_formatting.add(rng_stat, CellIsRule(operator='equal', formula=['"待补充"'], fill=PatternFill('solid', fgColor='FFF3CD'), font=Font(name=font_name, size=10, color='664D03')))
        ws1.conditional_formatting.add(rng_stat, CellIsRule(operator='equal', formula=['"合集"'], fill=PatternFill('solid', fgColor='CFE2FF'), font=Font(name=font_name, size=10, bold=True, color='084298')))
    for col_idx, w in {1: 11, 2: 30, 3: 32, 4: 20, 5: 12, 6: 13, 7: 8, 8: 48, 9: 12, 10: 46, 11: 18, 12: 20, 13: 15}.items():
        ws1.column_dimensions[get_column_letter(col_idx)].width = w

    # Sheet 2 & 3: 分话出场表 & 分话角色明细
    ws_ep = wb.create_sheet('分话出场表')
    ws_ep.merge_cells('A1:I1')
    ws_ep['A1'] = '分话出场表（精确到每一话）  ｜  不做别名归并、保留全部NPC；未实装占位标记为「未公开」'
    _style_merged(ws_ep, 'A1:I1', font=f_banner, fill=fill_banner, alignment=Alignment(horizontal='left', vertical='center', indent=1))
    ws_ep.row_dimensions[1].height = 30
    ws_ep.row_dimensions[2].height = 24
    for idx, text in enumerate(['类型', '剧情标题', '话序', '本话标题', '本话出场人物（含全部NPC）', '出场人数', '本话状态', '剧情ID', '话ID'], 1):
        c = ws_ep.cell(2, idx, text)
        c.font = f_header
        c.fill = fill_navy
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    ws_det = wb.create_sheet('分话角色明细')
    ws_det.merge_cells('A1:I1')
    ws_det['A1'] = '分话角色明细  ｜  1行 = 1话 × 1人物，按台词数降序，方便按角色反查精确到话的出场位置'
    _style_merged(ws_det, 'A1:I1', font=f_banner, fill=fill_banner, alignment=Alignment(horizontal='left', vertical='center', indent=1))
    ws_det.row_dimensions[1].height = 30
    ws_det.row_dimensions[2].height = 24
    for idx, text in enumerate(['类型', '剧情标题', '话序', '本话标题', '剧本署名', '身份分类', '台词数', '剧情ID', '话ID'], 1):
        c = ws_det.cell(2, idx, text)
        c.font = f_header
        c.fill = fill_navy
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    r_ep = r_det = 3
    review_ep_ids = []
    unreleased_count = 0
    for ep in episodes:
        sid, eid = ep['story_id'], ep['episode_id']
        st = story_by_id[sid]
        sorted_ep = sorted(ep_chars.get(eid, {}).items(), key=lambda kv: (-kv[1]['lines'], 0 if kv[1]['is_playable'] else 1, kv[0]))
        if sorted_ep:
            ep_status = '已解析'
        elif (ep['is_placeholder'] or st['type'] == '个人') and not ep['has_axis']:
            ep_status = '未公开'
            unreleased_count += 1
        else:
            ep_status = '待复核'
            review_ep_ids.append(eid)

        char_str = '、'.join(name for name, _ in sorted_ep)
        for col_idx, val in enumerate([st['type'], st['jp_title'], ep['seq'], ep['ep_title'], char_str or None, len(sorted_ep), ep_status, sid, eid], 1):
            c = ws_ep.cell(r_ep, col_idx, val)
            c.border = border
            c.font = f_muted if col_idx in (8, 9) else f_body
            if r_ep % 2 == 0:
                c.fill = fill_alt
            if col_idx in (1, 7):
                c.alignment = Alignment(horizontal='center', vertical='center')
            elif col_idx in (3, 6):
                c.alignment = Alignment(horizontal='right', vertical='center')
                c.number_format = '#,##0'
            elif col_idx == 5:
                c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            else:
                c.alignment = Alignment(horizontal='left', vertical='center')
        ws_ep.row_dimensions[r_ep].height = max(21, min((int(_display_width(char_str) / 46) + 1) * 17 + 8, 96)) if char_str else 21
        r_ep += 1

        json_stories[sid]['episodes'].append({
            'episode_id': eid, 'seq': ep['seq'], 'title': ep['ep_title'], 'status': ep_status,
            'speakers': [{'name': n, 'category': '主要角色' if info['is_playable'] else 'NPC', 'lines': info['lines']}
                         for n, info in sorted_ep],
        })
        for cname, info in sorted_ep:
            for col_idx, val in enumerate([st['type'], st['jp_title'], ep['seq'], ep['ep_title'], cname,
                                           '主要角色' if info['is_playable'] else 'NPC', info['lines'], sid, eid], 1):
                c = ws_det.cell(r_det, col_idx, val)
                c.border = border
                c.font = f_muted if col_idx in (8, 9) else f_body
                if r_det % 2 == 0:
                    c.fill = fill_alt
                if col_idx in (1, 6):
                    c.alignment = Alignment(horizontal='center', vertical='center')
                elif col_idx in (3, 7):
                    c.alignment = Alignment(horizontal='right', vertical='center')
                    c.number_format = '#,##0'
                else:
                    c.alignment = Alignment(horizontal='left', vertical='center')
            ws_det.row_dimensions[r_det].height = 20
            r_det += 1

    last_ep = max(2, r_ep - 1)
    ws_ep.freeze_panes = 'A3'
    ws_ep.auto_filter.ref = f'A2:I{last_ep}'
    if last_ep >= 3:
        rng_ep = f'G3:G{last_ep}'
        ws_ep.conditional_formatting.add(rng_ep, CellIsRule(operator='equal', formula=['"已解析"'], fill=PatternFill('solid', fgColor='D1E7DD'), font=Font(name=font_name, size=10, color='0F5132')))
        ws_ep.conditional_formatting.add(rng_ep, CellIsRule(operator='equal', formula=['"未公开"'], fill=PatternFill('solid', fgColor='E2E8F0'), font=Font(name=font_name, size=10, color='475569')))
        ws_ep.conditional_formatting.add(rng_ep, CellIsRule(operator='equal', formula=['"待复核"'], fill=PatternFill('solid', fgColor='F8D7DA'), font=Font(name=font_name, size=10, bold=True, color='842029')))
    for col_idx, w in {1: 11, 2: 32, 3: 8, 4: 26, 5: 52, 6: 10, 7: 11, 8: 15, 9: 18}.items():
        ws_ep.column_dimensions[get_column_letter(col_idx)].width = w

    ws_det.freeze_panes = 'A3'
    ws_det.auto_filter.ref = f'A2:I{max(2, r_det - 1)}'
    for col_idx, w in {1: 11, 2: 32, 3: 8, 4: 24, 5: 20, 6: 11, 7: 10, 8: 15, 9: 18}.items():
        ws_det.column_dimensions[get_column_letter(col_idx)].width = w

    # Sheet 4: 熟肉链接库
    ws2 = wb.create_sheet('熟肉链接库')
    ws2.merge_cells('A1:I1')
    ws2['A1'] = '熟肉链接库  ｜  在下方追加新行，填入【剧情ID】与【熟肉链接】，对应剧情名与《剧情总表》链接将自动更新'
    _style_merged(ws2, 'A1:I1', font=f_banner, fill=fill_banner, alignment=Alignment(horizontal='left', vertical='center', indent=1))
    ws2.row_dimensions[1].height = 30
    ws2.row_dimensions[2].height = 24
    for idx, (text, fill) in enumerate([
        ('剧情ID', fill_teal), ('对应剧情（自动）', fill_slate), ('覆盖范围', fill_teal), ('平台', fill_teal),
        ('熟肉链接', fill_teal), ('翻译 / UP主', fill_teal), ('翻译类型', fill_teal), ('进度', fill_teal), ('链接状态', fill_teal),
    ], 1):
        c = ws2.cell(2, idx, text)
        c.font = f_header
        c.fill = fill
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    def _title_formula(r):
        return (f'=IF(A{r}="","",IF(COUNTIF(\'剧情总表\'!$M$3:$M${last_s1},A{r})=0,"未匹配ID",'
                f'INDEX(\'剧情总表\'!$C$3:$C${last_s1},MATCH(A{r},\'剧情总表\'!$M$3:$M${last_s1},0))))')

    for r_idx, item in enumerate(linked_resources, start=3):
        vals = [item['story_id'], _title_formula(r_idx), item['scope'], item['platform'], item['url'],
                item['uploader'], item['trans_type'], item['progress'], item['status']]
        for col_idx, val in enumerate(vals, 1):
            c = ws2.cell(r_idx, col_idx, val)
            c.border = border
            if col_idx == 5 and val:
                c.font = f_link
                c.hyperlink = val
            elif col_idx == 1:
                c.font = f_muted
            else:
                c.font = f_body
            if r_idx % 2 == 0:
                c.fill = fill_alt
            c.alignment = Alignment(horizontal='center' if col_idx in (4, 7, 9) else 'left', vertical='center')
        ws2.row_dimensions[r_idx].height = 21

    blank_start = len(linked_resources) + 3
    blank_end = blank_start + 29
    for r_idx in range(blank_start, blank_end + 1):
        for col_idx in range(1, 10):
            c = ws2.cell(r_idx, col_idx, _title_formula(r_idx) if col_idx == 2 else None)
            c.border = border
            c.font = f_body
            c.fill = PatternFill('solid', fgColor='F1F5F9') if col_idx == 2 else fill_input
            c.alignment = Alignment(horizontal='center' if col_idx in (4, 7, 9) else 'left', vertical='center')
        ws2.row_dimensions[r_idx].height = 21

    for col_letter, opts in [('D', '"B站,B站合集,Lofter,微博,小红书,其他"'), ('G', '"人工,机翻,生肉"'), ('I', '"有效,失效,需核对"')]:
        dv = DataValidation(type='list', formula1=opts, allow_blank=True)
        ws2.add_data_validation(dv)
        dv.add(f'{col_letter}3:{col_letter}{res_last_row}')
    ws2.freeze_panes = 'A3'
    ws2.auto_filter.ref = f'A2:I{blank_end}'
    for col_idx, w in {1: 15, 2: 32, 3: 29, 4: 11, 5: 54, 6: 18, 7: 11, 8: 16, 9: 11}.items():
        ws2.column_dimensions[get_column_letter(col_idx)].width = w

    # Sheet 5: 进度看板与待处理
    ws4 = wb.create_sheet('进度看板与待处理')
    ws4.merge_cells('A1:L1')
    ws4['A1'] = '熟肉补录进度看板与待处理异常清单'
    _style_merged(ws4, 'A1:L1', font=f_banner, fill=fill_banner, alignment=Alignment(horizontal='left', vertical='center', indent=1))
    ws4.row_dimensions[1].height = 30

    categories = ['主线', '活动', '个人', '卡牌', '其他']
    cat_end = 8 + len(categories)
    total_row = cat_end + 1
    anom_title_row, anom_header_row, anom_start = 26, 27, 28
    anom_end = max(anom_start, anom_start + len(unmatched_anomalies) - 1)
    anom_formula = f'=COUNTA(A{anom_start}:A{anom_end})' if unmatched_anomalies else '=0'

    kpi_defs = [
        ('A3:C3', '剧情总篇数', 'A4:C4', f"=COUNTA('剧情总表'!$M$3:$M${last_s1})", '#,##0'),
        ('D3:F3', '已解析分话数', 'D4:F4', f'=COUNTIF(\'分话出场表\'!$G$3:$G${last_ep},"已解析")', '#,##0'),
        ('G3:I3', '已有熟肉（含合集）', 'G4:I4', f'=COUNTIF(\'剧情总表\'!$I$3:$I${last_s1},"<>待补充")', '#,##0'),
        ('J3:L3', '待处理异常链接', 'J4:L4', anom_formula, '#,##0'),
    ]
    ws4.row_dimensions[3].height = 22
    ws4.row_dimensions[4].height = 30
    for h_rng, h_txt, v_rng, v_form, fmt in kpi_defs:
        ws4.merge_cells(h_rng)
        ws4[h_rng.split(':')[0]] = h_txt
        _style_merged(ws4, h_rng, font=Font(name=font_name, size=9, bold=True, color='FFFFFF'),
                      fill=fill_navy, alignment=Alignment(horizontal='center', vertical='center'), border=border)
        ws4.merge_cells(v_rng)
        tl = ws4[v_rng.split(':')[0]]
        tl.value = v_form
        tl.number_format = fmt
        _style_merged(ws4, v_rng, font=Font(name=font_name, size=16, bold=True, color=navy),
                      fill=fill_kpi, alignment=Alignment(horizontal='center', vertical='center'), border=border)

    ws4.merge_cells('A7:E7')
    ws4['A7'] = '各类型熟肉覆盖进度'
    _style_merged(ws4, 'A7:E7', font=Font(name=font_name, size=11, bold=True, color=navy), alignment=Alignment(horizontal='left', vertical='center'))
    ws4.row_dimensions[7].height = 22
    ws4.row_dimensions[8].height = 23
    for idx, ht in enumerate(['剧情类型', '总篇数', '已有熟肉', '待补充', '覆盖率'], 1):
        c = ws4.cell(8, idx, ht)
        c.font = f_header
        c.fill = fill_navy
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    for i, cat in enumerate(categories, start=9):
        ws4.cell(i, 1, cat)
        ws4.cell(i, 2, f"=COUNTIF('剧情总表'!$A$3:$A${last_s1},A{i})")
        ws4.cell(i, 3, f'=COUNTIFS(\'剧情总表\'!$A$3:$A${last_s1},A{i},\'剧情总表\'!$I$3:$I${last_s1},"<>待补充")')
        ws4.cell(i, 4, f'=COUNTIFS(\'剧情总表\'!$A$3:$A${last_s1},A{i},\'剧情总表\'!$I$3:$I${last_s1},"待补充")')
        ws4.cell(i, 5, f'=IF(B{i}=0,0,C{i}/B{i})')
        for col_idx in range(1, 6):
            c = ws4.cell(i, col_idx)
            c.font = f_body
            c.border = border
            c.alignment = Alignment(horizontal='left' if col_idx == 1 else 'right', vertical='center')
            if col_idx > 1:
                c.number_format = '0.0%' if col_idx == 5 else '#,##0'
        ws4.row_dimensions[i].height = 22

    ws4.cell(total_row, 1, '合计')
    ws4.cell(total_row, 2, f'=SUM(B9:B{cat_end})')
    ws4.cell(total_row, 3, f'=SUM(C9:C{cat_end})')
    ws4.cell(total_row, 4, f'=SUM(D9:D{cat_end})')
    ws4.cell(total_row, 5, f'=IF(B{total_row}=0,0,C{total_row}/B{total_row})')
    tot_border = Border(top=Side(style='thin', color=navy), bottom=double_navy, left=thin, right=thin)
    for col_idx in range(1, 6):
        c = ws4.cell(total_row, col_idx)
        c.font = f_bold
        c.border = tot_border
        c.fill = fill_kpi
        c.alignment = Alignment(horizontal='left' if col_idx == 1 else 'right', vertical='center')
        if col_idx > 1:
            c.number_format = '0.0%' if col_idx == 5 else '#,##0'
    ws4.row_dimensions[total_row].height = 24

    chart = BarChart()
    chart.type = 'col'
    chart.grouping = 'stacked'
    chart.overlap = 100
    chart.style = 10
    chart.title = '各类型剧情熟肉覆盖情况'
    chart.y_axis.title = '篇数'
    chart.width = 16
    chart.height = 8.0
    chart.add_data(Reference(ws4, min_col=3, min_row=8, max_col=4, max_row=cat_end), titles_from_data=True)
    chart.set_categories(Reference(ws4, min_col=1, min_row=9, max_row=cat_end))
    chart.legend.position = 'b'
    chart.series[0].graphicalProperties.solidFill = '2E7D6F'
    chart.series[1].graphicalProperties.solidFill = 'CBD5E1'
    ws4.add_chart(chart, 'G7')

    review_note = f"；待复核分话 {len(review_ep_ids)} 话（{', '.join(review_ep_ids[:5])}）" if review_ep_ids else '；全部已公开分话均已解析'
    ws4.merge_cells(f'A{anom_title_row}:L{anom_title_row}')
    ws4[f'A{anom_title_row}'] = f'待人工处理异常清单（共 {len(unmatched_anomalies)} 条{review_note}；未公开占位共 {unreleased_count} 话）'
    _style_merged(ws4, f'A{anom_title_row}:L{anom_title_row}', font=Font(name=font_name, size=11, bold=True, color=navy), alignment=Alignment(horizontal='left', vertical='center'))
    ws4.row_dimensions[anom_title_row].height = 24

    spans = [(1, 2, '异常类型', 'center'), (3, 5, '原表提示 / 标题', 'left'), (6, 7, 'UP主 / 来源', 'left'),
             (8, 10, '原始链接', 'left'), (11, 12, '建议处理方式', 'left')]
    ws4.row_dimensions[anom_header_row].height = 23
    for c1, c2, htxt, _ in spans:
        rng = f'{get_column_letter(c1)}{anom_header_row}:{get_column_letter(c2)}{anom_header_row}'
        ws4.merge_cells(rng)
        ws4.cell(anom_header_row, c1, htxt)
        _style_merged(ws4, rng, font=f_header, fill=fill_slate, alignment=Alignment(horizontal='center', vertical='center'), border=border)

    for idx, item in enumerate(unmatched_anomalies):
        r = anom_start + idx
        vals = [item['kind'], item['hint'], item['source'], item['url'], item['action']]
        for (c1, c2, _, hal), val in zip(spans, vals):
            rng = f'{get_column_letter(c1)}{r}:{get_column_letter(c2)}{r}'
            ws4.merge_cells(rng)
            cell = ws4.cell(r, c1, val)
            is_url = c1 == 8 and val and str(val).startswith('http') and len(str(val)) > 35
            if is_url:
                cell.hyperlink = val
            _style_merged(ws4, rng, font=f_link if is_url else f_body, fill=fill_alt if r % 2 == 0 else None,
                          alignment=Alignment(horizontal=hal, vertical='center', wrap_text=(c1 in (3, 6, 11))), border=border)
        ws4.row_dimensions[r].height = 24

    for col_idx, w in {1: 12, 2: 11, 3: 12, 4: 12, 5: 12, 6: 4, 7: 15, 8: 15, 9: 15, 10: 15, 11: 16, 12: 16}.items():
        ws4.column_dimensions[get_column_letter(col_idx)].width = w
    ws4.freeze_panes = 'A3'

    for sheet in wb:
        sheet.page_setup.orientation = 'landscape'
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0

    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)

    if export_json:
        export_json = Path(export_json)
        export_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'stories': list(json_stories.values()),
            'resources': [{k: v for k, v in x.items() if k != 'sort_key'} for x in linked_resources],
            'anomalies': unmatched_anomalies,
        }
        export_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return {
        'stories': len(stories),
        'episodes': len(episodes),
        'cast_rows': r_det - 3,
        'linked_resources': len(linked_resources),
        'unreleased': unreleased_count,
        'review_episodes': review_ep_ids,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path, help='story-index.json 路径')
    parser.add_argument('output', type=Path, help='输出 V3 成品 .xlsx 路径')
    parser.add_argument('--preserve', type=Path, default=None, help='可选：已有 V2/V3 人工维护表，保留中文标题/备注/熟肉链接库')
    parser.add_argument('--export-json', type=Path, default=None, help='可选：同步导出 V3 分话结构 JSON')
    args = parser.parse_args()
    stats = export(args.snapshot, args.output, preserve=args.preserve, export_json=args.export_json)
    print(f"Generated {args.output} | stories={stats['stories']}, episodes={stats['episodes']}, "
          f"cast_rows={stats['cast_rows']}, links={stats['linked_resources']}, "
          f"unreleased={stats['unreleased']}, review={len(stats['review_episodes'])}")


if __name__ == '__main__':
    main()
