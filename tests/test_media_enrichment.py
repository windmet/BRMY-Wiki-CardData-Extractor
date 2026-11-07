import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from toolkit.media_enrichment import enrich

class Provider:
    enrichment_offline=True
    def download(self,key,**kwargs):
        if key!='Jukebox/full_N.mp3':raise AssertionError(key)
        return dict(key=key,path='unused.mp3',sha256='a'*64,size=20,fingerprint='1',manifest_sha256='b'*64)

class MediaTests(TestCase):
    def test_exact_file_receipt_cache_and_failure(self):
        source={'Meta':{'MasterdataSha256':'c'*64},'Entries':[{'id':1,'audioFileKey':'full_N','jacketKey':'jacket'}]}
        metadata={'version':'test','numberOfSamples':48000,'sampleRate':48000,'streamInfo':{'total':0,'index':0,'name':None}}
        with tempfile.TemporaryDirectory() as directory:
            exe=Path(directory)/'engine';exe.write_bytes(b'test')
            with patch('toolkit.media_enrichment.probe',return_value=metadata) as measure:
                first=enrich(source,Provider(),exe)
                self.assertEqual('jukebox_file',first['entries']['1']['duration']['kind'])
                enrich(source,Provider(),exe,first);self.assertEqual(1,measure.call_count)
            class Failed(Provider):
                def download(self,*args,**kwargs):raise OSError('offline missing')
            stale=enrich(source,Failed(),exe,first)
            self.assertEqual({'status':'stale','seconds':None,'kind':None},stale['entries']['1']['duration'])
            with patch('toolkit.media_enrichment.probe',return_value={**metadata,'streamInfo':{'total':2}}):
                pending=enrich(source,Provider(),exe)
                self.assertEqual('pending',pending['entries']['1']['duration']['status'])
