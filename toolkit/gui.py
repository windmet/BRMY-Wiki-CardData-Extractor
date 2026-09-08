"""Native desktop front end for the same local/production generation services."""
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Event
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog

TASKS = {
    'cards': '卡牌表', 'events': '活动资料', 'home_voices': '主页 / 生日祝福',
    'birthday': '生日庆典台词', 'card_update': '更新已有卡表', 'items': '道具图鉴',
    'music': '音乐资料', 'snap': 'Snap 文案', 'recipes': '配方', 'missions': '隐藏任务',
    'lyrics': '歌词', 'scripts': '剧情脚本', 'charts': '谱面（本地）', 'audio': '通用语音文本',
}
MODES = {'正式服在线': 'online', '正式服离线缓存': 'offline', '使用本地资源': 'local'}


def app_directory():
    return Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'BRMYWikiToolkit'


@dataclass
class JobRequest:
    mode: str
    domains: list
    output: str
    cache: str
    masterdata: str = ''
    audio: str = ''
    source: str = ''
    old_workbook: str = ''
    include_card_audio: bool = True
    cycle: str = ''
    subject: str = ''
    recent_year: str = ''
    resource_keys: list = field(default_factory=list)

    def validate(self):
        from .generate import MASTERDATA
        if self.mode not in {'online', 'offline', 'local'}:
            raise ValueError('请选择资源模式')
        if not self.domains or set(self.domains) - set(TASKS):
            raise ValueError('请至少选择一项要生成的资料')
        if not self.output.strip():
            raise ValueError('请选择输出目录')
        if self.cycle and (not self.cycle.isdigit() or int(self.cycle) < 1):
            raise ValueError('生日轮次应为正整数，留空自动选择最新轮次')
        if self.recent_year:
            from datetime import date
            try:
                date.fromisoformat(self.recent_year)
            except ValueError:
                raise ValueError('近一年截止日期应为 YYYY-MM-DD') from None
        if 'card_update' in self.domains and not Path(self.old_workbook).is_file():
            raise ValueError('更新已有卡表需要选择旧 Excel 工作簿')
        if self.mode != 'local':
            if not self.cache.strip():
                raise ValueError('请选择资源缓存目录')
            if 'charts' in self.domains:
                raise ValueError('在线谱面路径尚未确认，请切换到本地资源模式')
        else:
            if set(self.domains) & (MASTERDATA | {'home_voices', 'card_update'}):
                if not Path(self.masterdata).is_file():
                    raise ValueError('本地任务需要选择 masterdata 文件')
            if set(self.domains) & {'home_voices', 'audio'}:
                if not self.audio or not Path(self.audio).is_dir():
                    raise ValueError('该任务需要选择本地 ACB 音频目录')
            if self.audio and not Path(self.audio).is_dir():
                raise ValueError('本地音频目录不存在')
            if set(self.domains) & {'scripts', 'lyrics', 'charts'}:
                if not self.source or not Path(self.source).exists():
                    raise ValueError('请选择独立歌词、脚本或谱面文件 / 文件夹')
        return self


def execute_job(request, plan_only, cancelled, progress):
    request.validate()
    options = {'old_workbook': request.old_workbook or None,
               'cycle': int(request.cycle) if request.cycle else None,
               'subject': request.subject or None, 'recent_year': request.recent_year or None}
    if request.mode == 'local':
        if plan_only:
            return {'status': 'PLANNED', 'plan': {'domains': request.domains, 'resources': []},
                    'warnings': ['本地输入路径已检查；数据格式将在生成时验证。'], 'errors': []}
        from .generate import generate
        return generate(request.domains, request.output, masterdata=request.masterdata or None,
                        audio=request.audio or None, source=request.source or None,
                        cancelled=cancelled, progress=progress, **options)
    from .resolve import synchronize
    return synchronize(request.domains, request.output, request.cache,
                       offline=request.mode == 'offline', plan_only=plan_only,
                       include_card_audio=request.include_card_audio,
                       resource_keys=request.resource_keys or None,
                       cancelled=cancelled, progress=progress, **options)


