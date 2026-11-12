"""Shared readable labels for the per-type event workbooks."""
import re
from datetime import datetime, timedelta, timezone

from ..core.data import RARITY_MAP, ATTRIBUTE_MAP

JST = timezone(timedelta(hours=9))
# Coly.S2BShared.Enums.EventFormat in the 2.1.0 client.
FORMAT_BAR, FORMAT_BAR_SPECIAL = 3, 4
FORMAT_EXCHANGE, FORMAT_NON_MEDAL = 1, 2
FORMAT_ACCUMULATE = 6


def jst(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(JST).strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return value or ''


def plain_text(text):
    """Game rich text → readable cell text: real line breaks, no colour/size tags."""
    if not text:
        return ''
    text = str(text).replace('\\n', '\n').replace('<br>', '\n')
    text = re.sub(r'</?(color|size|b|i)(=[^>]*)?>', '', text)
    text = re.sub(r'heroine_?name', '衣都', text, flags=re.IGNORECASE)
    return text.strip()


def reward_text(rewards):
    return ' / '.join(f"{r['RewardName']} x{r['RewardCount']}" for r in rewards or [])


class Names:
    """Character and card names; records without a name keep a typed placeholder."""

    def __init__(self, tables):
        def table(name, key):
            return tables.by_id(name, key, active_only=False, required=False)
        self._characters = table('mst_character', 'CharacterId')
        self._characters.update(table('mst_character_collaboration', 'CharacterId'))
        self._cards = table('mst_character_card', 'CharacterCardId')

    def character(self, cid):
        return self._characters.get(cid, {}).get('CharacterNameJpn') or f'角色({cid})'

    def card(self, cid):
        row = self._cards.get(cid)
        if not row:
            return f'卡牌({cid})'
        rarity = RARITY_MAP.get(row.get('CardRarityCode'), '')
        attribute = ATTRIBUTE_MAP.get(row.get('CardAttributeCode'), '')
        return f"{row.get('CharacterCardName', '')}（{self.character(row.get('CharacterId'))} {rarity}{attribute}）"

    def cards(self, ids):
        return '、'.join(self.card(c) for c in ids or [])


BONUS_FIELDS = [
    ('BonusIncreaseRateByCharacterCard', '活动卡牌'),
    ('BonusIncreaseRateByR', 'R'), ('BonusIncreaseRateBySR', 'SR'), ('BonusIncreaseRateBySSR', 'SSR'),
    ('BonusIncreaseRateByCharacter', '活动角色'), ('BonusIncreaseRateByAttribute', '属性'),
    ('BonusIncreaseRateByShift', '轮班角色'),
]
LIMIT_BREAK_FIELDS = [('BonusIncreaseRatesByLimitBreakR', 'R'), ('BonusIncreaseRatesByLimitBreakSR', 'SR'),
                      ('BonusIncreaseRatesByLimitBreakSSR', 'SSR'), ('BonusIncreaseRatesByLimitBreakCR', 'CR')]


def bonus_text(row):
    """mst_event_bonus as one line; labels follow the field names (no in-game text found)."""
    if not row:
        return ''
    parts = [f'{label} +{row[key]}%' for key, label in BONUS_FIELDS if row.get(key)]
    for key, label in LIMIT_BREAK_FIELDS:
        steps = row.get(key) or []
        if any(steps):
            parts.append(f"{label}突破每阶 +{'/'.join(str(s) for s in steps)}%")
    return '；'.join(parts)


def tier_ranges(rows, key, value):
    """Merge consecutive tiers with the same reward text into (first, last, count, text)."""
    merged = []
    for row in rows:
        text = value(row)
        if merged and merged[-1][3] == text:
            first, _, count, _ = merged[-1]
            merged[-1] = (first, row[key], count + 1, text)
        else:
            merged.append((row[key], row[key], 1, text))
    return merged


def tier_label(first, last, count, unit=''):
    if count == 1:
        return f'{first:,}{unit}'
    return f'{first:,}～{last:,}{unit}（{count} 档，每档各得一次）'
