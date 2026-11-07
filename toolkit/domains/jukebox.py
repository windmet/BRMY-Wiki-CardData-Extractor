"""Jukebox source facts from masterdata; no audio download or ownership inference."""
from __future__ import annotations
from collections import Counter, defaultdict

from ..core.exporter import audit_path, json_path
from ..core.scanner import save_json


def active(row: dict) -> bool:
    flag = row.get('IsActive', True)
    if type(flag) is not bool:
        raise ValueError('IsActive must be boolean')
    return flag


def unique(rows: list[dict], field: str, *, only_active: bool = False) -> dict[int, dict]:
    result = {}
    for row in rows:
        if only_active and not active(row):
            continue
        key = row.get(field)
        if type(key) is not int or key <= 0 or key in result:
            raise ValueError(f'Missing/invalid/duplicate {field}: {key}')
        result[key] = row
    return result

REQUIRED = ('mst_music', 'mst_music_out_game', 'mst_music_position_jukebox',
            'mst_music_cue', 'mst_music_cue_sheet', 'mst_direct_reward',
            'mst_mission_sequence', 'mst_mission', 'mst_character_card_revision',
            'mst_character_card', 'mst_event', 'mst_campaign')
REWARD_TABLES = {'mst_direct_reward':'DirectRewardGroupId', 'mst_present':'PresentId',
                'mst_event_ojt_prize_box_reward':'PrizeBoxRewardId',
                'mst_event_ojt_prize_box_reward_random':'PrizeBoxRewardRandomId'}

def windows(row: dict, table: str, *, role: str = 'acquisition') -> list[dict]:
    if not any(k in row for k in ('StartTime','OpenStartTime','EndTime')):
        return []
    # Preserve raw endpoints. The shared GROOVE game-schedule owner interprets JST.
    start_field = 'OpenStartTime' if table == 'mst_event' and row.get('OpenStartTime') else 'StartTime'
    return [{'start':row.get(start_field) or None, 'end':row.get('EndTime') or None,
             'role':role, 'evidence':f'{table}.{start_field}/EndTime'}]

