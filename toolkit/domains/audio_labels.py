"""Speaker identities for non-card audio, separate from binary parsing."""
from pathlib import Path
import re


def voice_category(cue, category):
    for prefix, label in [('vo_home_', '主页'),
                          ('vo_campaign_', '活动'), ('spin_voice_', 'Spin'), ('vo_puzzle_', '消消乐'),
                          ('vo_training_', '培养'), ('vo_costume_', '换装'),
                          ('vo_oneshot_', '短句'), ('vo_select', '选择'),
                          ('vo_coly_', 'coly开场'), ('vo_title_', '标题'),
                          ('vo_dl_', '下载中'), ('vo_profile_', '档案')]:
        if cue.startswith(prefix):
            return label
    return {'character_voice': '角色语音', 'story_voice': '剧情语音',
            'bgm': '背景音乐', 'sound_effect': '音效', 'music_package': '音乐包'}.get(category, '其他')


class AudioLabels:
    def __init__(self, tables=None):
        # Import lazily: home_voices consumes the binary parser in audio.py.
        from .home_voices import STEM_TO_CHARACTER_ID
        from .system_voices import PACKAGE_BY_TARGET
        self.stems = STEM_TO_CHARACTER_ID
        self.system_packages = {name: cid for cid, name in PACKAGE_BY_TARGET.items()}
        self.characters = tables.by_id('mst_character', 'CharacterId', active_only=False, required=False) if tables else {}
        if tables:
            self.characters.update(tables.by_id('mst_character_collaboration', 'CharacterId', active_only=False, required=False))

    def name(self, cid):
        return self.characters.get(cid, {}).get('CharacterNameJpn') or f'角色({cid})'

    def label(self, filename, cue, *, stable=True, match_status='matched_by_acb_utf'):
        filename = Path(filename).name.lower()
        result = {'SpeakerCharacterIds': [], 'Speaker': '', 'SpeakerBasis': '', 'Status': '正常', 'Note': ''}
        reasons = []
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
               speakers):
            reasons.append('缺少角色名称资料')
        if not stable:
            reasons.append('资源读取不稳定')
        if match_status != 'matched_by_acb_utf':
            reasons.append('文本来自标题回退匹配，语音标识需核对')
        if reasons:
            result.update(Status='待核对', Note='；'.join(reasons))
        return result
