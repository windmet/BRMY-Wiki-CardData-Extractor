"""Required identities for new archives; empty tables remain valid input."""

CONTRACTS = {
    'ojt': {
        'mst_event_c': ('EventId',),
        'mst_event_ojt_chart': ('EventId', 'ChartFileName'),
        'mst_event_ojt_shift': ('EventId', 'OjtShiftId'),
        'mst_event_ojt_puzzle_stage': ('OjtShiftId', 'OjtPhase', 'PuzzleMapId'),
        'mst_event_ojt_terminal_character_text': ('OjtShiftId',),
        'mst_event_ojt_training_reward': ('OjtShiftId', 'OjtPhase', 'DirectRewardGroupId'),
        'mst_event_ojt_prize_box': ('OjtShiftId', 'PrizeBoxNo', 'PrizeBoxRewardId', 'PrizeBoxRewardRandomId'),
        'mst_event_ojt_prize_box_reward': ('PrizeBoxRewardId', 'RewardTypeCode', 'RewardTargetId'),
        'mst_event_ojt_prize_box_reward_random': ('PrizeBoxRewardRandomId', 'RewardTypeCode', 'RewardTargetId'),
    },
    'birthday_archive': {
        name: ('CharacterId', 'Year') for name in (
            'mst_character_birthday', 'mst_character_birthday_campaign_page',
            'mst_character_birthday_login_bonus_page', 'mst_character_birthday_login_bonus_sequence',
            'mst_character_birthday_mini_game', 'mst_character_birthday_mini_game_text')
    },
    'home_voice_duo': {
        'mst_character_home_voice_duo': ('CharacterId', 'HomeVoiceNo', 'PartnerCharacterId', 'PartnerHomeVoiceNo'),
        'mst_home_voice': ('HomeVoiceTypeCode', 'HomeVoiceCategory', 'HomeVoiceTargetId', 'HomeVoiceNo', 'VoiceCueName'),
    },
    'story_catalog': {
        'mst_main_story_section': ('MainStoryThreadNo', 'MainStoryChapterNo', 'MainStorySectionNo'),
        'mst_character_story_section': ('CharacterId', 'CharacterStoryChapterNo', 'CharacterStorySectionNo'),
        'mst_character_card_story_section': ('CharacterCardId', 'CharacterCardStorySectionNo'),
        'mst_event_story_section': ('EventId', 'EventStorySectionNo'),
        'mst_login_story_section': ('LoginStoryId', 'LoginStorySectionNo'),
        'mst_puzzle_story': ('StoryTypeCode', 'StoryTargetBaseId', 'StoryTargetChapterId', 'StoryTargetSectionNo', 'PuzzleStoryNo'),
        'mst_main_story_from_other_story_type_section': ('MainStoryThreadNo', 'MainStoryFromOtherStoryTypeChapterNo', 'MainStoryFromOtherStoryTypeSectionNo'),
    },
    'collections': {
        'mst_costume_model': ('CostumeModelId',), 'mst_costume_mini': ('CostumeMiniId',),
        'mst_honor': ('HonorId',), 'mst_pin': ('PinId',),
        'mst_home_background': ('BackgroundId',), 'mst_item': ('ItemId',),
    },
}


def validate_domain_input(domain, tables):
    errors = []
    for table, fields in CONTRACTS.get(domain, {}).items():
        if table not in tables.names:
            errors.append(f'{table}: required table is missing')
            continue
        for index, row in enumerate(tables.rows(table)):
            if not isinstance(row, dict):
                errors.append(f'{table}[{index}]: record is not an object')
                continue
            if row.get('IsActive', True) is False:
                continue
            missing = [field for field in fields if field not in row or row[field] is None]
            if missing:
                errors.append(f"{table}[{index}]: missing required fields {', '.join(missing)}")
    if errors:
        raise ValueError(f'{domain} input contract failed ({len(errors)}): ' + '; '.join(errors[:20]))
