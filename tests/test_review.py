import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from toolkit.core.review import MISSING, OK, REVIEW, status_of, summary_rows, write_summary


def workbook(path, sheets):
    wb = Workbook(); wb.remove(wb.active)
    for title, rows in sheets.items():
        sheet = wb.create_sheet(title)
        for row in rows:
            sheet.append(row)
    wb.save(path)
    return {'path': str(path), 'kind': 'wiki', 'domain': 'demo'}


class ReviewTests(unittest.TestCase):
    def test_status_maps_codes_to_three_levels_and_worst_wins(self):
        self.assertEqual((OK, ''), status_of('resolved'))
        self.assertEqual((MISSING, '语音文本为空'), status_of('resolved', 'empty_text'))
        self.assertEqual(MISSING, status_of('conflicting_text', 'missing_master')[0])
        status, reason = status_of('brand_new_code')
        self.assertEqual(REVIEW, status)
        self.assertIn('brand_new_code', reason)

    def test_summary_lists_flagged_rows_and_run_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            table = workbook(root / 'demo.xlsx', {
                'Main': [['编号', '名称', '日期状态', '关联状态', '说明'],
                         [1, 'a', '待核对', OK, ''],
                         [2, 'b', '已结束', MISSING, '找不到对应服装'],
                         [3, 'c', '已结束', REVIEW, '']],
                '卡牌语音待核对': [['卡牌ID', '卡牌名', '问题类型', '说明'], [7, 'x', '文本为空', '请试听']],
            })
            result = {'errors': [], 'artifacts': [table],
                      'warnings': [{'domain': 'demo', 'warning': '13 个主体不完整'},
                                   {'domain': 'resources', 'kind': 'offline_snapshot', 'warning': 'offline'}]}
            rows = summary_rows(result)
            self.assertIn(['运行提示', 'demo.xlsx', '', '', '', '', '13 个主体不完整'], rows)
            self.assertIn([MISSING, 'demo.xlsx', 'Main', 3, '2 / b', '关联状态', '找不到对应服装'], rows)
            self.assertIn([REVIEW, 'demo.xlsx', 'Main', 4, '3 / c', '关联状态', '关联状态为“待核对”'], rows)
            self.assertIn([REVIEW, 'demo.xlsx', '卡牌语音待核对', 2, '7 / x', '', '文本为空：请试听'], rows)
            # 日期状态 is a time phase, not a data problem; informational warnings stay out.
            self.assertEqual(4, len(rows))

    def test_many_rows_with_one_reason_collapse_into_one_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [['编号', '名称状态', '说明']] + [[i, MISSING, '没有名称'] for i in range(30)]
            result = {'artifacts': [workbook(root / 'big.xlsx', {'honor': rows})]}
            [line] = summary_rows(result)
            self.assertEqual([MISSING, 'big.xlsx', 'honor', '2、3、4、5、6 等 30 行', '', '名称状态', '没有名称'], line)

    def test_written_summary_says_so_when_nothing_needs_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_summary({'artifacts': []}, directory)
            sheet = load_workbook(path).active
            self.assertEqual('待核对汇总.xlsx', Path(path).name)
            self.assertEqual('为什么要看', sheet['G1'].value)
            self.assertEqual('本次没有需要核对的内容', sheet['G2'].value)


if __name__ == '__main__':
    unittest.main()
