import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import PatternFill

from scripts.export_story_v2 import export as export_v2
from toolkit.core.tables import TableCatalog
from toolkit.domains.story_catalog import extract
from toolkit.story_index import build


def _write_master(path: Path, tables: dict):
    payload = [dict.fromkeys(tables, []), *tables.values()]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def _make_v2_template(path: Path, rows: list[list]):
    wb = Workbook()
    cat = wb.active
    cat.title = '剧情总表'
    cat.append(['Break My Case 剧情总表（V2）'])
    cat.append(['类型', '系列 / 关联活动', '日文标题', '中文标题', '归属角色', '实装日期', '话数',
                '出场角色（按剧本署名）', '熟肉状态', '熟肉链接', '翻译 / UP主', '备注', '剧情ID'])
    for idx, row in enumerate(rows, 3):
        cat.append(row)
        cat.cell(idx, 9).value = f'=IF(COUNTIF(熟肉链接库!$A$3:$A$1000,M{idx})=0,"待补充","已有")'
        cat.cell(idx, 10).value = f'=IF(COUNTIF(熟肉链接库!$A$3:$A$1000,M{idx})=0,"",INDEX(熟肉链接库!$E$3:$E$1000,MATCH(M{idx},熟肉链接库!$A$3:$A$1000,0)))'
        cat.cell(idx, 11).value = f'=IF(COUNTIF(熟肉链接库!$A$3:$A$1000,M{idx})=0,"",INDEX(熟肉链接库!$F$3:$F$1000,MATCH(M{idx},熟肉链接库!$A$3:$A$1000,0)))'
    last = 2 + len(rows)
    cat.auto_filter.ref = f'A2:M{last}'
    cat.conditional_formatting.add(f'I3:I{last}', CellIsRule(operator='equal', formula=['"待补充"'], fill=PatternFill('solid', fgColor='FFF2CC')))

    links = wb.create_sheet('熟肉链接库')
    links.append(['熟肉链接库'])
    links.append(['剧情ID', '对应剧情（自动）', '覆盖范围', '平台', '熟肉链接', '翻译 / UP主', '翻译类型', '进度', '链接状态'])
    links.append(['main-3-1', f'=IF(A3="","",INDEX(剧情总表!$C$3:$C${last},MATCH(A3,剧情总表!$M$3:$M${last},0)))',
                  '全篇', 'B站', 'https://www.bilibili.com/video/BV1xx411c7mD', 'UP', '人工', '完结', '有效'])

    cast = wb.create_sheet('角色出场汇总')
    cast.append(['角色出场汇总'])
    cast.append(['类型', '剧情标题', '角色名', '角色分类', '出场话数', '台词数', '剧情ID'])
    cast.append(['主线', '占位', '皇坂逢', '主要角色', 1, 1, 'main-3-1'])

    alias = wb.create_sheet('角色别名映射')
    alias.append(['别名表'])

    dash = wb.create_sheet('进度看板与待处理')
    dash.append(['看板'])
    dash.append(['总篇数', f'=COUNTA(剧情总表!$M$3:$M${last})', f'=COUNTIF(剧情总表!$I$3:$I${last},"待补充")'])

    wb.save(path)


