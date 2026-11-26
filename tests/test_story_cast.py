import json
import lzma
import tempfile
import unittest
from pathlib import Path

import msgpack
from openpyxl import load_workbook

from toolkit.core.domain_contracts import validate_domain_input
from toolkit.core.session import MasterDataSession
from toolkit.domains import story_cast
from toolkit.gui import JobRequest
from toolkit.resolve import build_plan, MASTER_KEY
from scripts import export_story_v3


def _script_bytes(commands, *, lzma_layers=0):
    payload = msgpack.packb([commands], use_bin_type=True)
    for _ in range(lzma_layers):
        payload = lzma.compress(payload, format=lzma.FORMAT_ALONE)
    return payload


def _make_tables():
    return {
        'mst_character': [
            {'CharacterId': 1, 'CharacterNameJpn': '皇坂 逢', 'CharacterGroupCode': 1, 'IsActive': True},
            {'CharacterId': 13, 'CharacterNameJpn': '新開 戦', 'CharacterGroupCode': 4, 'IsActive': True},
            {'CharacterId': 14, 'CharacterNameJpn': '相沢 篠信', 'CharacterGroupCode': 4, 'IsActive': True},
            {'CharacterId': 23, 'CharacterNameJpn': '伊達 幸邑', 'CharacterGroupCode': 99, 'IsActive': True},
        ],
        'mst_main_story': [
            {'MainStoryThreadNo': 2, 'TitleName': '1', 'MainStoryTypeCode': 1, 'IsActive': True},
            {'MainStoryThreadNo': 3, 'TitleName': 'I', 'MainStoryTypeCode': 2, 'IsActive': True},
        ],
        'mst_main_story_chapter': [
            {'MainStoryThreadNo': 2, 'MainStoryChapterNo': 3, 'TitleName': 'Sly Red', 'IsActive': True},
            {'MainStoryThreadNo': 3, 'MainStoryChapterNo': 1, 'TitleName': '', 'IsActive': True},
        ],
        'mst_main_story_section': [
            {'MainStoryThreadNo': 2, 'MainStoryChapterNo': 3, 'MainStorySectionNo': 2,
             'TitleName': '第2話', 'ReleaseDateTime': '2024-05-09T00:00:00+00:00', 'IsActive': True},
            {'MainStoryThreadNo': 3, 'MainStoryChapterNo': 1, 'MainStorySectionNo': 1,
             'TitleName': '第1話', 'ReleaseDateTime': '2024-11-01T00:00:00+00:00', 'IsActive': True},
        ],
        'mst_puzzle_story': [
            {'StoryTypeCode': 1, 'StoryTargetBaseId': 2, 'StoryTargetChapterId': 3,
             'StoryTargetSectionNo': 2, 'PuzzleStoryNo': 1, 'StoryFileName': 'main_2_3_2_in-pazzle', 'IsActive': True},
        ],
        'mst_puzzle_story_stage': [
            {'StoryTypeCode': 1, 'StoryTargetBaseId': 2, 'StoryTargetChapterId': 3,
             'StoryTargetSectionNo': 2, 'PuzzleClearStoryFileName': 'main_2_3_2_after-pazzle',
             'RereadStoryFileName': 'main_2_3_2_skip-pazzle', 'IsActive': True},
        ],
        'mst_event': [
            {'EventId': 3, 'EventTitle': 'Prequel Test', 'OpenStartTime': '2024-06-01T00:00:00+00:00', 'IsActive': True},
            {'EventId': 99, 'EventTitle': '1st Anniversary Event', 'OpenStartTime': '2025-05-09T00:00:00+00:00', 'IsActive': True},
        ],
        'mst_event_story': [
            {'EventId': 3, 'TitleName': 'Prequel Test', 'IsActive': True},
            {'EventId': 99, 'TitleName': '1st Anniversary Event', 'IsActive': True},
        ],
        'mst_event_story_section': [
            {'EventId': 3, 'EventStorySectionNo': 1, 'TitleName': '第1話', 'ReleaseDateTime': '2024-06-01T00:00:00+00:00', 'IsActive': True},
            {'EventId': 99, 'EventStorySectionNo': 1, 'TitleName': '第1話', 'ReleaseDateTime': '2025-05-09T00:00:00+00:00', 'IsActive': True},
        ],
        'mst_main_story_from_other_story_type_chapter': [
            {'MainStoryThreadNo': 1, 'MainStoryFromOtherStoryTypeChapterNo': 3,
             'StoryTypeCode': 4, 'StoryTargetChapterId': 3, 'TitleName': 'Prequel Test', 'IsActive': True},
        ],
        'mst_main_story_from_other_story_type_section': [
            {'MainStoryThreadNo': 1, 'MainStoryFromOtherStoryTypeChapterNo': 3,
             'MainStoryFromOtherStoryTypeSectionNo': 1, 'TitleName': '第1話', 'IsActive': True},
        ],
        'mst_character_story': [
            {'CharacterId': 1, 'CharacterStoryChapterNo': 1, 'TitleName': '', 'IsActive': True},
        ],
        'mst_character_story_section': [
            {'CharacterId': 1, 'CharacterStoryChapterNo': 1, 'CharacterStorySectionNo': 1,
             'TitleName': '第1話', 'ReleaseDateTime': '2024-05-09T00:00:00+00:00', 'IsActive': True},
            {'CharacterId': 1, 'CharacterStoryChapterNo': 1, 'CharacterStorySectionNo': 2,
             'TitleName': '第2話', 'ReleaseDateTime': '3001-01-01T00:00:00+00:00', 'IsActive': True},
        ],
        'mst_character_card': [
            {'CharacterCardId': 10, 'CharacterId': 1, 'CharacterCardName': '#1a2b3c', 'ReleaseDateTime': '2001-01-01T00:00:00+00:00', 'IsActive': True},
        ],
        'mst_character_card_story': [
            {'CharacterCardId': 10, 'TitleName': '#1a2b3c', 'IsActive': True},
        ],
        'mst_character_card_story_section': [
            {'CharacterCardId': 10, 'CharacterCardStorySectionNo': 1, 'TitleName': '第1話', 'IsActive': True},
        ],
        'mst_campaign': [],
        'mst_campaign_story_section': [],
        'mst_login_story_section': [],
        'mst_event_a': [
            {'EventId': 3, 'CharacterCardIds': [10], 'IsActive': True},
            {'EventId': 99, 'PickUpCharacterCardIds': [10], 'IsActive': True},
        ],
        'mst_event_b': [],
        'mst_event_c': [],
        'mst_event_accumulate_item': [],
    }


