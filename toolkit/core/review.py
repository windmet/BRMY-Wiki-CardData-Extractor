"""Three-level row status for Wiki tables and the per-run review summary workbook."""
from pathlib import Path

from .feedback import feedback_groups, issue_text

OK, REVIEW, MISSING = '正常', '待核对', '缺失'
SUMMARY_NAME = '待核对汇总.xlsx'

# Internal resolution codes -> (status, plain reason). Unknown codes fall back to 待核对.
REASONS = {
    'resolved': (OK, ''),
    'named': (OK, ''),
    'explicit': (OK, ''),
    'missing_costume': (MISSING, '找不到对应服装'),
    'costume_name_unavailable': (MISSING, '服装没有名称'),
    'conflicting_costume': (REVIEW, '同一阶段指向多套服装'),
    'ambiguous_costume': (REVIEW, '服装编号对应多条记录'),
    'name_unavailable': (MISSING, '游戏数据里没有名称，表中以编号代替'),
    'missing_target': (MISSING, '找不到关联的目标章节'),
    'unsupported_story_type': (REVIEW, '剧情类型暂未适配'),
    'missing_or_ambiguous_event_story': (REVIEW, '找不到或有多个对应活动剧情'),
    'unsupported_target': (REVIEW, '语音对象暂未适配'),
    'missing_package': (MISSING, '缺少语音包'),
    'missing_cue_text': (MISSING, '语音包里没有这条台词'),
    'conflicting_text': (REVIEW, '同一条语音有多份不同文本'),
    'missing_master': (MISSING, '游戏数据里没有这条语音'),
    'ambiguous_master': (REVIEW, '游戏数据里有多条同号语音'),
    'missing_acb_cue': (MISSING, '语音包里没有这条语音'),
    'unstable_metadata': (REVIEW, '语音包信息不稳定'),
    'empty_text': (MISSING, '语音文本为空'),
}
_RANK = {OK: 0, REVIEW: 1, MISSING: 2}


def status_of(*codes):
    """Return (status, reason) for one or more internal codes; the worst status wins."""
    status, reasons = OK, []
    for code in codes:
        level, reason = REASONS.get(code, (REVIEW, f'未识别的状态：{code}'))
        if _RANK[level] > _RANK[status]:
            status = level
        if reason and reason not in reasons:
            reasons.append(reason)
    return status, '；'.join(reasons)


def _identity(row, status_index):
    """The first two non-empty cells before the status column identify the row for a reader."""
    cells = [str(value) for value in row[:status_index] if value not in (None, '')]
    return ' / '.join(cells[:2])


def _sheet_rows(path):
    """Yield (sheet, row number, identity, column, status, reason) for flagged rows of one workbook."""
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True)
    try:
        for sheet in workbook.worksheets:
            rows = sheet.iter_rows(values_only=True)
            headers = [str(value or '') for value in next(rows, ())]
            whole_sheet = '待核对' in sheet.title
            columns = [index for index, header in enumerate(headers)
                       if header.endswith('状态') and header != '日期状态']
            notes = [index for index, header in enumerate(headers) if header in ('问题类型', '说明')]
            if not columns and not whole_sheet:
                continue
            for number, row in enumerate(rows, start=2):
                reason = '：'.join(str(row[index]) for index in notes if index < len(row) and row[index])
                if whole_sheet:
                    yield sheet.title, number, _identity(row, len(row)), '', REVIEW, reason
                    continue
                for index in columns:
                    value = row[index] if index < len(row) else None
                    if value in (REVIEW, MISSING):
                        yield sheet.title, number, _identity(row, index), headers[index], value, reason
    finally:
        workbook.close()


def summary_rows(result, group_threshold=10):
    """One row per issue; many identical-reason rows in one sheet collapse into one line."""
    rows, files = [], {}
    for artifact in result.get('artifacts', []):
        if artifact['kind'] == 'wiki':
            files.setdefault(artifact['domain'], []).append(Path(artifact['path']).name)
    for key in ('errors', 'review'):
        for issue in feedback_groups(result)[key]:
            domain = issue.get('domain', '') if isinstance(issue, dict) else ''
            where = '、'.join(files.get(domain, [])) or domain or '整次运行'
            rows.append(['运行失败' if key == 'errors' else '运行提示', where, '', '', '', '', issue_text(issue)])
    for artifact in result.get('artifacts', []):
        path = Path(artifact['path'])
        if artifact['kind'] != 'wiki' or path.suffix != '.xlsx' or path.name == SUMMARY_NAME:
            continue
        groups = {}
        for sheet, number, identity, column, status, reason in _sheet_rows(path):
            groups.setdefault((sheet, column, status, reason), []).append((number, identity))
        for (sheet, column, status, reason), hits in groups.items():
            why = reason or (f'{column}为“{status}”' if column else '本表每行都需要人工核对')
            if column and len(hits) > group_threshold:
                numbers = '、'.join(str(number) for number, _ in hits[:5])
                rows.append([status, path.name, sheet, f'{numbers} 等 {len(hits)} 行', '', column, why])
            else:
                rows.extend([status, path.name, sheet, number, identity, column, why] for number, identity in hits)
    return rows


def write_summary(result, directory):
    """Write 待核对汇总.xlsx next to the Wiki tables and return its path."""
    from .exporter import write_workbook
    rows = summary_rows(result) or [[OK, '', '', '', '', '', '本次没有需要核对的内容']]
    return write_workbook(str(Path(directory) / SUMMARY_NAME), [{
        'title': '待核对汇总',
        'headers': ['类别', '文件 / 任务', '工作表', '行号', '这一行是', '状态列', '为什么要看'],
        'rows': rows,
        'col_widths': {'A': 10, 'B': 26, 'C': 18, 'D': 16, 'E': 30, 'F': 12, 'G': 60},
        'wrap_cols': [7],
    }])
