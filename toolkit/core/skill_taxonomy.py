"""Canonical Break My Case skill taxonomy (SP, Auto, Leader) and parameter tag expansion.

Masterdata tables supply live EffectIds, category codes, icons and per-card parameters.
Client-hardcoded mechanics (PandoraBox 28-entry weights, ShuffleW/ShuffleS avoidMatch)
are kept separately with explicit client-version provenance so they are never confused
with masterdata-derived values.
"""
from __future__ import annotations

from ..core.data import ATTRIBUTE_MAP, PIECE_MAP

# SpSkillCategoryCode (client 2.1.0 dump.cs)
SP_CATEGORIES: dict[int, tuple[str, str]] = {
    1: ('消除', 'Erase'),
    2: ('转换', 'Conversion'),
    3: ('生成', 'Create'),
    4: ('恢复', 'Recovery'),
    5: ('机关', 'Gimmick'),
    99: ('其他', 'Other'),
}

# Active SpSkillEffectId -> (SpSkillType enum, Wiki Chinese subtype label, mechanism note)
SP_EFFECTS: dict[int, tuple[str, str, str]] = {
    3: ('ChangePieceRandom', '生成指定颜色碎片', '官方大类为「转换」；可按颜色展开'),
    6: ('EraseCoin', '消除全部金币碎片', ''),
    7: ('MakeCombo', '生成连击球', ''),
    8: ('ScoreGet', '增加分数', ''),
    13: ('ContinueCombo', '增加 Bonus Combo', ''),
    14: ('GetLife', '恢复生命值', ''),
    15: ('ErasePiece', '消除指定颜色碎片', '可按颜色展开'),
    17: ('ErasePieceAttribute', '消除指定属性碎片（日／月／星）', '可按属性及是否全部消除展开'),
    18: ('ChangePiece', '将指定颜色的碎片全部转为另一颜色', '定向转色，可按原色→目标色展开'),
    19: ('PieceToCoin', '生成金币碎片', '官方大类为「转换」'),
    20: ('ErasePieceRandom', '随机消除碎片（指定数量或全部）', '固定数量或全消'),
    21: ('RecoverShock', '治愈麻痹碎片', '官方大类为「恢复＋机关」'),
    22: ('RecoverSleep', '唤醒睡眠碎片', '官方大类为「恢复＋机关」'),
    23: ('EraseGlass', '打破玻璃', '仅玻璃；打破三种板见 ID 47'),
    24: ('MakeBomb', '生成炸弹', '炸弹本体（非炸弹碎片 ID 36）'),
    27: ('MakeArrowRandom', '生成闪弹（方向随机）', '闪弹本体（非闪弹碎片 ID 35）'),
    29: ('ShuffleS', '强力打乱碎片', 'avoidMatch=false，重排后可能直接形成匹配并消除'),
    30: ('ShuffleW', '打乱碎片', 'avoidMatch=true，重排时尽量避开即时匹配'),
    31: ('AutoSkillActivation', '发动队员的自动技能', '主动 SP 触发队友 Auto 技能'),
    32: ('ChangeHiramekiPiece', '将指定颜色碎片转为闪弹碎片', '官方大类为「转换」'),
    34: ('MakeSpecialPiece', '生成特殊碎片', '官方大类为「转换」'),
    35: ('MakeHiramekiPiece', '生成闪弹碎片', '仅生成碎片，不立即发动'),
    36: ('MakeBombPiece', '生成炸弹碎片', '仅生成碎片，不立即爆炸'),
    37: ('MakeRainbowPiece', '生成彩蝶', '官方大类为「生成」'),
    38: ('ErasePieceRandomRange', '消除随机数量的碎片（范围内取值）', '如 1～50 个'),
    39: ('ErasePieceRandomTricolor', '消除指定三色碎片（合计指定数量）', ''),
    40: ('ErasePieceRandomCross', '以十字形消除碎片', ''),
    41: ('ErasePieceRandomHorizontal', '以行消除碎片', ''),
    42: ('ErasePieceRandomVertical', '以列消除碎片', ''),
    43: ('PandoraBox', '随机发动一种效果（专属加权池）', '卡 214 专属 28 项加权池，不混入普通功能标签'),
    44: ('BombCracker', '生成炸弹并立即爆炸', ''),
    45: ('HiramekiCracker', '生成闪弹并立即发动', '对象为闪弹本体而非闪弹碎片'),
    46: ('ErasePieceRandomColor', '消除随机颜色的碎片', '随机决定消除的颜色'),
    47: ('EraseBoard', '打破玻璃、胶合板、金属板', '覆盖玻璃及更硬挡板'),
    48: ('MakeSpecialPieceContact', '在特殊碎片旁生成特殊碎片', '依赖盘面已有特殊碎片'),
    49: ('MakeHiramekiPieceContact', '在特殊碎片旁生成闪弹碎片', '依赖盘面已有特殊碎片'),
    50: ('MakeBombPieceContact', '在特殊碎片旁生成炸弹碎片', '依赖盘面已有特殊碎片'),
    51: ('MakeSpecialPieceSideBySide', '成对生成相邻的特殊碎片', '直接生成相邻一组'),
    52: ('MakeHiramekiPieceSideBySide', '成对生成相邻的闪弹碎片', '直接生成相邻一组'),
    53: ('MakeBombPieceSideBySide', '成对生成相邻的炸弹碎片', '直接生成相邻一组'),
    54: ('ErasePieceAlternative', '消除随机数量的碎片（从指定数值中选取）', '如 1/10/30 或 1/100 个'),
    55: ('ErasePieceFixedX', '在固定位置以 X 形消除碎片', ''),
    56: ('RecoverAbnormalCondition', '治愈异常状态碎片', '官方大类仅为「恢复」'),
    59: ('AutoplayRun', '限时自动组成 Unit', '官方大类为「消除」'),
}

