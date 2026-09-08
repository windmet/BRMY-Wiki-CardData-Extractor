"""Application entry point shared by explicit CLI jobs and desktop UI."""
from pathlib import Path

from .core.output import OutputContext, output_directory, record_error
from .core.session import MasterDataSession, utc_now
from .core.masterdata import ensure_masterdata_json
from .domains import DOMAINS

MASTERDATA = {'cards', 'music', 'snap', 'birthday', 'recipes', 'missions', 'items', 'events'}


def generate(domains, output, *, masterdata=None, audio=None, source=None,
             old_workbook=None, cycle=None, year=None, subject=None,
             reference_acb=None, recent_year=None):
    """Run selected domains without chdir; return a receipt even on failure."""
    context = OutputContext(Path(output))
    domains = list(dict.fromkeys(domains))
    session = None
    started_at = utc_now()
    with context.activate():
        try:
            if not domains:
                raise ValueError('至少选择一个输出任务')
            unknown = set(domains) - set(DOMAINS)
            if unknown:
                raise ValueError(f'未知任务: {sorted(unknown)}')
            if set(domains) & (MASTERDATA | {'home_voices', 'card_update'}):
                if not masterdata:
                    raise ValueError('此任务需要 masterdata 文件')
                path = Path(masterdata).resolve()
                if path.suffix.lower() == '.s2b':
                    path = Path(ensure_masterdata_json(
                        path, output_directory('cache', context.root / '.bmc_toolkit')
                    ).json_path)
                session = MasterDataSession.open(path)
                context.warnings.extend(session.assessment.changes)
                if session.assessment.errors:
                    raise ValueError('; '.join(session.assessment.errors))
            for domain in domains:
                context.domain = domain
                error_count = len(context.errors)
                try:
                    module = DOMAINS[domain]
                    if domain == 'card_update':
                        if not old_workbook:
                            raise ValueError('更新卡牌需要旧工作簿')
                        module.run(old_workbook, audio_dir=audio, session=session)
                    elif domain == 'home_voices':
                        if not audio:
                            raise ValueError('主页语音需要 ACB 目录')
                        module.run(audio, selected_subject=subject, reference_acb_root=reference_acb,
                                   recent_year_end=recent_year, session=session)
                    elif domain == 'birthday':
                        module.run(session=session, target_cycle=cycle, target_year=year)
                    elif domain in {'cards', 'music'}:
                        if audio and not Path(audio).is_dir():
                            raise ValueError(f'音频目录不存在: {audio}')
                        module.run(audio, session=session)
                    elif domain in MASTERDATA:
                        module.run(session=session)
                    else:
                        input_path = audio if domain == 'audio' else source
                        if not input_path:
                            raise ValueError('此任务需要显式资源文件或目录')
                        if domain in {'scripts', 'charts', 'lyrics'} and Path(input_path).is_file():
                            expected = {'scripts': '.s2bscript', 'charts': '.s2bchart',
                                        'lyrics': '.s2blyrics'}[domain]
                            if Path(input_path).suffix.lower() != expected:
                                raise ValueError(f'{domain} 需要 {expected} 文件')
                        module.run(str(Path(input_path).resolve()))
                except Exception as error:
                    record_error(error)
                context.results.append({'name': domain,
                                        'status': 'FAIL' if len(context.errors) > error_count else 'PASS'})
        except Exception as error:
            record_error(error)
        finally:
            context.domain = 'run'
            if session:
                try:
                    session.write_audit(context.results, started_at=started_at, success=not context.errors)
                except Exception as error:
                    record_error(error)
    return context.finish()


def main(args):
    import argparse
    parser = argparse.ArgumentParser(description='生成 Wiki 输出及本次产物清单（不修改输入目录）')
    parser.add_argument('domains', nargs='+', choices=sorted(DOMAINS))
    parser.add_argument('--output', required=True)
    parser.add_argument('--masterdata')
    parser.add_argument('--audio')
    parser.add_argument('--source')
    parser.add_argument('--old-workbook')
    parser.add_argument('--cycle', type=int)
    parser.add_argument('--year', type=int)
    parser.add_argument('--subject')
    parser.add_argument('--reference-acb')
    parser.add_argument('--recent-year')
    report = generate(**vars(parser.parse_args(args)))
    print(f"[{report['status']}] 本次生成 {len(report['artifacts'])} 个文件")
    for error in report['errors']:
        print(f"[!] {error['domain']}: {error['error']}")
    return report['status'] != 'FAIL'
