"""Masterdata identities for the audio inventory, separate from binary parsing."""
from collections import defaultdict
from pathlib import Path
import re


def voice_category(cue, category):
    for prefix, label in [('card_vo_home_', '卡牌主页'), ('card_vo_skill_combi', '卡牌协作'),
                          ('card_vo_skill', '卡牌技能'), ('card_vo_gacha', '卡牌抽卡'), ('vo_home_', '主页'),
                          ('vo_campaign_', '活动'), ('spin_voice_', 'Spin'), ('vo_puzzle_', '消消乐'),
                          ('vo_training_', '培养'), ('vo_costume_', '换装'),
                          ('vo_oneshot_', '短句'), ('vo_select', '选择'),
                          ('vo_coly_', 'coly开场'), ('vo_title_', '标题'),
                          ('vo_dl_', '下载中'), ('vo_profile_', '档案')]:
        if cue.startswith(prefix):
            return label
    return {'card_voice': '卡牌语音', 'character_voice': '角色语音', 'story_voice': '剧情语音',
            'bgm': '背景音乐', 'sound_effect': '音效', 'music_package': '音乐包'}.get(category, '其他')


class AudioLabels:
    def __init__(self, tables=None):
        # Import lazily: home_voices consumes the binary parser in audio.py.
        from .home_voices import STEM_TO_CHARACTER_ID
        from .system_voices import PACKAGE_BY_TARGET
        self.stems = STEM_TO_CHARACTER_ID
        self.system_packages = {name: cid for cid, name in PACKAGE_BY_TARGET.items()}
        self.has_masterdata = tables is not None
        self.cards = tables.by_id('mst_character_card', 'CharacterCardId', active_only=False, required=False) if tables else {}
        self.characters = tables.by_id('mst_character', 'CharacterId', active_only=False, required=False) if tables else {}
        if tables:
            self.characters.update(tables.by_id('mst_character_collaboration', 'CharacterId', active_only=False, required=False))
        self.additional, self.home = defaultdict(list), defaultdict(list)
        if tables:
            for row in tables.rows('mst_character_card_multi_character', active_only=True):
                self.additional[row.get('CharacterCardId')].append(row.get('CharacterId'))
            for row in tables.rows('mst_home_voice', active_only=True):
                if row.get('HomeVoiceTypeCode') == 2:
                    self.home[(row.get('HomeVoiceTargetId'), row.get('VoiceCueName'))].append(row)

    def name(self, cid):
        return self.characters.get(cid, {}).get('CharacterNameJpn') or f'角色({cid})'

    def card(self, card_id):
        raw = self.cards.get(card_id, {})
        ids = list(dict.fromkeys(i for i in [raw.get('CharacterId'), *self.additional[card_id]] if i))
        return {'CharacterCardId': card_id, 'CharacterCardName': raw.get('CharacterCardName', ''),
                'CardCharacterIds': ids, 'CardCharacterNames': '、'.join(self.name(i) for i in ids)}

    def label(self, filename, cue, *, stable=True, match_status='matched_by_acb_utf', clip_count=None):
        filename = Path(filename).name.lower()
        result = {'CharacterCardId': None, 'CharacterCardName': '', 'CardCharacterIds': [],
                  'CardCharacterNames': '', 'SpeakerCharacterIds': [], 'Speaker': '',
                  'SpeakerBasis': '', 'Status': '正常', 'Note': ''}
        reasons = []
        card_match = re.fullmatch(r'voice_(\d+)\.acb', filename)
        if card_match:
            card_id = int(card_match[1])
            result.update(self.card(card_id))
            raw = self.cards.get(card_id)
            if not raw:
                reasons.append('找不到对应卡牌资料' if self.has_masterdata else '未提供 masterdata，无法关联卡牌名和角色')
            else:
                ids = result['CardCharacterIds']
                if not raw.get('CharacterCardName'):
                    reasons.append('卡牌资料没有卡牌名')
                skill = re.fullmatch(r'card_vo_skill_(\d+)', cue)
                homes = self.home.get((card_id, cue), [])
                if clip_count is not None and clip_count > 1:
                    reasons.append('多段语音需逐段确认说话人，不能直接使用卡牌角色')
                elif cue == 'card_vo_skill_combi':
                    partner = raw.get('CombiCharacterId')
                    if clip_count == 1 and partner:
                        result.update(SpeakerCharacterIds=[partner], SpeakerBasis='单段协作语音对应卡牌 CombiCharacterId')
                    else:
                        reasons.append('协作语音段数或协作角色尚未确认')
                elif skill:
                    cid = int(skill[1])
                    if cid in ids or cid == raw.get('CombiCharacterId'):
                        result.update(SpeakerCharacterIds=[cid], SpeakerBasis='技能语音标识中的角色编号')
                    else:
                        reasons.append('技能语音角色编号与卡牌角色资料不一致')
                elif len(homes) == 1 and homes[0].get('MotionCharacterId') in ids:
                    result.update(SpeakerCharacterIds=[homes[0]['MotionCharacterId']],
                                  SpeakerBasis='卡牌主页配置 MotionCharacterId')
                elif len(homes) > 1:
                    reasons.append('卡牌主页语音存在多条对应配置')
                elif len(ids) == 1 and (cue in ('card_vo_skill', 'card_vo_gacha') or re.fullmatch(r'card_vo_home_\d+', cue)):
                    result.update(SpeakerCharacterIds=ids, SpeakerBasis='单角色卡牌的主页 / 技能语音')
                else:
                    reasons.append('尚无可确认逐句说话人的关联')
        else:
            character_match = re.fullmatch(r'voice_([a-z]+)_(general|[123]|campaign)\.acb', filename)
            cid = self.system_packages.get(filename)
            if character_match:
                cid = self.stems.get(character_match[1], cid)
            boss = re.fullmatch(r'voice_boss_([a-z]+)\.acb', filename)
            if boss:
                cid = self.stems.get(boss[1])
            if filename.startswith('puzzle_gimmick_general_se'):
                boss_cue = re.fullmatch(r'boss_([a-z]+)_(?:b_start|moya_make|vo_\d+)', cue)
                if boss_cue:
                    cid = self.stems.get(boss_cue[1])
            local = re.fullmatch(r'vo_(?:coly|dl|title|profile_[123])_(\d+)', cue)
            if filename == 'local_voice.acb' and local and 1 <= int(local[1]) <= 21:
                # 2.1.0 Util.GetLocalVoiceFileName(localVoiceType, CharacterId), RVA 0x77CB8E8.
                cid = int(local[1])
                result['SpeakerBasis'] = '客户端 GetLocalVoiceFileName 的 CharacterId 后缀规则'
            if cid:
                result['SpeakerCharacterIds'] = [cid]
                if not result['SpeakerBasis']:
                    result['SpeakerBasis'] = '已确认的角色语音包 / 角色名标识映射'
            else:
                reasons.append('资源文件未建立说话人映射；剧情等多人资源需逐句关联')
        speakers = result['SpeakerCharacterIds']
        result['Speaker'] = '、'.join(self.name(i) for i in speakers) or '待核对'
        if any(not self.characters.get(i, {}).get('CharacterNameJpn') for i in
               set(speakers + result['CardCharacterIds'])):
            reasons.append('缺少角色名称资料')
        if not stable:
            reasons.append('资源读取不稳定')
        if match_status != 'matched_by_acb_utf':
            reasons.append('文本来自标题回退匹配，语音标识需核对')
        if reasons:
            result.update(Status='待核对', Note='；'.join(reasons))
        return result
