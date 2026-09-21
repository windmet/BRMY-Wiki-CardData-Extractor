import io
import json
import lzma
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

import msgpack

from toolkit.core.tables import TableCatalog
from toolkit.resources import ProdManifestProvider, MANIFEST_KEY
from toolkit.resolve import build_plan, synchronize, MASTER_KEY


def deflate(data):
    encoder = zlib.compressobj(wbits=-15)
    return encoder.compress(data) + encoder.flush()


class Response(io.BytesIO):
    status = 200
    def __init__(self, body, url):
        super().__init__(body)
        self.url = url
        self.headers = {'Content-Length': str(len(body))}
    def geturl(self):
        return self.url


class NewDomainPlanTests(unittest.TestCase):
    def test_new_masterdata_domains_and_duo_share_required_inputs(self):
        from toolkit.domains.home_voices import CHARACTER_ACB_STEMS
        resources = {MASTER_KEY: None, **{f'Musics/voice_{stem}_general.acb': None for stem in CHARACTER_ACB_STEMS.values()}}
        names = ['ojt', 'birthday_archive', 'story_catalog', 'collections', 'home_voice_duo']
        plan = build_plan(names, resources)
        self.assertEqual([], plan['errors'])
        self.assertEqual(22, len(plan['resources']))
        self.assertEqual(names, plan['resources'][0]['domains'])
        self.assertTrue(all(row['required'] for row in plan['resources']))


def provider_for(root, payloads):
    rows = [[key.split('/', 1)[1], 1, 2 if key.startswith('Tables/') else
             1 if key.startswith('Scripts/') else 6 if key.startswith('Jukebox/') else 5, 0, 1]
            for key in payloads]
    catalog = deflate(msgpack.packb([rows], use_bin_type=True))
    def opener(request, timeout):
        key = request.full_url.split('.com/', 1)[1]
        if key == MANIFEST_KEY:
            return Response(catalog, request.full_url)
        value = payloads[key]
        if isinstance(value, Exception):
            raise value
        return Response(value, request.full_url)
    return ProdManifestProvider(root, opener=opener)


