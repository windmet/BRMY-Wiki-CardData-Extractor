import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import lz4.block
import msgpack

from toolkit.core.s2b_parser import S2BDecodeError, parse_s2b_file
from toolkit.core.tables import TableCatalog
from toolkit.domains import groove_charts, puzzle_stages
from toolkit.resolve import MASTER_KEY, build_plan
from toolkit.resources import ProdManifestProvider


def lz4_block_array(value, split=40):
    """MessagePack-CSharp Lz4BlockArray: [ext98(sizes), bin, bin, ...]."""
    payload = msgpack.packb(value, use_bin_type=True)
    chunks = [payload[i:i + split] for i in range(0, len(payload), split)]
    header = b''.join(msgpack.packb(len(chunk)) for chunk in chunks)
    blocks = [lz4.block.compress(chunk, store_size=False) for chunk in chunks]
    return msgpack.packb([msgpack.ExtType(98, header), *blocks], use_bin_type=True)


def stage_info(*, targets=(), move_limit=-1, board=(), life=5.0, tutorials=()):
    info = [None] * 21
    info[1] = [-2, 0, *board]
    info[3] = [[[[1, 100], [3, 0]], [[100004, 50, None]], [100, 0], None, None]]
    info[4] = [-1, 0, 100006]
    info[5] = [[20, 0, [None, 1302, 1302, None, 1, 48], [[], False, 0], True, 0, [], 9, 0]]
    info[7] = [2, 1.0, True]
    info[8] = [[pid, count, False] for pid, count in targets]
    info[9] = [{'ssRank': 1400000}, 21]
    info[10] = [life, 1.0, 0.0, True]
    info[11] = [[[tid, True] for tid in tutorials]]
    info[18] = [1, False, True, move_limit, False]
    return info


def catalog(**tables):
    return TableCatalog([dict.fromkeys(tables, []), *tables.values()])


TABLES = dict(
    mst_puzzle_stage=[
        {'PuzzleMapId': 101, 'PuzzleStageNo': 2, 'PuzzleType': 1, 'PuzzleStageType': 1, 'MusicPuzzleStageId': 5,
         'ReleaseDateTime': '2001-01-01T00:00:00+00:00', 'SSRankScore': 1400000, 'AverageCombo': 10,
         'ConsumeStamina': 1, 'CardAttributeCode': 1},
        {'PuzzleMapId': 101, 'PuzzleStageNo': 2, 'PuzzleType': 3, 'PuzzleStageType': 1, 'IsCoinStage': True},
        {'PuzzleMapId': 1, 'PuzzleStageNo': 201, 'PuzzleType': 1, 'PuzzleStageType': 2, 'IsActive': False},
    ],
    mst_puzzle_map=[{'PuzzleMapId': 101, 'EventId': 1}],
    mst_event=[{'EventId': 1, 'EventTitle': 'Florist', 'StartTime': '2024-05-15T18:00:00+00:00'}],
    mst_puzzle_story_stage=[{'StoryTypeCode': 1, 'StoryTargetBaseId': 6, 'StoryTargetChapterId': 1,
                             'StoryTargetSectionNo': 2, 'Target1Text': 'スコアランクBを達成！'}],
    mst_piece_info=[{'PieceInfoId': 1, 'Name': '赤色ピース'}, {'PieceInfoId': 100004, 'Name': '蝶1'},
                    {'PieceInfoId': 100006, 'Name': '蝶3'}],
    mst_gimmick_tutorial=[{'TutorialId': 100004, 'GimmickSlideNo': 1, 'GimmickName': '蝶'}],
    mst_music_puzzle_stage=[{'MusicPuzzleStageId': 5, 'MusicId': 13}],
    mst_music=[{'MusicId': 13, 'DisplayName': 'Golden Rings'}],
    mst_music_info=[{'MusicInfoId': 1302, 'MusicId': 13}],
)


