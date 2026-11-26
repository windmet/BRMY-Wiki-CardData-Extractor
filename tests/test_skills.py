import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openpyxl import load_workbook

from toolkit.core.domain_contracts import validate_domain_input
from toolkit.core.session import MasterDataSession
from toolkit.core.skill_taxonomy import PANDORA_BOX_POOL, PANDORA_BOX_TOTAL_WEIGHT, expand_sp_tag
from toolkit.domains import skills
from toolkit.generate import generate
from toolkit.resolve import MASTER_KEY, build_plan


def _make_tables(*, include_unknown=False):
    sp_effects = [
        {'SpSkillEffectId': 17, 'SkillEffect': 'erase_piece_attribute', 'SpSkillCategoryCodeList': [1]},
        {'SpSkillEffectId': 43, 'SkillEffect': 'pandora_box', 'SpSkillCategoryCodeList': [99]},
        {'SpSkillEffectId': 45, 'SkillEffect': 'hirameki_cracker', 'SpSkillCategoryCodeList': [3, 5]},
    ]
    sp_levels = [
        {'CharacterCardId': 191, 'SpSkillLevel': 1, 'SpSkillEffectId': 17, 'SkillCost': 400,
         'SkillValue1': 2, 'SkillValue2': 100, 'SkillValue3': 0, 'SkillDescription': 'ムーン属性ピースを全部消す！', 'IsActive': True},
        {'CharacterCardId': 191, 'SpSkillLevel': 5, 'SpSkillEffectId': 17, 'SkillCost': 300,
         'SkillValue1': 2, 'SkillValue2': 100, 'SkillValue3': 0, 'SkillDescription': 'ムーン属性ピースを全部消す！', 'IsActive': True},
        {'CharacterCardId': 214, 'SpSkillLevel': 1, 'SpSkillEffectId': 43, 'SkillCost': 460,
         'SkillValue1': 0, 'SkillValue2': 0, 'SkillValue3': 0, 'SkillDescription': '何が起こるかわからない！', 'IsActive': True},
        {'CharacterCardId': 214, 'SpSkillLevel': 5, 'SpSkillEffectId': 43, 'SkillCost': 300,
         'SkillValue1': 0, 'SkillValue2': 0, 'SkillValue3': 0, 'SkillDescription': '何が起こるかわからない！', 'IsActive': True},
    ]
    if include_unknown:
        sp_effects.append({'SpSkillEffectId': 999, 'SkillEffect': 'mystery_new_skill', 'SpSkillCategoryCodeList': [99]})
        sp_levels.append({'CharacterCardId': 191, 'SpSkillLevel': 1, 'SpSkillEffectId': 999, 'SkillCost': 350,
                          'SkillValue1': 1, 'SkillValue2': 0, 'SkillValue3': 0, 'SkillDescription': '新技能', 'IsActive': True})
    return {
        'mst_character': [
            {'CharacterId': 1, 'CharacterNameJpn': '皇坂逢'},
            {'CharacterId': 3, 'CharacterNameJpn': '須王芦佳'},
        ],
        'mst_character_card': [
            {'CharacterCardId': 191, 'CharacterId': 1, 'CharacterCardName': '月清卡', 'CardRarityCode': 3,
             'CardAttributeCode': 2, 'SpSkillName': '月之清扫', 'CombiCharacterId': 3, 'IsActive': True},
            {'CharacterCardId': 214, 'CharacterId': 3, 'CharacterCardName': "Here's to Aporia!", 'CardRarityCode': 3,
             'CardAttributeCode': 1, 'SpSkillName': '強い意志', 'CombiCharacterId': 1, 'IsActive': True},
        ],
        'mst_sp_skill_effect': sp_effects,
        'mst_character_card_sp_skill_level': sp_levels,
        'mst_character_card_sp_skill_with_combi': [
            {'CharacterCardId': 191, 'SpSkillEffectId': 45, 'SkillValue1': 2, 'SkillValue2': 0, 'SkillValue3': 0,
             'SkillDescription': 'ひらめきを2個作り、すぐに発動させる！', 'IsActive': True},
        ],
        'mst_auto_skill_effect': [
            {'AutoSkillEffectId': 3, 'SkillName': 'SUN SHOWER', 'IconFileName': 'sun_shower',
             'SkillDescription': 'skill_value1秒間、出現確率大アップ！'},
            {'AutoSkillEffectId': 21, 'SkillName': 'ASSIST', 'IconFileName': 'assist',
             'SkillDescription': '他のカードのオートスキルを発動させる！'},
        ],
        'mst_character_card_auto_skill_level': [
            {'CharacterCardId': 191, 'AutoSkillLevel': 1, 'AutoSkillEffectId': 3, 'SkillValue1': 10, 'IsActive': True},
            {'CharacterCardId': 214, 'AutoSkillLevel': 1, 'AutoSkillEffectId': 21, 'SkillValue1': 0, 'IsActive': True},
        ],
        'mst_leader_skill_effect': [
            {'LeaderSkillEffectId': 4, 'SkillEffect': 'AllUp', 'SkillDescription': 'チームの総合力skill_value1%UP！'},
        ],
        'mst_character_card_leader_skill': [
            {'CharacterCardId': 214, 'LeaderSkillEffectId': 4, 'SkillValue1': 25, 'IsActive': True},
        ],
        'mst_notice': [
            {'NoticeId': 223, 'StartTime': '2024-12-10T00:00:00+00:00',
             'TitleName': '「SHOWER」系オートスキルの説明文変更等について', 'FileDesc': '<p>大アップ</p>'},
        ],
    }