# Active AutoSkillEffectId -> (Chinese summary, mechanism note)
AUTO_EFFECTS: dict[int, tuple[str, str]] = {
    1: ('限时提高获得分数', ''),
    2: ('限时提高连击加成', ''),
    3: ('限时提高日属性（红/桃）碎片出现权重', '公告 #223：实际效果因关卡掉落权重而异'),
    4: ('限时提高月属性（空/青）碎片出现权重', '公告 #223：实际效果因关卡掉落权重而异'),
    5: ('限时提高星属性（黄/绿）碎片出现权重', '公告 #223：实际效果因关卡掉落权重而异'),
    12: ('限时降低日属性（红/桃）碎片出现权重', ''),
    13: ('限时降低月属性（空/青）碎片出现权重', ''),
    14: ('限时降低星属性（黄/绿）碎片出现权重', ''),
    15: ('限时使生成的连击球等级提升 1 阶', ''),
    16: ('复制其他卡牌的自动技能并发动', '与 ASSIST（ID 21）不同，本项为复制后由自身发动'),
    17: ('限时将匹配的 Unit 转为日属性', ''),
    18: ('限时将匹配的 Unit 转为月属性', ''),
    19: ('限时将匹配的 Unit 转为星属性', ''),
    20: ('限时每次消除 Unit 回复 SP', ''),
    21: ('使其他卡牌发动自动技能', '图标 assist.png，资源包 Files/Android/assist'),
}

# Active LeaderSkillEffectId -> Chinese label
LEADER_EFFECTS: dict[int, str] = {
    1: '全队 Aura 提升',
    2: '全队 Visual 提升',
    3: '全队 Charisma 提升',
    4: '全队综合力提升',
    17: '指定部门综合力提升',
    18: '指定部门 Aura 提升',
    19: '指定部门 Visual 提升',
    20: '指定部门 Charisma 提升',
    21: '指定角色综合力提升',
}

# Notice #223 (2024-12-10, v1.3.2): SHOWER wording change reference
SHOWER_LEGACY_TABLE: tuple[tuple[str, str, str], ...] = (
    ('8% UP', '小アップ', '公告 #223（2024-12-10，v1.3.2）'),
    ('10% UP', '中アップ', '公告 #223（2024-12-10，v1.3.2）'),
    ('12% UP', '大アップ', '公告 #223（2024-12-10，v1.3.2）'),
    ('14% UP', '特大アップ', '公告 #223（2024-12-10，v1.3.2）'),
    ('20% UP', '超特大アップ', '公告 #223（2024-12-10，v1.3.2）'),
)

# Client 2.1.0 libil2cpp.so SpSkillPandoraBox hardcoded pool (total weight = 108).
# Kept strictly as reference metadata; never inferred from master_data.
PANDORA_BOX_CLIENT_VERSION = '2.1.0'
PANDORA_BOX_TOTAL_WEIGHT = 108
PANDORA_BOX_POOL: tuple[tuple[str, str, int], ...] = (
    ('CreateBombPiece5', '生成炸弹棋子 5 个（效果 ID 36）', 3),
    ('CreateBombPiece2', '生成炸弹棋子 2 个（效果 ID 36）', 3),
    ('CreateHiramekiPiece5', '生成灵感棋子 5 个（效果 ID 35）', 3),
    ('CreateHiramekiPiece2', '生成灵感棋子 2 个（效果 ID 35）', 3),
    ('CreateRainbowPiece1', '生成彩蝶 1 个（效果 ID 37）', 7),
    ('CreateSpecialPiece3', '生成特殊碎片 3 个（效果 ID 34）', 6),
    ('CreateSpecialPiece6', '生成特殊碎片 6 个（效果 ID 34）', 2),
    ('CreateComboPieceSSR4', '生成 SSR 连击球 4 个（效果 ID 7）', 4),
    ('CreateComboPieceSR4', '生成 SR 连击球 4 个（效果 ID 7）', 4),
    ('CreateComboPieceR3', '生成 R 连击球 3 个（效果 ID 7）', 6),
    ('CreateCoinPieceAll', '将棋子变为金币，目标数 100（效果 ID 19）', 3),
    ('ErasePieceRandom10', '随机消除 10 个碎片（效果 ID 20）', 8),
    ('ErasePieceRandom30', '随机消除 30 个碎片（效果 ID 20）', 8),
    ('ErasePieceRandom100', '随机消除 100 个碎片（效果 ID 20）', 3),
    ('CreateBomb2', '生成炸弹 2 个（效果 ID 24）', 3),
    ('CreateBomb4', '生成炸弹 4 个（效果 ID 24）', 3),
    ('MakeArrowRandom2', '生成随机方向闪弹 2 个（效果 ID 27）', 2),
    ('MakeArrowRandom4', '生成随机方向闪弹 4 个（效果 ID 27）', 4),
    ('ShuffleS', '强力打乱碎片 ShuffleS（效果 ID 29）', 6),
    ('EraseHorizontal1', '横向消除 1 行（效果 ID 41）', 3),
    ('EraseHorizontal3', '横向消除 3 行（效果 ID 41）', 3),
    ('EraseVertical1', '纵向消除 1 列（效果 ID 42）', 3),
    ('EraseVertical3', '纵向消除 3 列（效果 ID 42）', 3),
    ('EraseCross1', '十字消除 1 处（效果 ID 40）', 6),
    ('EraseCross2', '十字消除 2 处（效果 ID 40）', 3),
    ('CreateGrass6', '生成草丛 6 个（干扰效果）', 2),
    ('Sleep10', '将 10 个棋子变为睡眠状态（干扰效果）', 2),
    ('Shock15', '将 15 个棋子变为感电状态（干扰效果）', 2),
)