def _write_master(path, tables):
    header = {name: [0, 0] for name in tables}
    path.write_text(json.dumps([header, *tables.values()], ensure_ascii=False), encoding='utf-8')


class StoryCastDomainTests(unittest.TestCase):
    def test_resource_keys_and_plan_use_puzzle_reread_script(self):
        with tempfile.TemporaryDirectory() as td:
            master = Path(td) / 'master_data.json'
            _write_master(master, _make_tables())
            session = MasterDataSession.open(master)
            validate_domain_input('story_cast', session.tables)

            keys = story_cast.resource_keys(session.tables)
            self.assertIn('Scripts/main_2_3_2_skip-pazzle.s2bscript', keys)
            self.assertNotIn('Scripts/main_2_3_2.s2bscript', keys)
            self.assertIn('Scripts/main_3_1_1.s2bscript', keys)
            self.assertIn('Scripts/event_3_1.s2bscript', keys)
            self.assertIn('Scripts/card_10_1_1.s2bscript', keys)

            resources = {MASTER_KEY: None, 'Scripts/main_2_3_2_skip-pazzle.s2bscript': None,
                         'Scripts/event_3_1.s2bscript': None}
            plan = build_plan(['story_cast'], resources, session.tables)
            self.assertEqual([], plan['errors'])
            planned_keys = {r['key'] for r in plan['resources']}
            self.assertIn('Scripts/main_2_3_2_skip-pazzle.s2bscript', planned_keys)
            self.assertIn('Scripts/event_3_1.s2bscript', planned_keys)

    def test_extract_and_export_follow_v3_rules_and_walk_branches(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            master = root / 'master_data.json'
            _write_master(master, _make_tables())
            scripts_dir = root / 'scripts'
            scripts_dir.mkdir()

            # Puzzle reread script with branching choice + NPC + alias + garbage + player placeholder
            (scripts_dir / 'main_2_3_2_skip-pazzle.s2bscript').write_bytes(_script_bytes([
                [1, [2, 3], 'Selection', 'Show', {'message1': 'A', 'message2': 'B'}],
                [2, [4], 'Chat', 'Show', {'chatTitle': '相沢 篠信', 'chat': 'hi'}],
                [3, [4], 'Chat', 'Show', {'chatTitle': '新開 戦', 'chat': 'branch2'}],
                [4, [5], 'Chat', 'Show', {'chatTitle': '伊達 幸邑', 'chat': 'npc'}],
                [5, [6], 'Chat', 'Show', {'chatTitle': 'Kornelius', 'chat': 'alias kept'}],
                [6, [7], 'Chat', 'Show', {'chatTitle': '<SelfLastName> <SelfFirstName>', 'chat': 'player'}],
                [7, [-1], 'Chat', 'Show', {'chatTitle': '・', 'chat': 'garbage'}],
            ], lzma_layers=1))
            (scripts_dir / 'main_3_1_1.s2bscript').write_bytes(_script_bytes([
                [1, [-1], 'Chat', 'Show', {'chatTitle': '皇坂 逢', 'chat': 'interlude'}],
            ]))
            (scripts_dir / 'event_3_1.s2bscript').write_bytes(_script_bytes([
                [1, [2], 'Chat', 'Show', {'chatTitle': '皇坂 逢', 'chat': 'prequel'}],
                [2, [-1], 'Chat', 'Show', {'chatTitle': 'Man A', 'chat': 'npc english'}],
            ]))
            (scripts_dir / 'event_99_1.s2bscript').write_bytes(_script_bytes([
                [1, [-1], 'Chat', 'Show', {'chatTitle': '皇坂 逢', 'chat': 'anniv'}],
            ]))
            (scripts_dir / 'personal_1_1_1.s2bscript').write_bytes(_script_bytes([
                [1, [-1], 'Chat', 'Show', {'chatTitle': '皇坂 逢', 'chat': 'ep1'}],
            ]))
            (scripts_dir / 'card_10_1_1.s2bscript').write_bytes(_script_bytes([
                [1, [-1], 'Chat', 'Show', {'chatTitle': '皇坂 逢', 'chat': 'bday'}],
            ]))

            session = MasterDataSession.open(master)
            data = story_cast.extract(session, source=scripts_dir, as_of='2026-11-26T00:00:00+00:00')
            self.assertEqual([], data['Issues'])
            self.assertEqual(1, data['Unreleased'])
            self.assertEqual(6, data['Loaded'])

            by_sid = {s['story_id']: s for s in data['Stories']}
            self.assertEqual('Interlude I', by_sid['main-3-1']['jp_title'])
            self.assertEqual('周年活动', by_sid['event-99']['type'])
            self.assertEqual('活动', by_sid['event-3']['type'])
            self.assertEqual('部门箱活（banner） / Prequel', by_sid['event-3']['series'])
            self.assertEqual('一轮生日', by_sid['card-10']['series'])
            self.assertEqual('2024-06-01', by_sid['card-10']['release_date'])

            by_eid = {e['episode_id']: e for e in data['Episodes']}
            self.assertEqual('未公开', by_eid['character-1-1-2']['status'])
            self.assertEqual('已解析', by_eid['main-2-3-2']['status'])
            sp_map = {s['name']: s['category'] for s in by_eid['main-2-3-2']['speakers']}
            self.assertEqual('主要角色', sp_map['相沢篠信'])
            self.assertEqual('主要角色', sp_map['新開戦'])
            self.assertEqual('NPC', sp_map['伊達幸邑'])
            self.assertEqual('NPC', sp_map['Kornelius'])
            self.assertNotIn('・', sp_map)
            self.assertEqual(['皇坂逢', 'Man A'], [s['name'] for s in by_eid['event-3-1']['speakers']])

            # Export workbook via toolkit.generate
            from types import SimpleNamespace
            from unittest.mock import patch
            from toolkit.generate import generate
            out_dir = root / 'out'
            fake_session = SimpleNamespace(
                tables=session.tables,
                assessment=SimpleNamespace(changes=[], errors=[]),
                write_audit=lambda *a, **kw: None,
            )
            with patch('toolkit.generate.MasterDataSession.open', return_value=fake_session):
                report = generate(['story_cast'], out_dir, masterdata=master, source=scripts_dir, as_of='2026-11-26T00:00:00+00:00')
            self.assertEqual('PASS', report['status'], report['errors'])
            wb = load_workbook(out_dir / 'wiki_output' / 'story_cast.xlsx')
            self.assertEqual(['剧情总表', '分话出场表', '分话角色明细', '说明'], wb.sheetnames)
            self.assertEqual('未公开', next(r[6] for r in wb['分话出场表'].iter_rows(min_row=3, values_only=True) if r[8] == 'character-1-1-2'))

    def test_gui_local_validation_requires_source_for_story_cast(self):
        with tempfile.TemporaryDirectory() as td:
            master = Path(td) / 'master.json'
            master.write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, r'\.s2bscript'):
                JobRequest('local', ['story_cast'], td, '', masterdata=str(master)).validate()
            scripts_dir = Path(td) / 'scripts'
            scripts_dir.mkdir()
            JobRequest('local', ['story_cast'], td, '', masterdata=str(master), source=str(scripts_dir)).validate()

    def test_export_story_v3_builds_5_sheets_and_preserves_manual_columns(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snap = root / 'story-index.json'
            payload = {
                '剧情总表': [
                    ['story_id', '剧情类型', '日文名称', '中文名称', '系列', '角色归属ID', '活动ID', '卡牌ID', '活动形式码', '索引日期', '年份', '原表话数', '熟肉索引状态', '主线关联', '内部时间线', '活动形式', '有轴话数', '原始分类', '日期依据'],
                    ['main-3-1', '主线', 'Interlude I', '', 'Interlude I', None, '', '', '', '2024-11-01T00:00:00+00:00', '2024', 1, '待补录', '未核实', '', '', 1, '主线', '原表'],
                    ['event-3', '活动', 'Prequel Test', '', 'Prequel', None, 3, '', '', '2024-06-01T00:00:00+00:00', '2024', 1, '已索引·范围待核', '未核实', '', '部门箱活（banner）', 1, '活动', '原表'],
                    ['character-1-1', '个人', '皇坂 逢 / 第1章', '', '', 1, '', '', '', '2024-05-09T00:00:00+00:00', '2024', 2, '待补录', '未核实', '', '', 1, '个人', '原表'],
                ],
                '章节': [
                    ['story_id', 'episode_id', '话序', '日文标题', '原始日期', '来源表', '字幕轴入口'],
                    ['main-3-1', 'main-3-1-1', 1, '第1話', '2024-11-01T00:00:00+00:00', 'mst_main_story_section', 'main-3-1-1'],
                    ['event-3', 'event-3-1', 1, '第1話', '2024-06-01T00:00:00+00:00', 'mst_event_story_section', 'event-3-1,prequel-1-3-1'],
                    ['character-1-1', 'character-1-1-1', 1, '第1話', '2024-05-09T00:00:00+00:00', 'mst_character_story_section', 'character-1-1-1'],
                    ['character-1-1', 'character-1-1-2', 2, '第2話', '3001-01-01T00:00:00+00:00', 'mst_character_story_section', ''],
                ],
                '出场证据': [
                    ['story_id', 'episode_id', '角色ID', '剧本署名', '身份', '出场依据', '字幕轴入口', '首条操作序号', '署名台词数'],
                    ['main-3-1', 'main-3-1-1', 1, '皇坂 逢', '角色', '发言', 'main-3-1-1', 1, 5],
                    ['event-3', 'event-3-1', 1, '皇坂 逢', '角色', '发言', 'event-3-1', 1, 10],
                    ['event-3', 'event-3-1', 1, '皇坂 逢', '角色', '发言', 'prequel-1-3-1', 1, 10],
                    ['character-1-1', 'character-1-1-1', 1, '皇坂 逢', '角色', '发言', 'character-1-1-1', 1, 8],
                ],
                '熟肉资源': [
                    ['resource_id', '类型', '平台', 'BV', '分P', '原始链接', '链接状态', '视频最后核验'],
                    ['BV1xx411c7mD', '视频熟肉', 'Bilibili', 'BV1xx411c7mD', '', 'https://www.bilibili.com/video/BV1xx411c7mD', '待核验', ''],
                ],
                '资源关联': [
                    ['resource_id', 'story_id', '范围提示', '来源表头', 'UP主（原行）', '进度（原行）', '匹配依据', '来源页读取日期'],
                    ['BV1xx411c7mD', 'event-3', 'Prequel Test', '活动', 'TestUP', '已完结', '活动同名', '2026-11-26'],
                ],
                '待核清单': [['对象', '待核事项', '依据']],
            }
            snap.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            out1 = root / 'v3.xlsx'
            out_json = root / 'v3.json'
            stats = export_story_v3.export(snap, out1, export_json=out_json)
            self.assertEqual(3, stats['stories'])
            self.assertEqual(4, stats['episodes'])
            self.assertEqual(1, stats['unreleased'])
            self.assertEqual([], stats['review_episodes'])

            wb = load_workbook(out1)
            self.assertEqual(['剧情总表', '分话出场表', '分话角色明细', '熟肉链接库', '进度看板与待处理'], wb.sheetnames)
            # Ensure Prequel lines are NOT doubled (10, not 20)
            det_rows = list(wb['分话角色明细'].iter_rows(min_row=3, values_only=True))
            ev_row = next(r for r in det_rows if r[8] == 'event-3-1')
            self.assertEqual(10, ev_row[6])
            # Edit manual 中文标题 & 备注, then re-export with --preserve
            wb['剧情总表']['D3'] = '幕间一'
            wb['剧情总表']['L3'] = '人工备注'
            wb.save(out1)
            out2 = root / 'v3_preserved.xlsx'
            export_story_v3.export(snap, out2, preserve=out1)
            wb2 = load_workbook(out2)
            self.assertEqual('幕间一', wb2['剧情总表']['D3'].value)
            self.assertEqual('人工备注', wb2['剧情总表']['L3'].value)


if __name__ == '__main__':
    unittest.main()