def _write_master(path: Path, tables: dict):
    header = {name: [0, 0] for name in tables}
    path.write_text(json.dumps([header, *tables.values()], ensure_ascii=False), encoding='utf-8')


class SkillsDomainTests(unittest.TestCase):
    def test_pandora_box_reference_weight_sums_to_108(self):
        self.assertEqual(28, len(PANDORA_BOX_POOL))
        self.assertEqual(PANDORA_BOX_TOTAL_WEIGHT, sum(weight for _, _, weight in PANDORA_BOX_POOL))

    def test_parameter_expansion_covers_full_attribute_and_random_variants(self):
        self.assertEqual('消除全部月碎片', expand_sp_tag(17, {'SkillValue1': 2, 'SkillValue2': 100}))
        self.assertEqual('消除星碎片', expand_sp_tag(17, {'SkillValue1': 3, 'SkillValue2': 9}))
        self.assertEqual('消除随机数量碎片（1～50个）', expand_sp_tag(38, {'SkillValue1': 1, 'SkillValue2': 50}))
        self.assertEqual('消除随机数量碎片（1/10/30个）', expand_sp_tag(54, {'SkillValue1': 1, 'SkillValue2': 10, 'SkillValue3': 30}))
        self.assertEqual('随机发动一种效果（专属加权池）', expand_sp_tag(43, {}))

    def test_extract_export_and_plan_skills_domain(self):
        plan = build_plan(['skills'], {MASTER_KEY: None})
        self.assertEqual([], plan['errors'])
        self.assertEqual([MASTER_KEY], [r['key'] for r in plan['resources']])

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            master = root / 'master.json'
            _write_master(master, _make_tables())
            session = MasterDataSession.open(master)
            validate_domain_input('skills', session.tables)

            data = skills.extract(session)
            self.assertEqual([], data['Issues'])
            self.assertEqual(3, data['Stats']['ActiveSpEffects'])
            self.assertEqual(1, data['Stats']['DualCategorySpEffects'])
            self.assertEqual(2, data['Stats']['ActiveAutoEffects'])

            auto_by_id = {r['effect_id']: r for r in data['AutoSummary']}
            self.assertEqual('assist.png', auto_by_id[21]['icon_file'])
            self.assertEqual('Files/Android/assist', auto_by_id[21]['asset_bundle'])

            by_card = {r['card_id']: r for r in data['CardIndex']}
            self.assertEqual('消除全部月碎片', by_card[191]['sp_expanded_tag'])
            self.assertEqual('生成闪弹并立即发动', by_card[191]['combi_subtype'])
            self.assertIn('12% UP', by_card[191]['auto_legacy_note'])
            self.assertEqual('随机发动一种效果（专属加权池）', by_card[214]['sp_expanded_tag'])
            self.assertEqual('ASSIST', by_card[214]['auto_name'])

            fake_session = SimpleNamespace(
                tables=session.tables,
                assessment=SimpleNamespace(changes=[], errors=[]),
                write_audit=lambda *a, **kw: None,
            )
            out_dir = root / 'out'
            with patch('toolkit.generate.MasterDataSession.open', return_value=fake_session):
                report = generate(['skills'], out_dir, masterdata=master)
            self.assertEqual('PASS', report['status'], report['errors'])
            wb = load_workbook(out_dir / 'wiki_output' / 'skills_catalog.xlsx')
            self.assertEqual(['SP技能分类', '自动技能分类', '卡牌技能标签索引', '公告与漂移核对', '客户端机制附注'], wb.sheetnames)

    def test_unmapped_effect_id_triggers_drift_issue_and_warning(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            master = root / 'master.json'
            _write_master(master, _make_tables(include_unknown=True))
            session = MasterDataSession.open(master)
            fake_session = SimpleNamespace(
                tables=session.tables,
                assessment=SimpleNamespace(changes=[], errors=[]),
                write_audit=lambda *a, **kw: None,
            )
            out_dir = root / 'out'
            with patch('toolkit.generate.MasterDataSession.open', return_value=fake_session):
                report = generate(['skills'], out_dir, masterdata=master)
            self.assertEqual('PASS_WITH_WARNINGS', report['status'])
            self.assertTrue(any('未收录' in str(w) for w in report['warnings']))


if __name__ == '__main__':
    unittest.main()