class StoryIndexTests(unittest.TestCase):
    def test_story_catalog_extracts_campaign_sections(self):
        tables = {
            'mst_campaign': [{'CampaignId': 7, 'CampaignTitle': 'April Fools'}],
            'mst_campaign_story_section': [
                {'CampaignId': 7, 'CampaignStorySectionNo': 1, 'TitleName': 'Intro', 'ReleaseDateTime': '2025-04-01T00:00:00Z'},
            ],
        }
        data = extract(SimpleNamespace(tables=TableCatalog([dict.fromkeys(tables, []), *tables.values()])), as_of='2026-09-09T00:00:00Z')
        self.assertEqual(1, len(data['Sections']))
        self.assertEqual('campaign', data['Sections'][0]['Kind'])
        self.assertEqual([7, 1], data['Sections'][0]['Key'])

    def test_build_classification_interlude_rerun_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master = root / 'master_data.json'
            station = root / 'station'
            (station / 'ep').mkdir(parents=True)
            wiki = root / 'bwiki.html'

            tables = {
                'mst_character': [
                    {'CharacterId': 1, 'CharacterNameJpn': '皇坂 逢'},
                ],
                'mst_main_story': [
                    {'MainStoryThreadNo': 3, 'TitleName': 'I', 'MainStoryTypeCode': 2},
                ],
                'mst_main_story_chapter': [
                    {'MainStoryThreadNo': 3, 'MainStoryChapterNo': 1, 'TitleName': ''},
                ],
                'mst_main_story_section': [
                    {'MainStoryThreadNo': 3, 'MainStoryChapterNo': 1, 'MainStorySectionNo': 1,
                     'TitleName': '第1話', 'ReleaseDateTime': '2024-11-08T00:00:00Z'},
                ],
                'mst_event': [
                    {'EventId': 3, 'EventTitle': 'Prequel 礎を仰ぐ瞳', 'EventFormat': 1, 'OpenStartTime': '2024-06-01T00:00:00Z'},
                    {'EventId': 25, 'EventTitle': 'Travelogue 蒼海に結ぶ思い出', 'EventFormat': 2, 'OpenStartTime': '2025-06-01T00:00:00Z'},
                    {'EventId': 11, 'EventTitle': '1st Anniversary', 'EventFormat': 3, 'OpenStartTime': '2025-05-09T00:00:00Z'},
                ],
                'mst_event_story': [
                    {'EventId': 3, 'TitleName': ''},
                    {'EventId': 25, 'TitleName': ''},
                    {'EventId': 11, 'TitleName': ''},
                ],
                'mst_event_story_section': [
                    {'EventId': 3, 'EventStorySectionNo': 1, 'TitleName': '第1話', 'ReleaseDateTime': '2024-06-01T00:00:00Z'},
                    {'EventId': 25, 'EventStorySectionNo': 1, 'TitleName': '第1話', 'ReleaseDateTime': '2025-06-01T00:00:00Z'},
                    {'EventId': 11, 'EventStorySectionNo': 1, 'TitleName': '第1話', 'ReleaseDateTime': '2025-05-09T00:00:00Z'},
                ],
                'mst_main_story_from_other_story_type_chapter': [
                    {'MainStoryThreadNo': 1, 'MainStoryFromOtherStoryTypeChapterNo': 3, 'StoryTypeCode': 4, 'StoryTargetChapterId': 3, 'TitleName': 'Prequel'},
                ],
                'mst_main_story_from_other_story_type_section': [
                    {'MainStoryThreadNo': 1, 'MainStoryFromOtherStoryTypeChapterNo': 3, 'MainStoryFromOtherStoryTypeSectionNo': 1, 'TitleName': '第1話'},
                ],
                'mst_character_card': [
                    {'CharacterCardId': 68, 'CharacterId': 1, 'CharacterCardName': '花束の記憶', 'ReleaseDateTime': ''},
                    {'CharacterCardId': 136, 'CharacterId': 1, 'CharacterCardName': '旧常驻卡', 'ReleaseDateTime': '2024-05-09T00:00:00Z'},
                    {'CharacterCardId': 200, 'CharacterId': 1, 'CharacterCardName': '#ff00aa', 'ReleaseDateTime': '2024-07-01T00:00:00Z'},
                ],
                'mst_character_card_story': [
                    {'CharacterCardId': 68},
                    {'CharacterCardId': 136},
                    {'CharacterCardId': 200},
                ],
                'mst_character_card_story_section': [
                    {'CharacterCardId': 68, 'CharacterCardStorySectionNo': 1, 'TitleName': '第1話', 'ReleaseDateTime': ''},
                    {'CharacterCardId': 136, 'CharacterCardStorySectionNo': 1, 'TitleName': '第1話', 'ReleaseDateTime': '2024-05-09T00:00:00Z'},
                    {'CharacterCardId': 200, 'CharacterCardStorySectionNo': 1, 'TitleName': '第1話', 'ReleaseDateTime': '2024-07-01T00:00:00Z'},
                ],
                'mst_event_a': [
                    {'EventId': 3, 'CharacterCardIds': [68]},
                    {'EventId': 11, 'CharacterCardIds': [68, 136]},
                ],
                'mst_login_story_section': [
                    {'LoginStoryId': 1, 'LoginStorySectionNo': 1, 'TitleName': '1st Anniversary Login [1日目]', 'ReleaseDateTime': '2025-05-09T00:00:00Z'},
                ],
            }
            _write_master(master, tables)

            index = {
                'categories': [
                    {'id': 'main', 'groups': [{'episodes': [{'id': 'main-3-1-1'}]}]},
                    {'id': 'event', 'groups': [{'episodes': [{'id': 'event-3-1'}, {'id': 'prequel-1-3-1'}]}]},
                ]
            }
            (station / 'index.json').write_text(json.dumps(index, ensure_ascii=False), encoding='utf-8')
            (station / 'ep' / 'main-3-1-1.json').write_text(
                json.dumps([['c', '皇坂 逢', 'hello', 0], ['c', '<SelfFirstName>', 'hi', 0]], ensure_ascii=False),
                encoding='utf-8',
            )
            (station / 'ep' / 'event-3-1.json').write_text(
                json.dumps([['c', '皇坂 逢', 'line1', 0], ['c', '謎の男', 'line2', 0]], ensure_ascii=False),
                encoding='utf-8',
            )
            (station / 'ep' / 'prequel-1-3-1.json').write_text(
                json.dumps([['c', '皇坂 逢', 'line1', 0], ['c', '謎の男', 'line2', 0]], ensure_ascii=False),
                encoding='utf-8',
            )
            wiki.write_text(
                '<div class="mw-parser-output"><h3>活动</h3><table>'
                '<tr><th>类型</th><th>活动名</th><th>链接</th><th>UP</th><th>进度</th></tr>'
                '<tr><td>活动</td><td>Prequel 礎を仰ぐ瞳</td>'
                '<td><a href="https://www.bilibili.com/video/BV1xx411c7mD">P1</a></td><td>UP1</td><td>完结</td></tr>'
                '</table></div>',
                encoding='utf-8',
            )

            data = build(master, station, wiki, '2026-11-26')
            by_id = {row[0]: row for row in data['剧情总表'][1:]}

            # Interlude falls back to series name instead of blank title
            self.assertEqual('Interlude I', by_id['main-3-1'][2])
            self.assertEqual('Interlude I', by_id['main-3-1'][4])

            # Prequel and Travelogue are event -> banner; anniversary event stays 活动 and login stays 其他 with series=周年活动
            self.assertEqual('活动', by_id['event-3'][1])
            self.assertEqual('部门箱活（banner）', by_id['event-3'][15])
            self.assertEqual('活动', by_id['event-25'][1])
            self.assertEqual('部门箱活（banner）', by_id['event-25'][15])
            self.assertEqual('活动', by_id['event-11'][1])
            self.assertEqual('周年活动', by_id['event-11'][4])
            self.assertEqual('其他', by_id['login-1'][1])
            self.assertEqual('周年活动', by_id['login-1'][4])

            # Rerun/pickup card does not steal origin event; missing card date falls back to origin open date
            self.assertEqual(3, by_id['card-68'][6])
            self.assertEqual('Prequel 礎を仰ぐ瞳', by_id['card-68'][4])
            self.assertEqual('2024-06-01T00:00:00Z', by_id['card-68'][9])
            self.assertEqual('关联活动开放日（推定）', by_id['card-68'][18])
            self.assertEqual('', by_id['card-136'][6])
            self.assertEqual('一轮生日', by_id['card-200'][4])

            # Test V2 export: preserves manual columns, removes alias sheet, deduplicates reread, appends new story_ids
            snap_path = root / 'story-index.json'
            snap_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            tpl_path = root / 'tpl.xlsx'
            out_path = root / 'out.xlsx'
            _make_v2_template(tpl_path, [
                ['主线', 'Interlude I', 'Interlude I', '人工中文名', None, None, 1, None, None, None, None, '人工备注', 'main-3-1'],
                ['活动', 'Prequel', 'Prequel 礎を仰ぐ瞳', None, None, None, 1, None, None, None, None, None, 'event-3'],
                ['卡牌', None, '花束の記憶', None, '皇坂逢', None, 1, None, None, None, None, None, 'card-68'],
            ])

            export_v2(tpl_path, snap_path, out_path)
            wb = load_workbook(out_path, data_only=False)
            self.assertEqual(['剧情总表', '熟肉链接库', '角色出场汇总', '进度看板与待处理'], wb.sheetnames)

            cat = wb['剧情总表']
            self.assertEqual(2 + len(by_id), cat.max_row)
            # Manual columns preserved on existing row, Interlude title preserved
            self.assertEqual('Interlude I', cat['C3'].value)
            self.assertEqual('人工中文名', cat['D3'].value)
            self.assertEqual('人工备注', cat['L3'].value)
            # Banner series updated
            self.assertEqual('部门箱活（banner） / Prequel', cat['B4'].value)
            # Appended rows get formulas, owner name, and IDs
            appended = {cat.cell(r, 13).value: r for r in range(3, cat.max_row + 1)}
            self.assertIn('card-200', appended)
            r_200 = appended['card-200']
            self.assertEqual('皇坂逢', cat.cell(r_200, 5).value)
            self.assertEqual('一轮生日', cat.cell(r_200, 2).value)
            self.assertIn(f'M{r_200}', cat.cell(r_200, 9).value)

            # Extended filter, conditional formatting, and cross-sheet formula ranges
            expected_last = cat.max_row
            self.assertEqual(f'A2:M{expected_last}', cat.auto_filter.ref)
            cf_ranges = [str(cf.sqref) for cf in cat.conditional_formatting]
            self.assertEqual([f'I3:I{expected_last}'], cf_ranges)
            self.assertIn(f'$M$3:$M${expected_last}', wb['熟肉链接库']['B3'].value)
            self.assertIn(f'$M$3:$M${expected_last}', wb['进度看板与待处理']['B2'].value)
            self.assertIn(f'$I$3:$I${expected_last}', wb['进度看板与待处理']['C2'].value)

            # Reread episode is not double-counted in cast summary and Interlude title is populated
            cast_rows = list(wb['角色出场汇总'].values)[2:]
            event3_cast = {(r[2], r[3]): (r[4], r[5]) for r in cast_rows if r[6] == 'event-3'}
            self.assertEqual({('皇坂逢', '主要角色'): (1, 1), ('謎の男', '其他署名'): (1, 1)}, event3_cast)
            main3_cast = [r for r in cast_rows if r[6] == 'main-3-1']
            self.assertEqual('Interlude I', main3_cast[0][1])

            # Re-running against an already-cleaned V2 workbook is idempotent (no 角色别名映射 error)
            out_path2 = root / 'out2.xlsx'
            export_v2(out_path, snap_path, out_path2)
            wb2 = load_workbook(out_path2, data_only=False)
            self.assertEqual(expected_last, wb2['剧情总表'].max_row)


if __name__ == '__main__':
    unittest.main()
