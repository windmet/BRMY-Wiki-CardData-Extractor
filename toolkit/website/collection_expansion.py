"""Export ONLY new native facets for the existing canonical pipeline.

Offline audit CLI, not a replacement for Puzzle Core/Bartending/Items. Ordinary
stage challenges, menu semantics and resource URLs remain owned by their current
production domains. Optional bundle hashes bind this run to a canonical snapshot.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from pathlib import Path
from .collection_support import MasterData, stage_key, verify_bundle, write_json

# Verified against Toolkit core/rewards.py; pin is NOT spin_sticky_note.
TARGETS = {
    1: ('card','mst_character_card','CharacterCardId','CharacterCardName',None),
    2: ('item','mst_item','ItemId','ItemName','ItemFileName'),
    3: ('home_background','mst_home_background','BackgroundId','DisplayName','IconFileName'),
    6: ('honor','mst_honor','HonorId','HonorName','HonorFileName'),
    7: ('pin','mst_pin','PinId','PinName','PinFileName'),
    101: ('ingredient','mst_event_ingredient','IngredientId','IngredientName','IngredientFileName'),
}
COLLECTION_CODES = (3, 6, 7)
RANKS = ('SS','S','A','B','C','D','E')


def extract(md: MasterData):
    targets = {code: md.by_id(spec[1], spec[2]) for code, spec in TARGETS.items()}
    direct = md.group('mst_direct_reward', 'DirectRewardGroupId')
    present = md.group('mst_present', 'PresentId')
    events = md.by_id('mst_event','EventId')
    missions = md.by_id('mst_mission','MissionId')
    exchanges = md.by_id('mst_exchange','ExchangeId')
    chars = md.by_id('mst_character','CharacterId')
    recipes = md.by_id('mst_event_recipe','RecipeId')
    categories = md.by_id('mst_pin_category_type','PinCategoryType')
    issues = []

    def identity(reward):
        code, target = reward['RewardTypeCode'], reward['RewardTargetId']
        spec = TARGETS.get(code)
        if not spec:
            return {'rewardTypeCode': code, 'targetId': target, 'entityKey': None,
                    'targetResolution': 'unsupported_type', 'nativeName': None,
                    'nameStatus': 'unknown', 'nativeAssetKey': None}
        kind, table, key, name_field, asset_field = spec
        raw = targets[code].get(target)
        return {'rewardTypeCode': code, 'targetId': target, 'entityKey': f'{kind}:{target}',
                'targetResolution': 'identified' if raw else 'missing_target',
                'targetActive': raw.get('IsActive',True) if raw else None,
                'nativeName': raw.get(name_field) or None if raw else None,
                'nameStatus': 'named' if raw and str(raw.get(name_field,'')).strip() else 'native_name_empty' if raw else 'unknown',
                'nativeAssetKey': raw.get(asset_field) or None if raw and asset_field else None,
                'targetTable': table, 'targetKeyField': key}

    # Composite reward-container keys prevent collisions between Present and Direct.
    references = defaultdict(list)
    for table, group_field, rows in (
        ('mst_direct_reward','DirectRewardGroupId',md.rows('mst_direct_reward',True)),
        ('mst_present','PresentId',md.rows('mst_present',True)),
    ):
        for r in rows:
            ident = identity(r)
            if ident['entityKey']:
                references[ident['entityKey']].append({
                    'containerKey': f'{table}:{r[group_field]}',
                    'rewardCount': r.get('RewardCount'),
                    'sequence': r.get('DirectRewardSequenceNo', r.get('PresentSequenceNo')),
                })

    sources = defaultdict(list)
    supported_fields = set()
    def add(table, row, field, reward_table, kind, context=None):
        supported_fields.add((table,field))
        group_id = row.get(field)
        if group_id:
            sources[f'{reward_table}:{group_id}'].append({
                'kind': kind, 'sourceTable': table, 'sourceField': field,
                'raw': row, 'context': context or {},
            })

    # Exact reward-consuming relations only. Text describes conditions; it is not
    # parsed into invented achievement expressions.
    for table in ('mst_event_sales_reward','mst_event_accumulate_item_reward'):
        for row in md.rows(table,True):
            add(table,row,'DirectRewardGroupId','mst_direct_reward',
                'event_sales' if table=='mst_event_sales_reward' else 'event_accumulate',
                {'event': events.get(row.get('EventId'))})
    for row in md.rows('mst_mission_sequence',True):
        mission = missions.get(row['MissionId'])
        if not mission:
            issues.append({'status':'missing_mission','id':row['MissionId']}); continue
        # Retain template + Border. Render # only in the existing mission presenter.
        add('mst_mission_sequence',row,'DirectRewardGroupId','mst_direct_reward','mission',{'mission':mission})
    for row in md.rows('mst_exchange_product',True):
        ex = exchanges.get(row['ExchangeId'])
        if not ex:
            issues.append({'status':'missing_exchange','id':row['ExchangeId']}); continue
        slot = row.get('CostItemIdNumber')
        cost_id = ex.get(f'CostItemId{slot}') if slot in (1,2) else None
        add('mst_exchange_product',row,'DirectRewardGroupId','mst_direct_reward','exchange',
            {'exchange':ex, 'resolvedCostItemId':cost_id, 'costResolution':'resolved' if cost_id else 'unresolved'})
    for row in md.rows('mst_character_card_revision',True):
        add('mst_character_card_revision',row,'DirectRewardGroupId','mst_direct_reward','card_revision')
    for row in md.rows('mst_character_birthday',True):
        for field in ('TapRewardNo1','TapRewardNo2','TapRewardNo3','TapRewardSecretPin'):
            add('mst_character_birthday',row,field,'mst_direct_reward','character_birthday')
    for row in md.rows('mst_event_ranking_reward',True):
        add('mst_event_ranking_reward',row,'PresentId','mst_present','event_ranking',{'event':events.get(row['EventId'])})
    for table, parent, id_field in (
        ('mst_login_bonus_special_sequence','mst_login_bonus_special','LoginBonusSpecialId'),
        ('mst_login_bonus_daily_sequence','mst_login_bonus_daily','LoginBonusDailyId'),
    ):
        owners=md.by_id(parent,id_field)
        for row in md.rows(table,True):
            add(table,row,'PresentId','mst_present','login',{'parent':owners.get(row[id_field])})
    for row in md.rows('mst_login_bonus_total',True):
        add('mst_login_bonus_total',row,'PresentId','mst_present','login_total')
    for row in md.rows('mst_character_birthday_login_bonus_sequence',True):
        add('mst_character_birthday_login_bonus_sequence',row,'PresentId','mst_present','birthday_login')

    collections=[]; asset_requests=[]
    for code in COLLECTION_CODES:
        kind, table, id_field, name_field, asset_field = TARGETS[code]
        for identifier, raw in sorted(targets[code].items()):
            ident=identity({'RewardTypeCode':code,'RewardTargetId':identifier})
            entry={**ident, 'raw':raw, 'rewardReferences':references.get(ident['entityKey'],[])}
            if kind=='pin':
                entry['category']=categories.get(raw.get('PinCategoryType'))
            if kind=='honor':
                entry['conditionText']=raw.get('HonorGetConditionsDescription','')
                # This field is attached/outgoing reward evidence, NOT how the honor
                # itself is acquired. Keep a neutral label until client semantics checked.
                entry['attachedRewardGroupId']=raw.get('DirectRewardGroupId',0)
                entry['attachedRewards']=[{**identity(r),'count':r['RewardCount']} for r in direct.get(raw.get('DirectRewardGroupId'),[])]
                entry['rankingBindings']=[r for r in md.rows('mst_honor_ranking',True) if r['HonorId']==identifier]
            collections.append(entry)
            asset_requests.append({'entityKey':ident['entityKey'], 'kind':kind,'id':identifier,
                'nativeName':ident['nativeName'], 'sourceTable':table,'sourceField':asset_field,
                'nativeKey':raw.get(asset_field) or None,
                'keySemantics':'native_file_name',
                'roles':{'icon':raw.get(asset_field) or None},
                'maxEdge':768 if kind=='honor' else 640 if kind=='home_background' else 256})

    for p in md.rows('mst_piece_info'):
        asset_requests.append({'entityKey':f"piece:{p['PieceInfoId']}",'kind':'piece','id':p['PieceInfoId'],
            'nativeName':p.get('Name'),'sourceTable':'mst_piece_info','sourceField':'TargetSprite / MainSprite',
            'nativeKey':p.get('TargetSprite') or p.get('MainSprite') or None,
            'keySemantics':'sprite_name_NOT_proven_resource_path',
            'roles':{'target':p.get('TargetSprite') or None,'main':p.get('MainSprite') or None,'dark':p.get('DarkSprite') or None},
            'maxEdge':128})
    for r in recipes.values():
        asset_requests.append({'entityKey':f"recipe:{r['RecipeId']}",'kind':'recipe','id':r['RecipeId'],
            'nativeName':r['RecipeName'],'sourceTable':'mst_event_recipe','sourceField':'RecipeFileName',
            'nativeKey':r.get('RecipeFileName') or None,'keySemantics':'native_file_name',
            'roles':{'icon':r.get('RecipeFileName') or None,'memo':r.get('RecipeMemoBackGroundFileName') or None},'maxEdge':256})

    bart_ids={r['EventId'] for r in md.rows('mst_event_b',True)}
    sales_rewards=[]
    for row in md.rows('mst_event_sales_reward',True):
        if row['EventId'] not in bart_ids: continue
        sales_rewards.append({'eventId':row['EventId'],'shiftId':row['ShiftId'],'keySales':row['KeySales'],
            'isPickUp':row['IsPickUp'],'directRewardGroupId':row['DirectRewardGroupId'],
            'rewards':[{**identity(r),'count':r['RewardCount']} for r in direct.get(row['DirectRewardGroupId'],[])]})

    collection_group_keys={ref['containerKey'] for c in collections for ref in c['rewardReferences']}
    collection_sources={key:sources[key] for key in sorted(collection_group_keys) if key in sources}
    # Coverage is deliberately scoped: supported group references != every game's route.
    unidentified=[c['entityKey'] for c in collections if c['targetResolution']!='identified']
    no_source=[c['entityKey'] for c in collections if not any(r['containerKey'] in sources for r in c['rewardReferences'])]
    missing_consumers=sorted({r['containerKey'] for c in collections for r in c['rewardReferences'] if r['containerKey'] not in sources})

    pools=md.group('mst_puzzle_drop_reward','PuzzleDropRewardGroupId')
    pool_totals=Counter(sum(r['LotteryRate'] for r in rr) for rr in pools.values())
    mixed=sum(len({r.get('IsEvent') for r in rr})>1 for rr in pools.values())
    native_stage_economics=[{'StageKey':stage_key(s),
        **{k:s.get(k) for k in ('PuzzleDropRewardLotteryCountId','ConsumeStamina','ConsumeEventStamina',
             'FirstFixedDropPuzzleScoreRank','FirstFixedDropReward','IsHidden',
             'PuzzleStageUnlockConditionIdA','PuzzleStageUnlockConditionIdB')}} for s in md.rows('mst_puzzle_stage')]
    economics={'RecipePriceFacts':[{
        k:r.get(k) for k in ('RecipeId','EventId','RecipeName','RecipeDifficulty','Price','RequiredSecond','IngredientIds','DirectRewardGroupId')
    } for r in recipes.values()], 'BartendingBonusBindings':md.rows('mst_event_b'),
        'EventBonusProfiles':md.rows('mst_event_bonus'), 'SpecialTimeWindows':md.rows('mst_event_special_time'),
        'DropLotteryCountProfiles':md.rows('mst_puzzle_drop_reward_lottery_count'),
        'StaminaBoostProfiles':md.rows('mst_puzzle_stamina_boost_reward_rate'),
        'StageEconomicsEnrichment':native_stage_economics,
        'CampaignEconomicsEnrichment':[{'StageKey':stage_key(s),**{k:s.get(k) for k in
            ('CampaignId','PuzzleDropRewardLotteryCountId','ConsumeStamina','ConsumeEventStamina')}}
            for s in md.rows('mst_puzzle_stage_campaign')],
        'TextEvidence':[r for r in md.rows('mst_text') if r['Id'] in (90800019,90800020,90800022)],
        'RuleEvidence':[r for r in md.rows('mst_event_rule_window') if r['EventId'] in bart_ids and r['SlideNo']==5]}
    audit={'masterdataSha256':md.sha256,
        'counts':{'pin':len(targets[7]),'honor':len(targets[6]),'home_background':len(targets[3]),
                  'piece':len(md.rows('mst_piece_info')),'recipe':len(recipes)},
        'nameEmptyCounts':{kind:sum(not str(r.get(name_field,'')).strip() for r in targets[code].values())
             for code,(kind,table,id_field,name_field,asset_field) in TARGETS.items() if code in COLLECTION_CODES},
        'bartendingPickupRewardTypes':dict(Counter(r['rewardTypeCode'] for s in sales_rewards if s['isPickUp'] for r in s['rewards'])),
        'randomPoolWeightTotals':dict(sorted(pool_totals.items())), 'mixedIsEventFlagPools':mixed,
        'collectionWithoutAdaptedAcquisitionCount':len(no_source), 'completeAcquisitionGuide':False,
        'unadaptedReferencedContainers':missing_consumers,
        'unidentifiedTargets':unidentified, 'issues':issues}
    return {'Meta':{'SchemaVersion':1,'Domain':'hub_planning_collectibles_extension','MasterdataSha256':md.sha256},
        'Collections':collections,'CollectionSourceContainers':collection_sources,
        'CollectionSourceCoverage':{'complete':False,'supportedFields':[{'table':a,'field':b} for a,b in sorted(supported_fields)],
             'entityKeysWithoutKnownSource':no_source},
        'EconomicsNativeFacts':economics,'BartendingSalesRewardIdentities':sales_rewards},asset_requests,audit


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--masterdata',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--puzzle-bundle')
    ap.add_argument('--bartending-bundle')
    args=ap.parse_args(); md=MasterData(args.masterdata)
    native,assets,audit=extract(md)
    native['Meta']['CanonicalInputs']={
        'puzzle':verify_bundle(args.puzzle_bundle,md.sha256),
        'bartending':verify_bundle(args.bartending_bundle,md.sha256)}
    out=Path(args.output)
    write_json(out/'Expansion_Source.json',native)
    write_json(out/'asset_requests.json',{'schemaVersion':1,'masterdataSha256':md.sha256,'requests':assets})
    write_json(out/'audit_summary.json',audit)
    print('Exported:',audit['counts'])
    print('Snapshot:',md.sha256,'| Complete acquisition coverage: false')
    if audit['issues']:
        raise SystemExit('Relation issues written to audit_summary.json; do not promote without review')

if __name__=='__main__': main()