class ToolkitApp:
    def __init__(self, root, *, backend=execute_job, settings_path=None):
        self.root = root
        self.backend = backend
        self.settings_path = Path(settings_path) if settings_path else app_directory() / 'settings.json'
        self.queue = Queue()
        self.cancel_event = Event()
        self.worker = None
        self.closing = False
        self.artifacts = {}
        self.last_result = None
        self.active_request = None
        self.root.title('BRMY Wiki Toolkit')
        self.root.geometry('980x800')
        self.root.minsize(860, 760)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.mode = tk.StringVar(value='正式服在线')
        self.status = tk.StringVar(value='选择需要的资料，检查资源后开始生成。')
        self.paths = {name: tk.StringVar() for name in
                      ['output', 'cache', 'masterdata', 'audio', 'source', 'old_workbook',
                       'cycle', 'subject', 'recent_year', 'resource_keys']}
        self.paths['output'].set(str(Path.home() / 'Documents/BRMYWikiOutput'))
        self.paths['cache'].set(str(app_directory() / 'cache'))
        self.selected = {name: tk.BooleanVar(value=name == 'cards') for name in TASKS}
        self.include_card_audio = tk.BooleanVar(value=True)
        self.inputs = []
        self._build()
        self._restore()
        self._mode_changed()
        self.root.after(100, self._poll)

    def _build(self):
        style = ttk.Style(self.root)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 19, 'bold'))
        style.configure('Hint.TLabel', foreground='#526070')
        outer = ttk.Frame(self.root, padding=22)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='BRMY Wiki Toolkit', style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer, text='整理游戏资料，保留翻译工作，生成可直接使用的 Wiki 表格。',
                  style='Hint.TLabel').pack(anchor='w', pady=(4, 14))
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill='both', expand=True)
        main = ttk.Frame(self.tabs, padding=16)
        advanced = ttk.Frame(self.tabs, padding=16)
        details = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(main, text='生成资料')
        self.tabs.add(advanced, text='输入与高级设置')
        self.tabs.add(details, text='运行详情')
        source = ttk.Frame(main)
        source.pack(fill='x', pady=(0, 12))
        ttk.Label(source, text='资源来源').pack(side='left', padx=(0, 10))
        self.mode_box = ttk.Combobox(source, textvariable=self.mode, values=list(MODES),
                                     state='readonly', width=22)
        self.mode_box.pack(side='left')
        self.mode_box.bind('<<ComboboxSelected>>', lambda event: self._mode_changed())
        self.inputs.append(self.mode_box)
        self.mode_hint = ttk.Label(main, style='Hint.TLabel', wraplength=800)
        self.mode_hint.pack(anchor='w', pady=(0, 12))
        tasks = ttk.LabelFrame(main, text='要生成什么', padding=12)
        tasks.pack(fill='x')
        for index, (name, label) in enumerate(TASKS.items()):
            button = ttk.Checkbutton(tasks, text=label, variable=self.selected[name])
            button.grid(row=index // 4, column=index % 4, sticky='w', padx=(0, 18), pady=7)
            self.inputs.append(button)
        for column in range(4):
            tasks.columnconfigure(column, weight=1)
        options = ttk.Frame(main)
        options.pack(fill='x', pady=10)
        check = ttk.Checkbutton(options, text='同步卡牌语音（正式资源任务可选）', variable=self.include_card_audio)
        self.card_audio_check = check
        check.pack(side='left')
        self.inputs.append(check)
        self._path_row(main, '输出到', 'output', directory=True)
        controls = ttk.Frame(main)
        controls.pack(fill='x', pady=(10, 12))
        self.plan_button = ttk.Button(controls, text='检查所需资源', command=lambda: self.start(True))
        self.plan_button.pack(side='left')
        self.start_button = ttk.Button(controls, text='同步并生成', command=lambda: self.start(False))
        self.start_button.pack(side='left', padx=10)
        self.cancel_button = ttk.Button(controls, text='取消', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left')
        self.progress = ttk.Progressbar(main, mode='determinate')
        self.progress.pack(fill='x')
        ttk.Label(main, textvariable=self.status, wraplength=820).pack(anchor='w', pady=(7, 10))
        result = ttk.Frame(main)
        result.pack(fill='both', expand=True)
        self.results = ttk.Treeview(result, columns=('name', 'task', 'status'), show='headings', height=5)
        for name, label, width in [('name', '本次文件', 430), ('task', '资料', 180), ('status', '状态', 100)]:
            self.results.heading(name, text=label)
            self.results.column(name, width=width, minwidth=70)
        self.results.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(result, orient='vertical', command=self.results.yview)
        scroll.pack(side='right', fill='y')
        self.results.configure(yscrollcommand=scroll.set)
        self.results.bind('<Double-1>', lambda event: self.open_selected())
        actions = ttk.Frame(main)
        actions.pack(fill='x', side='bottom', before=result, pady=(8, 0))
        ttk.Button(actions, text='打开选中文件', command=self.open_selected).pack(side='left')
        ttk.Button(actions, text='打开输出目录', command=self.open_output).pack(side='left', padx=8)
        ttk.Label(actions, text='审计信息请查看“运行详情”。', style='Hint.TLabel').pack(side='right')
        ttk.Label(advanced, text='本地资源可单独使用；在线模式自动取得任务所需数据。',
                  style='Hint.TLabel').pack(anchor='w', pady=(0, 10))
        add = ttk.Button(advanced, text='添加并识别本地文件…', command=self.add_local_file)
        add.pack(anchor='w', pady=(0, 10))
        self.inputs.append(add)
        self._path_row(advanced, 'Masterdata', 'masterdata')
        self._path_row(advanced, 'ACB 音频目录', 'audio', directory=True)
        self._path_row(advanced, '歌词 / 脚本 / 谱面', 'source', allow_folder=True)
        self._path_row(advanced, '旧卡牌工作簿', 'old_workbook')
        self._path_row(advanced, '资源缓存', 'cache', directory=True)
        for label, name in [('生日轮次（可空）', 'cycle'), ('语音主体（可空）', 'subject'),
                            ('近年截止 YYYY-MM-DD', 'recent_year'), ('指定线上资源（分号分隔）', 'resource_keys')]:
            self._path_row(advanced, label, name, picker=False)
        ttk.Label(advanced, text='本地模式不会联网。正式服离线模式只使用已有缓存；缺失资源会明确报错。\n'
                  '检查在线资源可能下载 masterdata，用于判断卡牌所需的语音包。',
                  style='Hint.TLabel', wraplength=790).pack(anchor='w', pady=12)
        self.details = tk.Text(details, wrap='word', state='disabled', font=('Microsoft YaHei UI', 10))
        self.details.pack(fill='both', expand=True)

    def _path_row(self, parent, label, name, *, directory=False, allow_folder=False, picker=True):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=5)
        ttk.Label(row, text=label, width=25 if parent == self.tabs.nametowidget(self.tabs.tabs()[1]) else 9).pack(side='left')
        entry = ttk.Entry(row, textvariable=self.paths[name])
        entry.pack(side='left', fill='x', expand=True)
        self.inputs.append(entry)
        if picker:
            button = ttk.Button(row, text='选择…', width=8, command=lambda: self.pick(name, directory))
            button.pack(side='left', padx=(7, 0))
            self.inputs.append(button)
            if allow_folder:
                button = ttk.Button(row, text='文件夹…', width=8, command=lambda: self.pick(name, True))
                button.pack(side='left', padx=(5, 0))
                self.inputs.append(button)

    def pick(self, name, directory=False):
        path = filedialog.askdirectory(parent=self.root) if directory else filedialog.askopenfilename(parent=self.root)
        if path:
            self.paths[name].set(path)

    def add_local_file(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[
            ('游戏资料与工作簿', '*.s2b *.json *.s2blyrics *.s2bscript *.s2bchart *.xlsx'), ('所有文件', '*.*')])
        if not path:
            return
        suffix = Path(path).suffix.lower()
        if suffix in {'.s2b', '.json'}:
            self.paths['masterdata'].set(path)
        elif suffix == '.xlsx':
            self.paths['old_workbook'].set(path)
            self.selected['card_update'].set(True)
            self.selected['cards'].set(False)
        elif suffix in {'.s2blyrics', '.s2bscript', '.s2bchart'}:
            self.paths['source'].set(path)
            task = {'.s2blyrics': 'lyrics', '.s2bscript': 'scripts', '.s2bchart': 'charts'}[suffix]
            for name, variable in self.selected.items():
                variable.set(name == task)
        else:
            self.status.set('尚未识别该文件类型，请在输入设置中指定。')
            return
        self.mode.set('使用本地资源')
        self._mode_changed()
        self.status.set(f'已添加 {Path(path).name}；生成时会校验文件内容。')

    def _mode_changed(self):
        mode = MODES.get(self.mode.get(), 'online')
        self.mode_hint.configure(text={
            'online': '从正式资源清单同步本次所需数据；已有且校验通过的缓存会复用。',
            'offline': '只使用已验证的正式资源缓存，不检查线上更新。',
            'local': '请在“输入与高级设置”中添加本地资源；整个流程不联网。',
        }[mode])
        self.start_button.configure(text='生成资料' if mode == 'local' else '同步并生成')
        self.card_audio_check.configure(state='disabled' if mode == 'local' else 'normal')

    def request(self):
        values = {name: variable.get().strip() for name, variable in self.paths.items()}
        values['resource_keys'] = [key.strip() for key in values['resource_keys'].split(';') if key.strip()]
        return JobRequest(MODES.get(self.mode.get(), ''), [name for name, value in self.selected.items() if value.get()],
                          include_card_audio=self.include_card_audio.get(), **values).validate()

    def start(self, plan_only=False):
        if self.worker and self.worker.is_alive():
            return
        try:
            request = self.request()
        except ValueError as error:
            self.status.set(str(error))
            return
        self.active_request = request
        self.last_result = None
        self.results.delete(*self.results.get_children())
        self.artifacts.clear()
        self._log('', clear=True)
        self.cancel_event.clear()
        self.progress.configure(value=0, maximum=100)
        self.status.set('正在检查资源…' if plan_only else '正在开始任务…')
        self._busy(True)
        try:
            self._save_settings()
        except OSError as error:
            self._log(f'设置未保存：{error}')
        def work():
            try:
                result = self.backend(request, plan_only, self.cancel_event.is_set,
                                      lambda event: self.queue.put(('progress', event)))
            except Exception as error:
                result = {'status': 'FAIL', 'artifacts': [], 'errors': [f'{type(error).__name__}: {error}']}
            self.queue.put(('done', result))
        self.worker = Thread(target=work, name='wiki-job', daemon=False)
        self.worker.start()

    def _busy(self, busy):
        for widget in self.inputs:
            widget.configure(state='disabled' if busy else ('readonly' if widget is self.mode_box else 'normal'))
        self.plan_button.configure(state='disabled' if busy else 'normal')
        self.start_button.configure(state='disabled' if busy else 'normal')
        self.cancel_button.configure(state='normal' if busy else 'disabled')
        if not busy:
            self._mode_changed()

    def cancel(self):
        self.cancel_event.set()
        self.cancel_button.configure(state='disabled')
        self.status.set('正在取消；当前解析步骤结束后停止。')

    def _poll(self):
        try:
            while True:
                kind, value = self.queue.get_nowait()
                if kind == 'progress':
                    if self.cancel_event.is_set():
                        continue
                    stage = value.get('stage')
                    label = {'catalog': '读取正式资源目录', 'masterdata': '准备基础数据',
                             'plan': '资源计划已建立', 'download': '同步资源', 'generate': '生成资料'}.get(stage, stage)
                    if stage == 'download':
                        total, index = value.get('total', 0), value.get('index', 0)
                        self.progress.configure(maximum=max(1, total), value=index)
                        label += f' {index}/{total}'
                    elif value.get('domain'):
                        label += '：' + TASKS.get(value['domain'], value['domain'])
                    self.status.set(label)
                else:
                    self._complete(value)
                    if self.closing:
                        self.root.destroy()
                        return
        except Empty:
            pass
        self.root.after(100, self._poll)

    def _complete(self, result):
        self.last_result = result
        self._busy(False)
        status = result.get('status', 'FAIL')
        if status == 'PLANNED':
            count = len(result.get('plan', {}).get('resources', []))
            self.status.set(f'资源计划已建立，共 {count} 个资源。可开始同步并生成。' if self.active_request.mode != 'local'
                            else '本地输入路径已检查；可开始生成并校验数据。')
        else:
            labels = {'PASS': '生成完成', 'PASS_WITH_WARNINGS': '生成完成，但有信息需要核对', 'FAIL': '任务未完整完成'}
            if self.cancel_event.is_set():
                label = '任务已取消'
            else:
                label = labels.get(status, status)
            wiki = [a for a in result.get('artifacts', []) if a['kind'] == 'wiki'
                    or (a['domain'] in {'scripts', 'charts'} and a['path'].endswith('.json'))]
            self.status.set(f'{label} · 本次 {len(wiki)} 个文件，请核对状态。详情见“运行详情”。')
            for index, artifact in enumerate(wiki):
                row = str(index)
                self.artifacts[row] = artifact
                self.results.insert('', 'end', iid=row, values=(Path(artifact['path']).name,
                                    TASKS.get(artifact['domain'], artifact['domain']),
                                    '不完整' if artifact.get('domain_status') == 'FAIL' else '已生成'))
        if result.get('warnings') or result.get('errors'):
            self._log('需要核对：')
            for issue in [*result.get('errors', []), *result.get('warnings', [])]:
                if isinstance(issue, dict):
                    issue = issue.get('warning') or issue.get('error') or json.dumps(issue, ensure_ascii=False)
                self._log('• ' + str(issue))
            self._log('\n源资料缺项不会自动补成完整数据。\n')
        self._log('本次产物与详细记录：\n' + json.dumps(result, ensure_ascii=False, indent=2))

    def _log(self, text, clear=False):
        self.details.configure(state='normal')
        if clear:
            self.details.delete('1.0', 'end')
        self.details.insert('end', text + '\n')
        self.details.configure(state='disabled')

    def open_selected(self):
        selected = self.results.selection()
        if not selected:
            self.status.set('请先选择本次生成的文件。')
            return
        self._open(Path(self.artifacts[selected[0]]['path']))

    def open_output(self):
        self._open(Path(self.active_request.output if self.active_request else self.paths['output'].get()))

    def _open(self, path):
        try:
            if not path.exists():
                raise FileNotFoundError('文件或目录不存在')
            if path.is_file() and path.suffix.lower() not in {'.xlsx', '.lrc', '.json', '.md'}:
                raise ValueError('不支持打开此文件类型')
            os.startfile(str(path.resolve()))
        except (OSError, ValueError) as error:
            self.status.set(f'无法打开：{error}')

    def _save_settings(self):
        from .resources import atomic_json
        atomic_json(self.settings_path, {'mode': self.mode.get(), 'paths': {k: v.get() for k, v in self.paths.items()},
                    'tasks': [k for k, v in self.selected.items() if v.get()], 'card_audio': self.include_card_audio.get()})

    def _restore(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding='utf-8'))
            if data.get('mode') in MODES:
                self.mode.set(data['mode'])
            for key, value in data.get('paths', {}).items():
                if key in self.paths and isinstance(value, str):
                    self.paths[key].set(value)
            if isinstance(data.get('tasks'), list):
                for key, variable in self.selected.items():
                    variable.set(key in data['tasks'])
            self.include_card_audio.set(bool(data.get('card_audio', True)))
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def close(self):
        if self.worker and self.worker.is_alive():
            self.closing = True
            self.cancel()
        else:
            self.root.destroy()


def main(initial_path=None):
    root = tk.Tk()
    app = ToolkitApp(root)
    if initial_path:
        app.mode.set('使用本地资源')
        app.paths['masterdata'].set(str(Path(initial_path).resolve()))
        app._mode_changed()
    root.mainloop()


def self_test():
    """Exercise bundled Tcl/Tk construction without showing or controlling a window."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix='brmy-gui-smoke-') as directory:
        root = tk.Tk()
        root.withdraw()
        try:
            app = ToolkitApp(root, settings_path=Path(directory) / 'settings.json')
            root.update_idletasks()
            if len(app.tabs.tabs()) != 3 or not app.start_button.winfo_exists():
                raise RuntimeError('GUI widget construction failed')
            return {'status': 'PASS', 'scope': 'hidden-widget-construction',
                    'tk_version': str(root.tk.call('info', 'patchlevel')),
                    'tasks': list(TASKS), 'tabs': 3}
        finally:
            root.destroy()


if __name__ == '__main__':
    main()
