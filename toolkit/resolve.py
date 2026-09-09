"""Resolve task inputs from the production catalog, then invoke generation."""
from pathlib import Path
import lzma
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event

from .resources import (ProdManifestProvider, atomic_bytes, atomic_json, sha256,
                        prepare_production_masterdata)
from .core.masterdata import decode_masterdata
from .core.tables import TableCatalog
from .core.output import OutputContext
from .core.scanner import save_json
from .core.s2b_parser import parse_s2b_file
from .domains import DOMAINS
from .domains.home_voices import CHARACTER_PACKAGE_RE, STEM_TO_CHARACTER_ID
from .generate import generate, MASTERDATA

MASTER_KEY = 'Tables/master_data.s2b'
SUFFIXES = {'scripts': '.s2bscript', 'lyrics': '.s2blyrics', 'charts': '.s2bchart'}


def build_plan(domains, resources, tables=None, *, include_card_audio=True, resource_keys=None):
    domains = list(dict.fromkeys(domains))
    if not domains or set(domains) - set(DOMAINS):
        raise ValueError('请选择有效的输出任务')
    selected = {}
    warnings = []
    errors = []

    def add(key, domain, required, kind):
        if key not in resources:
            (errors if required else warnings).append(f'{domain}: 正式清单未收录 {key}')
            return
        item = selected.setdefault(key, {'key': key, 'domains': [], 'required': False, 'kind': kind})
        item['domains'].append(domain)
        item['required'] |= required

    for domain in domains:
        if domain in MASTERDATA | {'home_voices', 'home_voice_duo', 'card_update'}:
            add(MASTER_KEY, domain, True, 'masterdata')
        if domain in {'cards', 'card_update'} and include_card_audio:
            if tables is None:
                raise ValueError('卡牌资源规划需要 masterdata 表')
            for row in tables.require('mst_character_card'):
                add(f"Musics/voice_{row['CharacterCardId']}.acb", domain, False, 'audio')
        if domain in {'home_voices', 'home_voice_duo'}:
            speakers = set()
            for key in sorted(resources):
                if not key.startswith('Musics/'):
                    continue
                match = CHARACTER_PACKAGE_RE.fullmatch(Path(key).name)
                if match and match['stem'].lower() in STEM_TO_CHARACTER_ID:
                    speakers.add(match['stem'].lower())
                    add(key, domain, True, 'audio')
            for stem in sorted(set(STEM_TO_CHARACTER_ID) - speakers):
                errors.append(f'{domain}: 正式清单缺少角色包 {stem}')
        if domain == 'audio':
            keys = [key for key in resources if key.startswith('Musics/') and key.endswith('.acb')]
            if not keys:
                errors.append('audio: 正式清单未发现 ACB')
            for key in sorted(keys):
                add(key, domain, True, 'audio')
        if domain in SUFFIXES:
            keys = [key for key in resources if key.endswith(SUFFIXES[domain])]
            if resource_keys is not None:
                keys = [key for key in keys if key in resource_keys]
            if not keys:
                errors.append(f'{domain}: 已识别的正式资源路径中没有所需文件；不会猜测未知类别路径')
            for key in sorted(keys):
                add(key, domain, True, domain)
    if resource_keys is not None:
        invalid = set(resource_keys) - set(selected)
        if invalid:
            errors.append(f'所选资源不属于本次任务或未被清单确认: {sorted(invalid)}')
    output_names = set()
    for item in selected.values():
        if item['kind'] in SUFFIXES:
            identity = Path(item['key']).name.casefold()
            if identity in output_names:
                errors.append(f"独立文件导出名称冲突: {item['key']}；请缩小资源选择")
            output_names.add(identity)
    return {'domains': domains, 'resources': list(selected.values()), 'warnings': warnings,
            'errors': errors, 'include_card_audio': include_card_audio}


def materialize(download, destination, kind):
    """Validate and prepare one parser input without mutating the raw cache."""
    raw = Path(download['path']).read_bytes()
    if sha256(raw) != download['sha256']:
        raise ValueError('资源缓存校验失败')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    envelope = 'none'
    data = raw
    if kind in SUFFIXES:
        if raw.startswith(b'\x5d'):
            decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE, memlimit=256 * 1024 * 1024)
            data = decoder.decompress(raw, max_length=64 * 1024 * 1024 + 1)
            if len(data) > 64 * 1024 * 1024 or not decoder.eof or decoder.unused_data:
                raise ValueError('独立 S2B 的 LZMA 外层损坏或过大')
            envelope = 'lzma-alone'
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.validation', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        try:
            parsed = parse_s2b_file(temporary, strict_extensions=True)
            if not parsed:
                raise ValueError('独立 S2B 没有可解析内容')
        finally:
            temporary.unlink(missing_ok=True)
    elif kind == 'audio':
        from .core.cri_utf import extract_acb_cue_rows
        if not data.startswith(b'@UTF'):
            raise ValueError('ACB 不是已确认的 CRI @UTF 格式')
        extract_acb_cue_rows(data)
    atomic_bytes(destination, data)
    return {'prepared_path': str(destination.resolve()), 'prepared_sha256': sha256(data), 'envelope': envelope}


