"""Canonical Music identities; references are evidence, not title-based joins."""
from collections import defaultdict
from .jukebox import unique, active


def build_source(tables, snapshot):
    music = unique(tables.require('mst_music'), 'MusicId')
    # Membership does not select one resource row from an ambiguous relation.
    # The existing music_relations audit retains duplicate/orphan evidence.
    out = {r['MusicId'] for r in tables.require('mst_music_out_game') if active(r)}
    references = defaultdict(list)
    for table in tables.names:
        if table == 'mst_music':
            continue
        for row in tables.rows(table):
            if not active(row):
                continue
            for field, value in row.items():
                if field.endswith('MusicId') and type(value) is int and value in music:
                    domain = ('PUZZLE' if table.startswith('mst_music_puzzle_') else
                              'GROOVE' if table.startswith('mst_groove_') else
                              'Jukebox' if table in ('mst_music_out_game', 'mst_music_position_jukebox') else '其他')
                    references[value].append({'domain': domain, 'table': table, 'field': field,
                        'identity': {k:v for k,v in row.items() if k.endswith(('Id','No')) and type(v) is int}})
    return {'Meta': {'SchemaVersion': 1, 'Domain': 'music', 'MasterdataSha256': snapshot,
                     'Status': 'candidate_not_published'},
            'Entries': [{'id': mid, 'title': row.get('DisplayName',''),
                         'artist': row.get('ArtistNameInformal') or row.get('ArtistName',''),
                         'musicType': row.get('MusicType'), 'characterId': row.get('CharacterId'),
                         'active': active(row), 'jukebox': mid in out,
                         'usages': sorted({r['domain'] for r in references[mid]}),
                         'references': references[mid]}
                        for mid, row in sorted(music.items())]}