class Lz4BlockArrayTests(unittest.TestCase):
    def test_stage_file_round_trips_through_the_strict_parser(self):
        info = stage_info(targets=[(100004, 24)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Stage1_1_1.s2bStage'
            path.write_bytes(lz4_block_array(info))
            self.assertEqual([info], parse_s2b_file(path, strict_extensions=True))

    def test_block_count_must_match_header(self):
        raw = msgpack.packb([msgpack.ExtType(98, msgpack.packb(5) + msgpack.packb(5)),
                             lz4.block.compress(b'\x91\x01', store_size=False)], use_bin_type=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.s2bStage'
            path.write_bytes(raw)
            with self.assertRaises(S2BDecodeError):
                parse_s2b_file(path, strict_extensions=True)


class PuzzleStageTests(unittest.TestCase):
    def test_file_names_follow_client_format_strings(self):
        tables = catalog(**TABLES)
        self.assertEqual(['Stages/Stage101_2_1.s2bStage', 'Stages/Stage101_2_3.s2bStage',
                          'Stages/StoryStage1_6_1_2.s2bStage'], puzzle_stages.resource_keys(tables))

    def test_digest_reads_targets_limits_board_and_drops(self):
        names = puzzle_stages.Names(catalog(**TABLES))
        result = puzzle_stages.digest(stage_info(targets=[(100004, 24), (0, 600000)], move_limit=30,
                                                 board=[100006, 100006, 1], tutorials=[100004]), names)
        self.assertEqual('蝶1×24 / 分数≥600000', result['TargetText'])
        self.assertEqual(30, result['MoveLimit'])
        self.assertEqual('赤色ピース×1 / 蝶3×3', result['BoardText'])
        self.assertEqual([1], result['DropColors'])
        self.assertEqual('蝶1', result['DropGimmickText'])
        self.assertEqual('蝶', result['TutorialText'])
        self.assertEqual('Golden Rings', names.music_info[result['MusicInfoId']])
        self.assertEqual('スペシャルピース', result['SpecialPiece'])
        self.assertIsNone(puzzle_stages.digest(stage_info(), names)['MoveLimit'])

    def test_extract_joins_masterdata_and_reports_missing_files(self):
        session = SimpleNamespace(tables=catalog(**TABLES))
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'Stage101_2_1.s2bStage').write_bytes(lz4_block_array(stage_info(targets=[(1, 60)])))
            data = puzzle_stages.extract(session, source=directory)
        first, coin = data['Stages']
        self.assertEqual(('活动', 'Florist', '2024-05-16', 'A'), (first['Kind'], first['Owner'], first['Released'], first['Face']))
        self.assertEqual(('Golden Rings', '日', 10), (first['Music'], first['Attribute'], first['AverageCombo']))
        self.assertEqual('赤色ピース×60', first['Stage']['TargetText'])
        self.assertTrue(coin['IsCoinStage'])
        self.assertIsNone(coin['Stage'])
        self.assertEqual((2, 3), (len(data['Issues']), data['Expected']))
        self.assertEqual({'missing_stage_file'}, {issue['Status'] for issue in data['Issues']})


class GrooveChartTests(unittest.TestCase):
    def test_summary_counts_note_kinds_and_unreleased_scores_are_missing(self):
        score = {'Bpm': 120, 'EndTimeMs': 10000, 'CueName': 'X_01', 'Gimmicks': [{'GimmickType': 'Bush'}],
                 'Notes': [{'TimeMs': 1, 'Type': 'Left'}, {'TimeMs': 2, 'Type': 'Right', 'DurationMs': 400},
                           {'TimeMs': 3, 'Type': 'Right', 'NoteType': 'Rare'},
                           {'TimeMs': 4, 'Type': 'Left', 'NoteType': 'Hirameki', 'DurationMs': 300}]}
        summary = groove_charts.summarize(score)
        self.assertEqual((4, 2, 2, 2, 1, 1, 0.4), (summary['Notes'], summary['Left'], summary['Right'], summary['Long'],
                                                   summary['Rare'], summary['Hirameki'], summary['Density']))
        tables = catalog(mst_groove_music_stage=[
            {'MusicId': 13, 'GrooveMusicStageType': 1, 'StageFileName': 'X_01_A'},
            {'MusicId': 13, 'GrooveMusicStageType': 2, 'StageFileName': 'X_01_B'}],
            mst_music=[{'MusicId': 13, 'DisplayName': 'Golden Rings'}],
            mst_groove_music=[{'MusicId': 13, 'GrooveMusicType': 1, 'ReleaseDateTime': '2027-10-07T12:00:00+00:00'}])
        self.assertEqual(['Score/X_01_A.s2bscore', 'Score/X_01_B.s2bscore'], groove_charts.resource_keys(tables))
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'X_01_A.s2bscore').write_bytes(msgpack.packb(score))
            data = groove_charts.extract(SimpleNamespace(tables=tables), source=[directory])
        self.assertEqual((1, 2), (data['Loaded'], data['Expected']))
        self.assertEqual('missing_score_file', data['Issues'][0]['Status'])
        self.assertEqual('2027-10-07', data['Charts'][1]['Released'])


class PlanTests(unittest.TestCase):
    def test_stages_are_derived_and_scores_must_be_in_the_manifest(self):
        tables = catalog(**TABLES, mst_groove_music_stage=[
            {'MusicId': 13, 'GrooveMusicStageType': 1, 'StageFileName': 'X_01_A'},
            {'MusicId': 14, 'GrooveMusicStageType': 1, 'StageFileName': 'Unreleased_A'}])
        resources = {MASTER_KEY: None, 'Score/X_01_A.s2bscore': None}
        plan = build_plan(['puzzle_stages', 'groove_charts'], resources, tables)
        self.assertEqual([], plan['errors'])
        by_key = {item['key']: item for item in plan['resources']}
        self.assertTrue(by_key['Stages/Stage101_2_1.s2bStage']['derived'])
        self.assertEqual('stages', by_key['Stages/Stage101_2_1.s2bStage']['kind'])
        self.assertEqual('scores', by_key['Score/X_01_A.s2bscore']['kind'])
        self.assertNotIn('derived', by_key['Score/X_01_A.s2bscore'])
        self.assertNotIn('Score/Unreleased_A.s2bscore', by_key)
        with self.assertRaises(ValueError):
            build_plan(['puzzle_stages'], resources)


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, url, etag):
        super().__init__(data)
        self.url = url
        self.headers = {'Content-Length': str(len(data)), 'ETag': etag}

    def geturl(self):
        return self.url


