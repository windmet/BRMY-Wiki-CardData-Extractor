"""Required identities for new archives; empty tables remain valid input."""

CONTRACTS = {
    'groove': {
        'mst_item': ('ItemId', 'ItemName', 'ItemDescription1'),
        'mst_item_groove_stamina_recover': ('ItemId', 'RecoveryAmount'),
        'mst_groove_constant': ('ConstantKey', 'RelationLotteryRateDenominator', 'WishListItemLotteryRateDenominator', 'ChanceBoxPinCustomItemLotteryRateMax', 'ChanceBoxWishListItemMaxRate', 'ConsumeGrooveStaminaRecoveryCrystal'),
        'mst_groove_wish_list_item': ('ItemId', 'LotteryRate', 'ReleaseDateTime', 'EndTime', 'SortOrder'),
        'mst_groove_wish_list_lottery_rate_level': ('GrooveWishListLotteryRateLevelId', 'BorderLotteryRate', 'Text'),
        'mst_groove_chance_box_color': ('ChanceBoxItemRarity', 'ChanceBoxColor', 'LotteryRate'),
        'mst_groove_play_quality_reward_rate': ('PlayQualityRewardRateId', 'Rainbow', 'Gold', 'Silver', 'Copper'),
        'mst_character_card': ('CharacterId',),
        'mst_character': ('CharacterId', 'CharacterNameJpn'),
        'mst_music': ('MusicId', 'DisplayName'),
        'mst_groove_music': ('MusicId', 'GrooveMusicType', 'ReleaseDateTime', 'EndTime', 'SortOrder'),
        'mst_groove_music_bonus_runner': ('MusicId', 'CharacterId', 'GrooveRunnerBonusLevel'),
        'mst_groove_card_level_exp': ('GrooveRunnerStatus', 'CardLevelExpRunner1', 'CardLevelExpRunner2', 'CardLevelExpRunner3', 'CardLevelExpRunner4'),
        'mst_groove_runner_bonus': ('GrooveRunnerBonusLevel', 'CardLevelExpIncreaseCount', 'ChanceBoxLotteryIncreaseCount'),
        'mst_groove_music_stage': ('MusicId', 'GrooveMusicStageType', 'GrooveMusicStageDifficulty', 'RelationLotteryRateIncreaseRate'),
        'mst_groove_relation': ('GrooveRelationId', 'CharacterIds', 'LotteryRate', 'RelationText'),
    },
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