def build_source(tables: dict[str, list[dict]], snapshot: str) -> dict:
    missing = set(REQUIRED) - tables.keys()
    if missing:
        raise ValueError('Missing required tables: ' + ', '.join(sorted(missing)))
    music = unique(tables['mst_music'], 'MusicId')
    out = unique(tables['mst_music_out_game'], 'MusicId', only_active=True)
    positions = unique(tables['mst_music_position_jukebox'], 'MusicId', only_active=True)
    cues = unique(tables['mst_music_cue'], 'MusicCueId', only_active=True)
    sheets = unique(tables['mst_music_cue_sheet'], 'MusicCueSheetId', only_active=True)
    missions = unique(tables['mst_mission'], 'MissionId', only_active=True)
    events = unique(tables['mst_event'], 'EventId', only_active=True)
    campaigns = unique(tables['mst_campaign'], 'CampaignId', only_active=True)
    cards = unique(tables['mst_character_card'], 'CharacterCardId')
    issues: list[dict] = []
    consumers: dict[int,list[dict]] = defaultdict(list)
    seen_consumers: set[tuple] = set()
    for sequence in tables['mst_mission_sequence']:
        if not active(sequence):
            continue
        k = (sequence.get('MissionId'),sequence.get('MissionSequenceNo'))
        if k in seen_consumers:
            raise ValueError(f'Duplicate mission sequence: {k}')
        seen_consumers.add(k)
        group = sequence.get('DirectRewardGroupId')
        if not group:
            continue
        mission = missions.get(sequence.get('MissionId'))
        if mission is None:
            # Only escalate as a Jukebox issue when a music reference consumes it.
            consumers[group].append({'key':f'mission:{k[0]}:{k[1]}','kind':'unresolved',
                'reason':'missing_active_mission','sequence':sequence,'windows':[]})
            continue
        code, target = mission.get('SpecialTabTypeCode'), mission.get('SpecialTabTargetId')
        parent = events.get(target) if code == 1 else campaigns.get(target) if code == 2 else None
        parent_table = 'mst_event' if code == 1 else 'mst_campaign'
        kind = {0:'mission',1:'event_mission',2:'campaign_mission'}.get(code,'unresolved')
        resolution = 'resolved' if code == 0 or code in (1,2) and parent else 'unresolved'
        condition = mission.get('Description','')
        if not isinstance(condition, str):
            raise ValueError(f'Invalid mission description: {k}')
        border = sequence.get('Border')
        if type(border) in (int,float):
            condition = condition.replace('#',str(border))
        ws = windows(mission,'mst_mission') + (windows(parent,parent_table) if parent else [])
        consumers[group].append({
            'key':f'mission:{k[0]}:{k[1]}', 'kind':kind, 'resolution':resolution,
            'conditionText':condition, 'missionId':k[0], 'sequenceNo':k[1],
            'owner':{'type':code, 'id':target, 'title':(parent or {}).get('EventTitle') or (parent or {}).get('CampaignTitle') or ''},
            'conditionTarget':{'missionType':mission.get('MissionType'),
                'value1':mission.get('Value1'),'value2':mission.get('Value2'),'value3':mission.get('Value3')},
            'requirementLabel':'Puzzle SS' if mission.get('MissionType')==1008 and 'スコアランクSS' in condition else '原生任务条件',
            'windows':ws,
            # Named parent + mission dates are retained, but not certified as all
            # possible unlock/claim/account constraints. Do not infer current ownership.
            'windowResolution':'partial' if ws else 'unknown',
            'provenance':{'sourceTable':'mst_mission_sequence','sourceField':'DirectRewardGroupId',
                          'mission':mission,'sequence':sequence,'parent':parent},
        })
    seen_revision: set[tuple] = set()
    for r in tables['mst_character_card_revision']:
        if not active(r):
            continue
        k = (r.get('CharacterCardId'),r.get('RevisionRank'))
        if k in seen_revision:
            raise ValueError(f'Duplicate card revision: {k}')
        seen_revision.add(k)
        if not r.get('DirectRewardGroupId'):
            continue
        card = cards.get(r.get('CharacterCardId'))
        consumers[r['DirectRewardGroupId']].append({
            'key':f'card_revision:{k[0]}:{k[1]}','kind':'card_revision',
            'resolution':'resolved' if card else 'unresolved',
            'conditionText':f"{(card or {}).get('CharacterCardName') or '卡牌 #' + str(k[0])} · Revision {k[1]}",
            'cardId':k[0],'revisionRank':k[1], 'windows':[], 'windowResolution':'unknown',
            'provenance':{'sourceTable':'mst_character_card_revision','sourceField':'DirectRewardGroupId',
                          'revision':r,'cardReleaseDateTime':(card or {}).get('ReleaseDateTime')},
        })
    refs: dict[int,list[dict]] = defaultdict(list)
    for table, group_key in REWARD_TABLES.items():
        seen_rewards: set[tuple] = set()
        sequence_key = {'mst_direct_reward':'DirectRewardSequenceNo', 'mst_present':'PresentSequenceNo'}.get(table)
        for r in tables.get(table,[]):
            if not active(r) or r.get('RewardTypeCode') != 8:
                continue
            target = r.get('RewardTargetId')
            if target not in music:
                raise ValueError(f'Typed music reward references missing MusicId: {target}')
            if sequence_key:
                identity = (r.get(group_key), r.get(sequence_key))
                if identity in seen_rewards:
                    raise ValueError(f'Duplicate typed music reward row: {table}:{identity}')
                seen_rewards.add(identity)
            refs[target].append({'sourceTable':table,'groupKey':group_key,'groupId':r.get(group_key),'raw':r})
    entries = []
    for mid, resource in sorted(out.items()):
        if mid not in music:
            raise ValueError(f'Out-game row has missing MusicId {mid}')
        m = music[mid]
        for field in ('AudioFileName','JacketFileName','LyricsFileName'):
            if not isinstance(resource.get(field,''),str):
                raise ValueError(f'Invalid {field}: MusicId {mid}')
        cue = cues.get(resource.get('ProfileMusicCueId'))
        sheet = sheets.get((cue or {}).get('MusicCueSheetId'))
        binding_ok = bool(cue and sheet)
        if not binding_ok:
            issues.append({'musicId':mid,'status':'profile_cue_sheet_unresolved'})
        acquired = []
        unresolved = []
        for ref in refs.get(mid,[]):
            matches = consumers.get(ref['groupId'],[]) if ref['sourceTable']=='mst_direct_reward' else []
            if not matches:
                unresolved.append(ref)
            for match in matches:
                route = {**match, 'reward':ref, 'rewardTargetMusicId':mid}
                acquired.append(route)
                if route.get('resolution') != 'resolved':
                    issues.append({'musicId':mid,'status':'source_unresolved','sourceKey':route['key']})
        if unresolved:
            issues.append({'musicId':mid,'status':'typed_reward_consumer_not_adapted','count':len(unresolved)})
        entries.append({
            'id':mid,'entityKey':f'music:{mid}', 'title':m.get('DisplayName',''),
            'artist':m.get('ArtistNameInformal') or m.get('ArtistName',''),
            'musicType':m.get('MusicType'), 'characterId':m.get('CharacterId'),
            'targetActive':active(m),'sortOrder':resource.get('SortOrder',0),
            'audioFileKey':resource.get('AudioFileName',''),'jacketKey':resource.get('JacketFileName',''),
            'lyricsKey':resource.get('LyricsFileName',''), 'position':positions.get(mid),
            'profileBinding':{'status':'resolved_profile_only' if binding_ok else 'unresolved',
                'profileMusicCueId':resource.get('ProfileMusicCueId'),
                'cueName':(cue or {}).get('MusicCueName'), 'cueSheetId':(cue or {}).get('MusicCueSheetId'),
                'downloadFileName':(sheet or {}).get('DownloadFileName'), 'fullPlaybackStreamVerified':False},
            'acquisitionRoutes':acquired, 'unresolvedRewardReferences':unresolved,
            'sourceCoverage':'supported_consumers_only', 'ownership':'not_assessed',
            'duration':{'status':'pending','seconds':None,'kind':None},
        })
    entries.sort(key=lambda e:(e['sortOrder'],e['id']))
    counts = Counter(r['kind'] for e in entries for r in e['acquisitionRoutes'])
    if set(out) != set(positions):
        issues.append({'status':'out_game_position_set_diff',
                       'outGameOnly':sorted(set(out)-set(positions)), 'positionOnly':sorted(set(positions)-set(out))})
    # Audit recognizable references to music reward groups in tables not handled by
    # this vertical slice. Do not interpret absence here as exhaustive game coverage.
    music_groups = {r['groupId'] for rr in refs.values() for r in rr if r['sourceTable']=='mst_direct_reward'}
    unexpected = []
    adapted = {('mst_mission_sequence','DirectRewardGroupId'),('mst_character_card_revision','DirectRewardGroupId')}
    for table,rows in tables.items():
        if table in REWARD_TABLES:
            continue
        for row in rows:
            if not active(row):
                continue
            for field,value in row.items():
                if field.endswith('DirectRewardGroupId') and type(value) is int and value in music_groups and (table,field) not in adapted:
                    unexpected.append({'table':table,'field':field,'groupId':value})
    if unexpected:
        issues.append({'status':'additional_consumers_require_adapter','consumers':unexpected})
    return {'Meta':{'SchemaVersion':1,'Domain':'jukebox','MasterdataSha256':snapshot,
                    'Status':'candidate_needs_review' if issues else 'candidate_not_published',
                    'ScheduleContract':'groove-masterdata-jst-wall-clock-v1',
                    'CompleteAcquisitionCoverage':False},
            'Entries':entries,
            'Audit':{'musicIdentityCount':len(music),'jukeboxCount':len(entries),
                'positionCount':len(positions),'routeCount':sum(counts.values()),'routeKinds':dict(counts),
                'withoutKnownRoutes':[e['id'] for e in entries if not e['acquisitionRoutes']],
                'typedRewardMusicOutsideJukebox':sorted(set(refs)-set(out)),
                'profileCueSheets':len({e['profileBinding']['cueSheetId'] for e in entries if e['profileBinding']['cueSheetId']}),
                'issues':issues}}

def run(session=None):
    if session is None:
        raise ValueError('Jukebox requires a masterdata session')
    tables = {name: session.tables.rows(name) for name in REQUIRED}
    source = build_source(tables, session.json_sha256)
    save_json(source['Audit'], audit_path('jukebox-audit.json'))
    if source['Audit']['issues']:
        raise ValueError(f"Jukebox source has {len(source['Audit']['issues'])} unresolved issues")
    save_json(source, json_path('Jukebox_Source.json'))
    return source
