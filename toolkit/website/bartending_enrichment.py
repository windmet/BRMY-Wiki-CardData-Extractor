"""Bartending-only menu facts, consuming canonical stages and ingredient supply.

Menu code 1 interpretation: user-supplied in-game rule confirmation, 2026-09-23.
Unknown codes and multi-condition combinations remain unresolved, never guessed.
"""
from collections import Counter, defaultdict
from .common import resolve_direct_reward_group


def enrich(source, md):
    ingredients = md.by_id('mst_event_ingredient', 'IngredientId')
    recipes = md.by_id('mst_event_recipe', 'RecipeId')
    menus = md.group_by('mst_event_menu', 'ShiftId')
    conditions = md.by_id('mst_event_menu_unlock_condition', 'MenuUnlockConditionId')
    notices = md.group_by('mst_event_rule_window', 'EventId')
    sales = md.group_by('mst_event_sales_reward', 'EventId')
    groups = {g['PuzzleDropRewardIngredientGroupId']:g['Rewards'] for g in source['IngredientDropGroups']}

    def ref(iid):
        i = ingredients[iid]
        return dict(IngredientId=iid, IngredientName=i['IngredientName'], PieceInfoId=i.get('PieceInfoId'), Description=i.get('IngredientDescription',''), FileName=i.get('IngredientFileName',''))

    def recipe(rid):
        r = recipes[rid]
        return {**{k:r.get(k) for k in ('RecipeId','RecipeName','RecipeTypeCode','EventId','RecommendCharacterId','RecipeDifficulty','RequiredSecond','Price','DirectRewardGroupId','RecipeMemo','RecipeFileName','RecipeFrameTypeCode')},
                'RecipeMemoBackGroundFileName':r.get('RecipeMemoBackGroundFileName',''),
                'IngredientIdsRaw':r['IngredientIds'],
                'IngredientRequirements':[{**ref(i), 'RequiredCount':n} for i,n in sorted(Counter(r['IngredientIds']).items())],
                'MakingRewards':resolve_direct_reward_group(md,r.get('DirectRewardGroupId')), 'Resolution':'masterdata'}

    for event in source['Events']:
        eid = event['EventId']
        legacy = eid == 10
        event.update(AcquisitionModel='legacy_board_piece' if legacy else 'post_clear_overlay', SupplyResolution='unresolved_per_stage_in_current_masterdata' if legacy else 'masterdata_overlay')
        event['RuleNotices'] = [{k:r.get(k) for k in ('SlideNo','RuleWindowSlideType','ReleaseDateTime','DescriptionFileName','Description')} for r in sorted(notices.get(eid,[]),key=lambda r:r['SlideNo'])]
        event['SalesMilestones'] = [{**{k:r[k] for k in ('ShiftId','KeySales','IsPickUp')},'Rewards':resolve_direct_reward_group(md,r['DirectRewardGroupId'])} for r in sorted(sales.get(eid,[]),key=lambda r:(r['ShiftId'],r['KeySales']))]
        demands, supplies, unlock_demands = defaultdict(list), defaultdict(list), defaultdict(list)
        for ordinal, shift in enumerate(event['Shifts'],1):
            shift['ShiftOrdinal'] = ordinal
            projected = []
            for m in sorted(menus.get(shift['ShiftId'],[]),key=lambda r:r['MenuSequenceNo']):
                raw = [{'Slot':slot,**{k:v for k,v in conditions[m['MenuUnlockConditionId'+slot]].items() if k!='IsActive'}} for slot in ('A','B') if m.get('MenuUnlockConditionId'+slot)]
                projected.append(dict(MenuSequenceNo=m['MenuSequenceNo'], Recipe=recipe(m['RecipeId']), UnlockConditions=raw, UnlockRules=[]))
            lookup = {m['MenuSequenceNo']:m for m in projected}
            one_each, unlock_total, source_counts = Counter(), Counter(), {}
            resolution = 'resolved'
            for m in projected:
                for c in m['UnlockConditions']:
                    src = lookup.get(c.get('Value1'))
                    known = c['MenuUnlockConditionCode']==1 and src and c.get('Value2',0)>0 and not c.get('Value3') and not c.get('Value4') and c['Value1']<m['MenuSequenceNo']
                    if not known:
                        m['UnlockRules'].append({'kind':'unresolved','evidence':c}); resolution='unresolved'; continue
                    m['UnlockRules'].append(dict(kind='making_count',sourceMenuSequenceNo=c['Value1'],requiredMakingCount=c['Value2'],sourceRecipeId=src['Recipe']['RecipeId'],evidence=c))
                    source_counts[c['Value1']] = max(source_counts.get(c['Value1'],0),c['Value2'])
                    for req in src['Recipe']['IngredientRequirements']:
                        unlock_demands[req['IngredientId']].append(dict(ShiftId=shift['ShiftId'],ShiftOrdinal=ordinal,TargetMenuSequenceNo=m['MenuSequenceNo'],SourceMenuSequenceNo=c['Value1'],SourceRecipeId=src['Recipe']['RecipeId'],SourceRecipeName=src['Recipe']['RecipeName'],RequiredMakingCount=c['Value2'],IngredientId=req['IngredientId'],IngredientName=req['IngredientName'],RequiredCountPerMaking=req['RequiredCount'],RequiredCountTotal=c['Value2']*req['RequiredCount']))
                if len(m['UnlockRules'])>1: resolution='unresolved'
                for req in m['Recipe']['IngredientRequirements']:
                    iid,n = req['IngredientId'],req['RequiredCount']; one_each[iid]+=n
                    demands[iid].append(dict(ShiftId=shift['ShiftId'],ShiftOrdinal=ordinal,MenuSequenceNo=m['MenuSequenceNo'],RecipeId=m['Recipe']['RecipeId'],RecipeName=m['Recipe']['RecipeName'],RequiredCountPerMaking=n))
            if resolution == 'resolved':
                for no,n in source_counts.items():
                    for req in lookup[no]['Recipe']['IngredientRequirements']: unlock_total[req['IngredientId']]+=n*req['RequiredCount']
            shift.update(Menus=projected,UnlockResolution=resolution,IngredientUnitsForOneOfEachMenu=[{**ref(i),'RequiredCount':n} for i,n in sorted(one_each.items())],IngredientUnitsToUnlockAllMenus=[{**ref(i),'RequiredCount':n} for i,n in sorted(unlock_total.items())])
            for s in shift['Stages']:
                for rank,gid in (s['IngredientConfig'] or {}).get('IngredientDropGroupIds',{}).items():
                    for r in groups.get(gid,[]):
                        if r['RewardCount']>0 and r.get('LotteryRateRaw')!=0:
                            supplies[r['RewardTargetId']].append(dict(ShiftId=shift['ShiftId'],ShiftOrdinal=ordinal,StageKey=s['StageKey'],Music=s['Music'],PuzzleType=s['PuzzleType'],Rank=rank,DropGroupId=gid,LotteryRateRaw=r.get('LotteryRateRaw'),RewardCount=r['RewardCount']))
        event['IngredientTimelines'] = []
        for iid in sorted(set(demands)|set(supplies)|set(unlock_demands)):
            d = sorted({f['ShiftOrdinal'] for f in demands[iid]}); s = sorted({f['ShiftOrdinal'] for f in supplies[iid]})
            event['IngredientTimelines'].append({**ref(iid),'DemandShifts':d,'SupplyShifts':s,'FirstDemandShiftOrdinal':d[0] if d else None,'FirstSupplyShiftOrdinal':s[0] if s else None,'DemandFacts':demands[iid],'SupplyFacts':supplies[iid],'UnlockDemandFacts':unlock_demands[iid]})
    source['Ingredients'] = [{'IngredientId':i,'IngredientName':r['IngredientName'],'PieceInfoId':r.get('PieceInfoId'),'IngredientDescription':r.get('IngredientDescription',''),'IngredientFileName':r.get('IngredientFileName','')} for i,r in sorted(ingredients.items())]
    source['Meta']['SchemaVersion'] = 3
    return source
