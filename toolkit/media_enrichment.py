"""Optional, receipt-backed Jukebox media enrichment, independent of masterdata sync.

Exact catalogued Jukebox files take precedence over profile cues. No guessed
suffix removal, preview duration, or 'longest subsong' selection is permitted.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import lzma
from pathlib import Path
import re
import subprocess
from .resources import ProdManifestProvider, atomic_json

RESOLVER = 'exact-jukebox-file-v1'


def probe(executable, path, subsong=None):
    command = [str(executable), '-m', '-I', '-i']
    if subsong is not None:
        command += ['-s', str(subsong)]
    result = subprocess.run(command + [str(path)], capture_output=True, text=True, timeout=60, check=True)
    data = json.loads(result.stdout)
    samples, rate = data.get('numberOfSamples'), data.get('sampleRate')
    if type(samples) is not int or type(rate) is not int or samples <= 0 or rate <= 0:
        raise ValueError('Invalid vgmstream sample count/rate')
    return data


def resource_evidence(receipt):
    return {k: receipt[k] for k in ('key', 'fingerprint', 'sha256', 'size', 'manifest_sha256')}


def enrich(source, provider, executable, previous=None, jacket_output=None):
    engine_hash = hashlib.sha256(Path(executable).read_bytes()).hexdigest()
    previous = (previous or {}).get('entries', {})

    def one(entry):
        mid, audio_key = str(entry['id']), entry['audioFileKey']
        result = {'id': entry['id'], 'audioFileKey': audio_key, 'jacketKey': entry['jacketKey'],
                  'resolver': RESOLVER, 'engineSha256': engine_hash,
                  'duration': {'status':'pending', 'seconds':None, 'kind':None}, 'jacket':None}
        old = previous.get(mid, {})
        try:
            if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.mp3)?', audio_key):
                raise ValueError('Unsafe audio key')
            key = 'Jukebox/' + audio_key + ('' if audio_key.endswith('.mp3') else '.mp3')
            receipt = provider.download(key, offline=provider.enrichment_offline)
            result['resource'] = resource_evidence(receipt)
            if (all(old.get('resource',{}).get(k) == result['resource'][k] for k in ('key','sha256','size','fingerprint')) and old.get('engineSha256') == engine_hash
                    and old.get('resolver') == RESOLVER and old.get('audioFileKey') == audio_key
                    and old.get('duration',{}).get('status') == 'measured'):
                result.update({k:old[k] for k in ('duration','measurement')})
            else:
                metadata = probe(executable, receipt['path'])
                if metadata.get('streamInfo',{}).get('total',0) > 1:
                    raise ValueError('Ambiguous Jukebox file streams')
                result['measurement'] = {'version':metadata['version'], 'sampleRate':metadata['sampleRate'],
                    'samples':metadata['numberOfSamples'], 'stream':metadata.get('streamInfo'),
                    'encoding':metadata.get('encoding')}
                result['duration'] = {'status':'measured', 'seconds':metadata['numberOfSamples']/metadata['sampleRate'], 'kind':'jukebox_file'}
        except Exception as error:
            result['duration']['status'] = 'stale' if old.get('duration',{}).get('status') == 'measured' else 'pending'
            result['error'] = f'{type(error).__name__}: {error}'
        if jacket_output:
            try:
                import UnityPy
                from PIL import Image
                native = entry['jacketKey']
                if not re.fullmatch(r'[A-Za-z0-9_-]+', native):
                    raise ValueError('Unsafe jacket key')
                receipt = provider.download('Files/Android/'+native, offline=provider.enrichment_offline, limit=16*1024*1024)
                decoder = lzma.LZMADecompressor(memlimit=256*1024*1024)
                data = decoder.decompress(Path(receipt['path']).read_bytes(), max_length=64*1024*1024)
                if not decoder.eof or decoder.unused_data:
                    raise ValueError('Invalid jacket envelope')
                textures = [o.read() for o in UnityPy.load(data).objects if o.type.name == 'Texture2D']
                textures = [t for t in textures if t.m_Name == native]
                if len(textures) != 1:
                    raise ValueError('Ambiguous jacket texture')
                image = textures[0].image.convert('RGBA');image.thumbnail((256,256), Image.Resampling.LANCZOS)
                destination = Path(jacket_output)/f'{native}.webp';destination.parent.mkdir(parents=True,exist_ok=True)
                image.save(destination,'WEBP',lossless=True,method=6)
                result['jacket'] = {'src':f'/brmy-assets/jukebox/{native}.webp','width':image.width,'height':image.height,
                                    'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(), 'resource':resource_evidence(receipt)}
            except Exception as error:
                result['jacketError'] = f'{type(error).__name__}: {error}'
        return mid, result

    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = dict(pool.map(one, source['Entries']))
    return {'schemaVersion':1, 'masterdataSha256':source['Meta']['MasterdataSha256'], 'entries':entries}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--vgmstream',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--offline',action='store_true');parser.add_argument('--jacket-output',type=Path)
    args=parser.parse_args()
    source=json.loads(args.source.read_text('utf-8'))
    if source['Meta']['Domain']!='jukebox':raise ValueError('Expected Jukebox source')
    provider=ProdManifestProvider(args.cache);provider.refresh(offline=args.offline);provider.enrichment_offline=args.offline
    previous=json.loads(args.output.read_text('utf-8')) if args.output.exists() else None
    receipt=enrich(source,provider,args.vgmstream.resolve(),previous,args.jacket_output)
    atomic_json(args.output,receipt)
    from collections import Counter
    print(dict(Counter(e['duration']['status'] for e in receipt['entries'].values())))
    print('Jackets:',sum(e['jacket'] is not None for e in receipt['entries'].values()))


if __name__=='__main__':main()