class DerivedDownloadTests(unittest.TestCase):
    def test_cache_is_revalidated_by_etag_and_usable_offline(self):
        requests = []
        body = {'value': b'stage-v1', 'etag': '"v1"'}

        def opener(request, timeout):
            requests.append(request.get_header('If-none-match'))
            if request.get_header('If-none-match') == body['etag']:
                raise urllib.error.HTTPError(request.full_url, 304, 'Not Modified', {}, None)
            return Response(body['value'], request.full_url, body['etag'])

        with tempfile.TemporaryDirectory() as directory:
            provider = ProdManifestProvider(directory, opener=opener, retry_delay=0)
            key = 'Stages/Stage1_1_1.s2bStage'
            with self.assertRaisesRegex(ValueError, '离线缓存缺失'):
                provider.download_derived(key, offline=True)
            first = provider.download_derived(key)
            self.assertFalse(first['cache_hit'])
            self.assertTrue(provider.download_derived(key)['cache_hit'])
            self.assertEqual([None, '"v1"'], requests)
            body.update(value=b'stage-v2', etag='"v2"')
            updated = provider.download_derived(key)
            self.assertEqual(b'stage-v2', Path(updated['path']).read_bytes())
            self.assertTrue(provider.download_derived(key, offline=True)['cache_hit'])
            with self.assertRaisesRegex(ValueError, 'derived path'):
                provider.download_derived('Musics/voice_1.acb')


if __name__ == '__main__':
    unittest.main()
