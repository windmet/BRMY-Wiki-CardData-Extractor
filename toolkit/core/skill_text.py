"""Skill description rendering that mirrors the client's SkillDescriptionParser.

Reconstructed from libil2cpp 2.1.0 (``Manager.Utility.SkillDescriptionParser.Parse``,
RVA 0x7F35F24) with emoji off, i.e. the text the client shows instead of sprites:

1. ``<name>1``..``<name>6`` become a label of ``SkillValueN`` for skill, piece,
   attribute, group and character placeholders, in that order;
2. special piece names (``Util.SpecialPieceNameToTextId``) become ``mst_text``;
3. ``combo:{x}`` and ``text:{x}`` are unwrapped; like the client, every match is
   replaced with the first match's ``x``;
4. ``strength_value1``..``6`` become ``mst_text`` 100134..100138.

Labels the client cannot resolve become empty strings, as in the client, and are
collected in ``unresolved``. ``wiki_text`` then applies the wiki's own wording.
"""
from __future__ import annotations

import re

SPECIAL_PIECE_TEXT_IDS = {
    **{f"combopiece_{n}": 100117 + n for n in range(1, 4)},
    **{f"bombpiece_{n}": 100120 + n for n in range(1, 7)},
    **{f"hiramekipiece_{n}": 100126 + n for n in range(1, 7)},
    "rainbowpiece": 100133,
}
ATTRIBUTE_TEXT_IDS = {0: 100114, 1: 100115, 2: 100116, 3: 100117}
GROUP_TEXT_IDS = {1: 100014, 2: 100015, 3: 100016, 4: 100017, 5: 100018, 6: 100019}
STRENGTH_TEXT_IDS = {1: 100134, 2: 100135, 3: 100136, 4: 100137, 5: 100138}

# Wiki wording for TextMeshPro sprites the client draws as icons.
SPRITE_WORDS = (
    ("<sprite name=piece_1><sprite name=piece_2>", "サンピース"),
    ("<sprite name=piece_3><sprite name=piece_4>", "ムーンピース"),
    ("<sprite name=piece_5><sprite name=piece_6>", "スターピース"),
    ("サン属性ピースサンピース", "サンピース"),
    ("ムーン属性ピースムーンピース", "ムーンピース"),
    ("スター属性ピーススターピース", "スターピース"),
    ("サン属性ピース", "サンピース"),
    ("ムーン属性ピース", "ムーンピース"),
    ("スター属性ピース", "スターピース"),
    ("属性ピース", "ピース"),
)


def skill_values(row):
    """SkillValue1..6 as the client's uint arguments (missing values are 0)."""
    return [row.get(f"SkillValue{index}") or 0 for index in range(1, 7)]


def _replace_match_pattern(description, pattern):
    match = re.search(pattern, description)
    if not match:
        return description
    return re.sub(pattern, lambda _: match.group(1), description)


class SkillTextRenderer:
    def __init__(self, tables, piece_labels=None):
        self.texts = {row["Id"]: row.get("Text", "") for row in tables.rows("mst_text") if "Id" in row}
        self.pieces = {
            row["PieceInfoId"]: row.get("Name", "")
            for row in tables.rows("mst_piece_info") if "PieceInfoId" in row
        }
        self.characters = {
            row["CharacterId"]: row.get("CharacterNameJpn", "")
            for row in tables.rows("mst_character") if "CharacterId" in row
        }
        self.piece_labels = piece_labels or {}
        self.unresolved = set()

    def _label(self, kind, value, label):
        if not label:
            self.unresolved.add((kind, value))
        return label or ""

    def _text_label(self, kind, ids, value):
        return self._label(kind, value, self.texts.get(ids.get(value)))

    def parse(self, description, values):
        """Return the client's emoji-free text for one description template."""
        if not description:
            return ""
        labelers = (
            ("skill_value", str),
            ("piece_value", lambda v: self._label(
                "piece_value", v, self.piece_labels.get(v) or self.pieces.get(v))),
            ("attribute_value", lambda v: self._text_label("attribute_value", ATTRIBUTE_TEXT_IDS, v)),
            ("group_value", lambda v: self._text_label("group_value", GROUP_TEXT_IDS, v)),
            ("character_value", lambda v: self._label("character_value", v, self.characters.get(v))),
        )
        for placeholder, label in labelers:
            for index, value in enumerate(values, start=1):
                token = f"{placeholder}{index}"
                if token in description:
                    description = description.replace(token, label(value))
        for name, text_id in SPECIAL_PIECE_TEXT_IDS.items():
            if name in description:
                description = description.replace(name, self._label(name, text_id, self.texts.get(text_id)))
        description = _replace_match_pattern(description, r"combo:{(.*?)}")
        description = _replace_match_pattern(description, r"text:{(.*?)}")
        for index, value in enumerate(values, start=1):
            token = f"strength_value{index}"
            if token in description:
                description = description.replace(
                    token, self._text_label("strength_value", STRENGTH_TEXT_IDS, value)
                )
        return description

    def wiki_text(self, description, row):
        text = self.parse(description, skill_values(row))
        for old, new in SPRITE_WORDS:
            text = text.replace(old, new)
        return text
