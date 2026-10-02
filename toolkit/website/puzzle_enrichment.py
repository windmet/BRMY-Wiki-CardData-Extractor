from .puzzle_stage_v2 import extract

def enrich(source, md):
    extra = extract(md)
    lookup = {s['StageKey']: s for s in extra['Stages']}
    native = {f"{s['PuzzleMapId']}:{s['PuzzleStageNo']}:{s['PuzzleType']}": s for s in md.rows('mst_puzzle_stage')}
    types = md.by_id('mst_marvelous_challenge','MarvelousChallengeId')
    for stage in source['Stages']:
        key = f"{stage['PuzzleMapId']}:{stage['PuzzleStageNo']}:{stage['PuzzleType']}"
        evidence = lookup[key]
        for field in ('ClearRewardChallengeCoin','ClearRewardChallengeCoinRewardRateId'):
            stage[field] = native[key].get(field,0)
        stage['MarvelousChallengeType'] = types.get(stage['MarvelousChallengeId'],{}).get('MarvelousChallengeType',0)
        for field in ('PieceProfile', 'Regulations', 'Quiz', 'Preset', 'CardAttributeCode', 'SpCost'):
            stage[field] = evidence[field]
    source['StageGroups'] = [{k: v for k, v in group.items() if k != 'Variants'} | {
        'StageKeys': [variant['StageKey'] for variant in group['Variants']]
    } for group in extra['StageGroups']]
    for field in ('PieceCatalog', 'UnboundRuleCatalog', 'DropGroupUsage'):
        source[field] = extra[field]
    source['Meta']['SchemaVersion'] = 5
    return source