def synchronize(domains, output, cache, *, offline=False, include_card_audio=True,
                resource_keys=None, plan_only=False, cancelled=None, progress=None,
                provider=None, **generation_options):
    """Plan/download only selected inputs. Required failures stop generation."""
    output = Path(output).resolve()
    provider = provider or ProdManifestProvider(cache)
    audit = {'provider': 'production', 'offline': offline, 'downloads': [], 'warnings': [], 'errors': []}
    domains = list(dict.fromkeys(domains))

    def check():
        if cancelled and cancelled():
            raise InterruptedError('任务已取消')

    def notify(stage, **details):
        check()
        if progress:
            progress({'stage': stage, **details})

    try:
        if not domains or set(domains) - set(DOMAINS):
            raise ValueError('请选择有效的输出任务')
        if 'card_update' in domains and not Path(generation_options.get('old_workbook') or '').is_file():
            raise ValueError('更新卡牌需要有效的旧工作簿')
        notify('catalog')
        catalog = provider.refresh(offline=offline, cancelled=cancelled)
        audit['manifest_sha256'] = catalog['manifest_sha256']
        audit['unknown_record_count'] = len(catalog['unknown_records'])
        if offline:
            audit['warnings'].append('当前使用离线缓存，未检查线上更新')
        if catalog['unknown_records']:
            audit['warnings'].append(f"清单有 {len(catalog['unknown_records'])} 条未知类别，已排除在自动下载之外")
        # Each run has a fresh parser-input directory; removed/old files cannot leak in.
        stage = provider.root / 'jobs' / uuid.uuid4().hex
        tables = None
        masterdata = None
        if set(domains) & (MASTERDATA | {'home_voices', 'home_voice_duo', 'card_update'}):
            notify('masterdata')
            downloaded = provider.download(MASTER_KEY, offline=offline, cancelled=cancelled)
            prepared = prepare_production_masterdata(downloaded, stage / 'master_data.s2b')
            audit['downloads'].append({**downloaded, **prepared})
            masterdata = prepared['decoded_path']
            if set(domains) & {'cards', 'card_update'} and include_card_audio:
                tables = TableCatalog(decode_masterdata(masterdata))
        plan = build_plan(domains, provider.resources, tables, include_card_audio=include_card_audio,
                          resource_keys=resource_keys)
        audit['plan'] = plan
        audit['warnings'].extend(plan['warnings'])
        if plan['errors']:
            raise ValueError('; '.join(plan['errors']))
        notify('plan', count=len(plan['resources']), plan=plan)
        if plan_only:
            audit['status'] = 'PLANNED'
            atomic_json(output / 'audit_output/resource_plan.json', audit)
            return audit
        pending = [item for item in plan['resources'] if item['key'] != MASTER_KEY]
        abort = Event()

        def fetch(item):
            stop = lambda: abort.is_set() or bool(cancelled and cancelled())
            try:
                downloaded = provider.download(item['key'], offline=offline, cancelled=stop)
                # Hash subdirectories preserve case-sensitive keys and prevent collisions.
                # Audio parsers recurse; standalone parsers receive one file below.
                target = stage / item['kind'] / sha256(item['key'].encode()) / Path(item['key']).name
                prepared = materialize(downloaded, target, item['kind'])
                return {**downloaded, **prepared, 'domains': item['domains']}, None
            except InterruptedError:
                raise
            except Exception as error:
                if item['required']:
                    raise ValueError(f"{item['key']}: {error}") from error
                return None, f"可选卡牌语音不可用: {item['key']}: {error}"

        notify('download', index=0, total=len(pending))
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(fetch, item): item for item in pending}
            try:
                for index, future in enumerate(as_completed(futures), start=1):
                    result, warning = future.result()
                    if result:
                        audit['downloads'].append(result)
                    if warning:
                        audit['warnings'].append(warning)
                    notify('download', key=futures[future]['key'], index=index, total=len(pending))
            finally:
                abort.set()
                for future in futures:
                    future.cancel()
        audit['downloads'].sort(key=lambda item: item['key'])
        notify('generate')
        sources = {domain: [entry['prepared_path'] for entry in audit['downloads']
                            if domain in entry.get('domains', [])]
                   for domain in SUFFIXES if domain in domains}
        audio_dir = stage / 'audio'
        if set(domains) & {'cards', 'card_update'} and include_card_audio:
            audio_dir.mkdir(parents=True, exist_ok=True)
        return generate(domains, output, masterdata=masterdata,
                        audio=str(audio_dir) if audio_dir.exists() else None,
                        source=sources, resource_manifest=audit,
                        cancelled=cancelled, progress=progress, **generation_options)
    except Exception as error:
        audit['errors'].append(str(error))
        context = OutputContext(output)
        context.domain = 'resources'
        context.errors.append({'domain': 'resources', 'error': str(error)})
        context.warnings.extend(audit['warnings'])
        with context.activate():
            directory = output / 'audit_output'
            directory.mkdir(parents=True, exist_ok=True)
            save_json(audit, directory / 'resource_manifest.json')
        return context.finish()


def main(args):
    import argparse
    parser = argparse.ArgumentParser(description='按任务同步正式资源并生成 Wiki 文件')
    parser.add_argument('domains', nargs='+', choices=sorted(DOMAINS))
    parser.add_argument('--output', required=True)
    parser.add_argument('--cache', required=True)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--no-card-audio', dest='include_card_audio', action='store_false')
    parser.add_argument('--resource', dest='resource_keys', action='append')
    parser.add_argument('--old-workbook')
    parser.add_argument('--cycle', type=int)
    parser.add_argument('--year', type=int)
    parser.add_argument('--subject')
    parser.add_argument('--reference-acb')
    parser.add_argument('--recent-year')
    report = synchronize(**vars(parser.parse_args(args)))
    print(f"[{report['status']}]")
    for error in report.get('errors', []):
        print(error)
    return report['status'] != 'FAIL'