PIECE_COLOR_ZH = {
    1: '红色',
    2: '桃色',
    3: '空色',
    4: '青色',
    5: '黄色',
    6: '绿色',
}
ATTR_ZH = {1: '日', 2: '月', 3: '星'}


def format_sp_categories(code_list) -> tuple[str, str, str]:
    """Return (zh_joined, id_joined, enum_joined) from SpSkillCategoryCodeList."""
    codes = list(code_list or ())
    zh = '＋'.join(SP_CATEGORIES.get(c, (f'未知({c})', f'Unknown({c})'))[0] for c in codes)
    ids = ' / '.join(str(c) for c in codes)
    enums = ' / '.join(SP_CATEGORIES.get(c, (f'未知({c})', f'Unknown({c})'))[1] for c in codes)
    return zh, ids, enums


def expand_sp_tag(effect_id: int | None, row: dict) -> str:
    """Derive a parameter-expanded player-facing Wiki tag from SpSkillEffectId + SkillValue1..3."""
    if effect_id is None:
        return ''
    base = SP_EFFECTS.get(effect_id)
    fallback = base[1] if base else f'未收录SP效果({effect_id})'
    v1 = row.get('SkillValue1') or 0
    v2 = row.get('SkillValue2') or 0
    v3 = row.get('SkillValue3') or 0
    desc = str(row.get('SkillDescription') or '')

    if effect_id == 3 and v2 in PIECE_COLOR_ZH:
        return f'生成{PIECE_COLOR_ZH[v2]}碎片'
    if effect_id == 15 and v1 in PIECE_COLOR_ZH:
        if v2 >= 99 or '全部' in desc or 'すべて' in desc or '全て' in desc:
            return f'消除全部{PIECE_COLOR_ZH[v1]}碎片'
        return f'消除{PIECE_COLOR_ZH[v1]}碎片'
    if effect_id == 17 and v1 in ATTR_ZH:
        if v2 >= 99 or '全部' in desc or 'すべて' in desc or '全て' in desc:
            return f'消除全部{ATTR_ZH[v1]}碎片'
        return f'消除{ATTR_ZH[v1]}碎片'
    if effect_id == 18 and v2 in PIECE_COLOR_ZH and v3 in PIECE_COLOR_ZH:
        return f'将全部{PIECE_COLOR_ZH[v2]}碎片转为{PIECE_COLOR_ZH[v3]}碎片'
    if effect_id == 20:
        if v1 >= 99 or '全部' in desc or 'すべて' in desc or '全て' in desc:
            return '消除全部碎片'
        return '随机消除碎片（指定数量）'
    if effect_id == 32 and v2 in PIECE_COLOR_ZH:
        return f'将{PIECE_COLOR_ZH[v2]}碎片转为闪弹碎片'
    if effect_id == 38 and v2:
        return f'消除随机数量碎片（{v1}～{v2}个）'
    if effect_id == 39:
        colors = [PIECE_COLOR_ZH[v] for v in (v1, v2, v3) if v in PIECE_COLOR_ZH]
        if colors:
            return f"消除{'/'.join(colors)}三色碎片"
    if effect_id == 54:
        choices = [str(v) for v in (v1, v2, v3) if v]
        if choices:
            return f"消除随机数量碎片（{'/'.join(choices)}个）"
    return fallback


def legacy_percentage_note(desc: str) -> str:
    """Return legacy Notice #223 percentage note if desc contains a SHOWER tier keyword."""
    if not desc:
        return ''
    for old_label, new_label, _ in reversed(SHOWER_LEGACY_TABLE):
        if new_label in desc:
            return f'旧版表记：{old_label}（现行：{new_label}）'
    return ''