class ResolverTests(unittest.TestCase):
    def test_preview_hash_checks_cache_without_downloading_missing_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = 'Scripts/story.s2bscript'
            provider = provider_for(root / 'cache', {key: b'cached content'})
            provider.refresh()
            downloaded = provider.download(key)
            def preview():
                return synchronize(['scripts'], root / 'out', root / 'cache', provider=provider,
                                   resource_keys=[key], offline=True, plan_only=True)
            report = preview()
            self.assertEqual(1, report['cache_assessment']['verified'])
            Path(downloaded['path']).write_bytes(b'corrupt content')
            report = preview()
            self.assertEqual('PLANNED', report['status'])
            self.assertEqual(0, report['cache_assessment']['verified'])
            self.assertEqual(1, report['cache_assessment']['not_verified'])
            self.assertEqual(b'corrupt content', Path(downloaded['path']).read_bytes())

    def test_card_plan_uses_masterdata_ids_and_never_downloads_unrelated_packages(self):
        tables = TableCatalog([{'mst_character_card': [0, 0]},
                               [{'CharacterCardId': 1}, {'CharacterCardId': 2}]])
        resources = {key: None for key in [MASTER_KEY, 'Musics/voice_1.acb',
                                          'Musics/voice_999.acb', 'Files/Android/bundle']}
        plan = build_plan(['cards', 'events'], resources, tables)
        self.assertEqual([MASTER_KEY, 'Musics/voice_1.acb'], [r['key'] for r in plan['resources']])
        self.assertIn('voice_2.acb', plan['warnings'][0])
        self.assertFalse(plan['errors'])
        self.assertEqual([MASTER_KEY], [r['key'] for r in build_plan(
            ['cards'], resources, include_card_audio=False)['resources']])

    def test_home_requires_known_speakers_and_charts_do_not_guess_paths(self):
        plan = build_plan(['home_voices'], {MASTER_KEY: None, 'Musics/voice_rare_general.acb': None})
        self.assertEqual(21, len(plan['errors']))
        self.assertEqual([MASTER_KEY], [r['key'] for r in plan['resources']])
        self.assertTrue(build_plan(['charts'], {})['errors'])
        self.assertTrue(build_plan(['scripts'], {'Scripts/A.s2bscript': None,
                                                'Scripts/a.s2bscript': None})['errors'])

    def test_script_and_lyrics_are_prepared_separately_and_generate_real_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = msgpack.packb([{'Text': 'story'}], use_bin_type=True)
            lyric = msgpack.packb([[[1, 2.5, 'lyric']]], use_bin_type=True)
            payloads = {'Scripts/story.s2bscript': lzma.compress(script, format=lzma.FORMAT_ALONE),
                        'Jukebox/song.s2blyrics': lyric,
                        'Scripts/unselected.s2bscript': ValueError('must not download')}
            provider = provider_for(root / 'cache', payloads)
            report = synchronize(['scripts', 'lyrics'], root / 'out', root / 'cache', provider=provider,
                                 resource_keys=['Scripts/story.s2bscript', 'Jukebox/song.s2blyrics'])
            self.assertEqual('PASS', report['status'], report['errors'])
            paths = {Path(a['path']).name for a in report['artifacts']}
            self.assertEqual({'resource_manifest.json', 'story.s2bscript.json', 'song.s2blyrics.json', 'song.lrc'}, paths)
            self.assertIn('lyric', (root / 'out/wiki_output/song.lrc').read_text(encoding='utf-8-sig'))
            audit = json.loads((root / 'out/audit_output/resource_manifest.json').read_text(encoding='utf-8'))
            self.assertEqual({'none', 'lzma-alone'}, {r['envelope'] for r in audit['downloads']})
            for record in audit['downloads']:
                self.assertNotEqual(record['path'], record['prepared_path'])

    def test_required_failure_and_cancellation_prevent_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payloads = {'Scripts/story.s2bscript': OSError('offline failure')}
            provider = provider_for(root / 'cache', payloads)
            with patch('toolkit.resolve.generate') as generate:
                report = synchronize(['scripts'], root / 'out', root / 'cache', provider=provider)
                self.assertEqual('FAIL', report['status'])
                generate.assert_not_called()
                report = synchronize(['scripts'], root / 'cancel', root / 'cache', provider=provider,
                                     cancelled=lambda: True)
                self.assertEqual('FAIL', report['status'])
                self.assertIn('取消', report['errors'][0]['error'])
                generate.assert_not_called()

    def test_optional_card_audio_failure_is_reported_without_blocking_card_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master = msgpack.packb({'mst_character_card': [0, 0]}) + msgpack.packb([{'CharacterCardId': 1}])
            provider = provider_for(root / 'cache', {MASTER_KEY: deflate(master),
                                                    'Musics/voice_1.acb': OSError('unavailable')})
            with patch('toolkit.resolve.generate', return_value={'status': 'TEST'}) as generate:
                synchronize(['cards'], root / 'out', root / 'cache', provider=provider)
                kwargs = generate.call_args.kwargs
                self.assertTrue(kwargs['resource_manifest']['warnings'])
                self.assertTrue(Path(kwargs['audio']).is_dir())

    def test_plan_only_downloads_masterdata_but_not_card_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master = msgpack.packb({'mst_character_card': [0, 0]}) + msgpack.packb([{'CharacterCardId': 1}])
            provider = provider_for(root / 'cache', {MASTER_KEY: deflate(master),
                                                    'Musics/voice_1.acb': OSError('must not download')})
            report = synchronize(['cards'], root / 'out', root / 'cache', provider=provider, plan_only=True)
            self.assertEqual('PLANNED', report['status'])
            self.assertEqual(2, len(report['plan']['resources']))
            self.assertEqual(1, len(report['downloads']))
            self.assertFalse((root / 'out/wiki_output').exists())

    def test_second_sync_does_not_include_previous_task_staged_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = msgpack.packb([{'Text': 'story'}])
            provider = provider_for(root / 'cache', {'Scripts/one.s2bscript': body,
                                                    'Scripts/two.s2bscript': body})
            first = synchronize(['scripts'], root / 'out', root / 'cache', provider=provider,
                                resource_keys=['Scripts/one.s2bscript'])
            second = synchronize(['scripts'], root / 'out', root / 'cache', provider=provider,
                                 resource_keys=['Scripts/two.s2bscript'])
            self.assertEqual('PASS', first['status'])
            self.assertEqual('PASS', second['status'])
            names = {Path(a['path']).name for a in second['artifacts']}
            self.assertIn('two.s2bscript.json', names)
            self.assertNotIn('one.s2bscript.json', names)
            self.assertTrue((root / 'out/audit_output/one.s2bscript.json').exists())


if __name__ == '__main__':
    unittest.main()
