"""Native desktop front end for the same local/production generation services."""
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Event
from datetime import date
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, font as tkfont
from .core.feedback import feedback_groups, issue_text, artifact_needs_review

TASKS = {
    'groove': 'GROOVE 配队数据',
    'campaign_voices': '活动语音 / Shuffle Talk',
    'cards': '卡牌表', 'events': '活动总表', 'home_voices': '主页 / 生日祝福',
    'birthday': '生日庆典台词', 'card_update': '更新已有卡表', 'items': '道具图鉴',
    'music': '音乐资料', 'snap': 'Snap 文案', 'missions': '隐藏任务',
    'lyrics': '歌词', 'scripts': '剧情脚本', 'charts': 'OJT Chart（本地）', 'audio': '通用语音文本',
    'ojt': 'OJT 活动档案', 'birthday_archive': '年度生日档案',
    'exchange_events': '交换所·剧情活动', 'bar_events': '营业（摇酒）活动', 'vignette_events': 'Vignette 活动',
    'home_voice_duo': '双人主页台词', 'card_combi_voices': '多段协作语音（例外表）', 'story_catalog': '剧情目录', 'collections': '收藏档案',
    'puzzle_stages': '消消乐关卡', 'groove_charts': 'GROOVE 谱面', 'spin_memos': 'Spin 备忘录检索',
}
# Not a selectable task: written after every run that produced Wiki tables.
ARTIFACT_LABELS = {'review': '待核对汇总'}
TASK_GROUPS = [
    ('卡牌', ('cards', 'card_update', 'collections', 'items'),
     '更新已有卡表会保留人工列。收藏档案列出卡牌关联、奖励来源和已确认的获取入口。'),
    ('语音', ('home_voices', 'campaign_voices', 'home_voice_duo', 'card_combi_voices', 'audio'),
     '活动语音收录活动页台词和按顺序排列的 Shuffle Talk。主页 / 生日祝福来自角色 ACB；双人主页台词按搭档配对；多段协作语音单独成表。缺资源时会写明缺哪一项。'),
    ('活动', ('events', 'exchange_events', 'bar_events', 'vignette_events', 'ojt', 'charts', 'missions'),
     '活动总表是全部活动的索引（剧情章节、任务、规则）；交换所·剧情、营业（摇酒）、Vignette、OJT 各有一份玩法档案。'
     'OJT 活动档案包含轮次、关卡、奖箱和站位坐标。'),
    ('剧情与台词', ('story_catalog', 'scripts', 'birthday', 'birthday_archive', 'snap', 'spin_memos'),
     '剧情目录列出标题、解锁条件和奖励，剧情脚本解析正文。生日庆典台词按轮次整理，年度生日档案按角色和年份汇总。'),
    ('音乐', ('music', 'lyrics', 'groove_charts'), '音乐主表及可关联资源；歌词需要指定资源。GROOVE 谱面统计每首曲 A/B/C 面的音符。'),
    ('关卡', ('puzzle_stages',), '消消乐每关的通关目标、生命、步数和机关，按用途分表。'),
    ('网站数据', ('groove',), '供计算器网站使用的源数据。'),
]
PRESETS = {
    '版本更新全套': ('cards', 'collections', 'items', 'events', 'exchange_events', 'bar_events', 'vignette_events',
                'ojt', 'missions', 'story_catalog',
                'birthday', 'home_voices', 'campaign_voices', 'home_voice_duo', 'music', 'snap'),
    '只更新语音': ('home_voices', 'campaign_voices', 'home_voice_duo', 'card_combi_voices'),
    '只出活动表': ('campaign_voices', 'events', 'exchange_events', 'bar_events', 'vignette_events', 'ojt', 'missions'),
}
MODES = {'联网更新': 'online', '只用已下载缓存': 'offline'}
# Task names saved by earlier versions.
LEGACY_TASKS = {'recipes': 'bar_events'}
# Names saved by earlier versions; local files are now an advanced-page switch.
LEGACY_MODES = {'正式服在线': '联网更新', '正式服离线缓存': '只用已下载缓存', '用本地缓存': '只用已下载缓存'}
TASK_HINT = '鼠标移到任务上可查看它生成什么。'
TASK_HELP = {
    'campaign_voices': '活动页语音与 Shuffle Talk：附说话角色、对话顺序和日期状态，历史占位配置另列待核对。',
    'groove': '曲目加成、Runner 位次、Relation 与 SIDE 的源数据，供计算器网站使用。',
    'cards': '卡牌资料；联网或只用缓存时可同时填入卡面语音台词（开关在“输入与高级设置”）。',
    'card_update': '在旧卡牌工作簿上更新，人工填写的列原样保留。旧表在“输入与高级设置”里选择。',
    'collections': '服装、Mini、称号、徽章、背景和道具；获取入口列收录已确认的途径。',
    'items': '道具名称和说明；游戏数据里没有名称的道具会列入待核对汇总。',
    'events': '全部活动一览（类型、开放与结束时间），附剧情章节、活动任务和规则说明。',
    'exchange_events': '交换所活动与无奖章活动（Prequel、Travelogue、周年等）：排名奖励、兑换所商品、活动加成。',
    'bar_events': '营业（摇酒）活动：轮班、菜单与配方、材料、关卡掉落、特别营业和营业额奖励。',
    'vignette_events': 'Vignette 累积道具活动：登场角色、卡牌和累积奖励。',
    'ojt': 'OJT 活动的轮次与带教台词、关卡、奖箱、规则，以及题面上的角色站位坐标。',
    'charts': '单独解析 .s2bchart 站位文件。OJT 活动档案已包含这部分，平时选它即可。',
    'missions': '常驻隐藏任务。每期活动的任务在“活动资料”里。',
    'home_voices': '从角色 ACB 提取主页语音和生日祝福文本。',
    'home_voice_duo': '两位角色配对的双人主页台词，需要 masterdata 和角色 ACB。',
    'card_combi_voices': '一条语音含多段音频的卡牌（如三周年生日部门协作），逐段导出音频供人工听写。',
    'audio': '卡牌语音关联卡号、卡名和卡牌角色；通用语音关联说话人，支持分类筛选，无法确认的逐条标注。',
    'birthday': '生日庆典小游戏台词，按轮次分表。角色 ACB 里的生日祝福在“主页 / 生日祝福”。',
    'birthday_archive': '按角色和年份整理年度生日的登录、点击奖励、服装和台词。',
    'story_catalog': '剧情目录：标题、解锁条件和奖励。剧情正文由“剧情脚本”解析。',
    'spin_memos': 'Spin 相片备忘录：R/SR/SSR 三联合并去重，附话题对照、评论检索和角色统计。',
    'puzzle_stages': '消消乐每关 A–F 面的目标、SS 分数线、生命、步数和盘面机关。联网时会下载约两千个小文件。',
    'groove_charts': 'GROOVE（音游）已上线曲目 A/B/C 面的 BPM、时长、音符数与机关。',
    'scripts': '剧情脚本正文。联网时在“指定线上资源”填资源键；用本地文件时选文件或目录。',
    'lyrics': '歌词与时间轴。联网时在“指定线上资源”填资源键；用本地文件时选文件或目录。',
    'music': '音乐主表，附可关联的音频等资源。',
    'snap': '去重后的 Snap 文案，原始关联在审计资料里。',
}


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
        from .generate import NEEDS_MASTERDATA
        if self.mode not in {'online', 'offline', 'local'}:
            raise ValueError('请选择资源模式')
        if not self.domains or set(self.domains) - set(TASKS):
            raise ValueError('请至少选择一项要生成的资料')
        if not self.output.strip():
            raise ValueError('请选择输出目录')
        if self.cycle and (not self.cycle.isdigit() or int(self.cycle) < 1):
            raise ValueError('生日轮次应为正整数，留空则导出全部轮次')
        if self.recent_year:
            from datetime import date
            try:
                date.fromisoformat(self.recent_year)
            except ValueError:
                raise ValueError('近一年语音截止日应为 YYYY-MM-DD') from None
        if 'card_update' in self.domains and not Path(self.old_workbook).is_file():
            raise ValueError('更新已有卡表需要选择旧 Excel 工作簿')
        if self.mode != 'local':
            if not self.cache.strip():
                raise ValueError('请选择资源缓存目录')
        else:
            if set(self.domains) & NEEDS_MASTERDATA:
                if not Path(self.masterdata).is_file():
                    raise ValueError('本地任务需要选择 masterdata 文件')
            if set(self.domains) & {'home_voices', 'campaign_voices', 'home_voice_duo', 'card_combi_voices', 'audio'}:
                if not self.audio or not Path(self.audio).is_dir():
                    raise ValueError('该任务需要选择本地 ACB 音频目录')
            if self.audio and not Path(self.audio).is_dir():
                raise ValueError('本地音频目录不存在')
            if 'ojt' in self.domains and self.source:
                path = Path(self.source)
                if not (path.is_dir() or (path.is_file() and path.suffix.lower() == '.s2bchart')):
                    raise ValueError('OJT 坐标输入需要 .s2bchart 文件或目录')
            if set(self.domains) & {'puzzle_stages', 'groove_charts'}:
                if not self.source or not Path(self.source).exists():
                    raise ValueError('关卡 / 谱面任务需要选择 .s2bStage / .s2bscore 文件夹')
            if set(self.domains) & {'scripts', 'lyrics', 'charts'}:
                if not self.source or not Path(self.source).exists():
                    raise ValueError('请选择独立歌词、脚本或OJT Chart文件 / 文件夹')
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
    def __init__(self, root, *, backend=execute_job, settings_path=None, choice_loader=None):
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
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.mode = tk.StringVar(value='联网更新')
        self.use_local = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='选择需要的资料，检查资源后开始生成。')
        self.paths = {name: tk.StringVar() for name in
                      ['output', 'cache', 'masterdata', 'audio', 'source', 'old_workbook',
                       'cycle', 'subject', 'recent_year', 'resource_keys']}
        self.paths['output'].set(str(Path.home() / 'Documents/BRMYWikiOutput'))
        self.paths['cache'].set(str(app_directory() / 'cache'))
        self.selected = {name: tk.BooleanVar(value=name == 'cards') for name in TASKS}
        self.include_card_audio = tk.BooleanVar(value=True)
        self.inputs = []
        self.idle_states = {}
        if choice_loader is None:
            from .choices import load_choices as choice_loader
        self.choice_loader = choice_loader
        self.choice_cache = None
        self.choice_hint = tk.StringVar()
        self.choice_text = {name: tk.StringVar() for name in ('cycle', 'subject')}
        self.choice_maps = {name: {} for name in self.choice_text}
        self.choice_boxes = {}
        for name, variable in self.choice_text.items():
            variable.trace_add('write', lambda *args, name=name: self._choice_changed(name))
        self.recent_enabled = tk.BooleanVar(value=False)
        self.recent_parts = {key: tk.StringVar() for key in ('year', 'month', 'day')}
        self.recent_boxes = []
        self._build()
        self._restore()
        for name in self.choice_text:
            self.choice_text[name].set(self.paths[name].get())
        self._restore_recent()
        self.paths['cache'].trace_add('write', lambda *args: self.root.after(800, self.refresh_choices))
        self.refresh_choices()
        self.root.update_idletasks()
        width = min(max(980, self.root.winfo_reqwidth()), self.root.winfo_screenwidth() - 40)
        height = min(max(860, self.root.winfo_reqheight()), self.root.winfo_screenheight() - 80)
        self.root.geometry(f'{width}x{height}')
        self.root.minsize(min(width, 860), min(height, 800))
        self._mode_changed()
        self.root.after(100, self._poll)

    def _build(self):
        style = ttk.Style(self.root)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 19, 'bold'))
        style.configure('Hint.TLabel', foreground='#526070')
        style.configure('Group.TLabel', font=('Microsoft YaHei UI', 10, 'bold'))
        # ttk keeps a fixed pixel row height; at 150-200% scaling the text would be clipped.
        self.line_height = tkfont.nametofont('TkDefaultFont').metrics('linespace')
        style.configure('Treeview', rowheight=int(self.line_height * 1.5))
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='BRMY Wiki Toolkit', style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer, text='整理游戏资料，保留翻译工作，生成可直接使用的 Wiki 表格。',
                  style='Hint.TLabel').pack(anchor='w', pady=(4, 8))
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill='both', expand=True)
        main = ttk.Frame(self.tabs, padding=12)
        advanced = ttk.Frame(self.tabs, padding=16)
        details = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(main, text='生成资料')
        self.tabs.add(advanced, text='输入与高级设置')
        self.tabs.add(details, text='运行详情')
        source = ttk.Frame(main)
        source.pack(fill='x', pady=(0, 8))
        ttk.Label(source, text='资源来源').pack(side='left', padx=(0, 10))
        self.mode_box = ttk.Combobox(source, textvariable=self.mode, values=list(MODES),
                                     state='readonly', width=14)
        self.mode_box.pack(side='left')
        self.mode_box.bind('<<ComboboxSelected>>', lambda event: self._mode_changed())
        self.inputs.append(self.mode_box)
        self.mode_hint = ttk.Label(source, style='Hint.TLabel', wraplength=640)
        self.mode_hint.pack(side='left', padx=(12, 0))
        tasks = ttk.LabelFrame(main, text='要生成什么', padding=8)
        tasks.pack(fill='x')
        presets = ttk.Frame(tasks)
        presets.pack(fill='x', pady=(0, 4))
        ttk.Label(presets, text='常用组合').pack(side='left', padx=(0, 8))
        for title, names in list(PRESETS.items()) + [('清空', ())]:
            button = ttk.Button(presets, text=title, command=lambda names=names: self.apply_preset(names))
            button.pack(side='left', padx=(0, 6))
            self.inputs.append(button)
        self.task_hint = tk.StringVar(value=TASK_HINT)
        grid = ttk.Frame(tasks)
        grid.pack(fill='x')
        row = 0
        for title, names, _ in TASK_GROUPS:
            ttk.Label(grid, text=title, style='Group.TLabel').grid(row=row, column=0, sticky='nw', padx=(0, 14), pady=3)
            for index, name in enumerate(names):
                button = ttk.Checkbutton(grid, text=TASKS[name], variable=self.selected[name])
                button.grid(row=row + index // 4, column=1 + index % 4, sticky='w', padx=(0, 12), pady=3)
                button.bind('<Enter>', lambda event, name=name: self.task_hint.set(f'{TASKS[name]}：{TASK_HELP[name]}'))
                button.bind('<Leave>', lambda event: self.task_hint.set(TASK_HINT))
                self.inputs.append(button)
            row += (len(names) + 3) // 4
            ttk.Separator(grid).grid(row=row, column=0, columnspan=5, sticky='ew', pady=1)
            row += 1
        # Fixed two-line box: a hint that wrapped to a new height would shift the checkboxes under the mouse.
        hint_box = ttk.Frame(tasks, height=self.line_height * 2 + 6)
        hint_box.pack(fill='x', pady=(4, 0))
        hint_box.pack_propagate(False)
        self._wrapping_label(hint_box, textvariable=self.task_hint, style='Hint.TLabel').pack(fill='both', expand=True)
        self._path_row(main, '输出到', 'output', directory=True)
        controls = ttk.Frame(main)
        controls.pack(fill='x', pady=(8, 8))
        self.plan_button = ttk.Button(controls, text='先检查资源', command=lambda: self.start(True))
        self.plan_button.pack(side='left')
        self.start_button = ttk.Button(controls, text='同步并生成', command=lambda: self.start(False))
        self.start_button.pack(side='left', padx=10)
        self.help_button = ttk.Button(controls, text='任务说明', command=self.show_task_help)
        self.help_button.pack(side='left', padx=(0, 10))
        self.cancel_button = ttk.Button(controls, text='取消', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left')
        self.progress = ttk.Progressbar(main, mode='determinate')
        self.progress.pack(fill='x')
        self._wrapping_label(main, textvariable=self.status).pack(fill='x', pady=(5, 7))
        result = ttk.Frame(main)
        result.pack(fill='both', expand=True)
        self.results = ttk.Treeview(result, columns=('name', 'task', 'status'), show='headings', height=6)
        for name, label, width in [('name', '本次文件', 430), ('task', '资料', 180), ('status', '状态', 140)]:
            self.results.heading(name, text=label, anchor='w')
            self.results.column(name, width=width, minwidth=70, anchor='w')
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
        ttk.Label(advanced, text='平时不需要改这里：联网更新会自动取得任务所需数据。',
                  style='Hint.TLabel').pack(anchor='w', pady=(0, 10))
        local = ttk.Frame(advanced)
        local.pack(fill='x', pady=(0, 10))
        check = ttk.Checkbutton(local, text='改用本地文件（不联网）', variable=self.use_local,
                                command=self._mode_changed)
        check.pack(side='left')
        self.inputs.append(check)
        add = ttk.Button(local, text='添加并识别本地文件…', command=self.add_local_file)
        add.pack(side='left', padx=12)
        self.inputs.append(add)
        check = ttk.Checkbutton(advanced, text='卡牌表同时填入卡面语音台词（联网或只用缓存时）',
                                variable=self.include_card_audio)
        self.card_audio_check = check
        check.pack(anchor='w', pady=(0, 6))
        self.inputs.append(check)
        self._path_row(advanced, 'Masterdata', 'masterdata')
        self._path_row(advanced, 'ACB 音频目录', 'audio', directory=True)
        self._path_row(advanced, '歌词 / 脚本 / OJT Chart', 'source', allow_folder=True)
        self._path_row(advanced, '旧卡牌工作簿', 'old_workbook')
        self._path_row(advanced, '资源缓存', 'cache', directory=True)
        self._choice_row(advanced, '生日轮次', 'cycle')
        self._choice_row(advanced, '单个语音主体另出表', 'subject')
        self._date_row(advanced, '近一年语音', 'recent_year')
        self._path_row(advanced, '指定线上资源（分号分隔）', 'resource_keys', picker=False)
        ttk.Label(advanced, textvariable=self.choice_hint, style='Hint.TLabel', wraplength=1200).pack(anchor='w')
        ttk.Label(advanced, text='改用本地文件时不联网；“只用已下载缓存”只读取已校验的缓存，缺失资源会明确报错。\n'
                  '联网时“先检查资源”可能下载 masterdata，用于判断卡牌所需的语音包。\n'
                  '单个语音主体：另出一张该主体的主页 / 生日祝福表。\n'
                  '近一年语音：额外汇总截止日前 365 天的主页与生日语音。',
                  style='Hint.TLabel', wraplength=1200).pack(anchor='w', pady=12)
        self.details = tk.Text(details, wrap='word', state='disabled', font=('Microsoft YaHei UI', 10))
        self.details.pack(fill='both', expand=True)

    def _wrapping_label(self, parent, **options):
        label = ttk.Label(parent, anchor='nw', justify='left', **options)
        label.bind('<Configure>', lambda event: label.configure(wraplength=max(event.width - 4, 100)))
        return label

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

    def _choice_row(self, parent, label, name):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=5)
        ttk.Label(row, text=label, width=25).pack(side='left')
        box = ttk.Combobox(row, textvariable=self.choice_text[name], height=20)
        box.pack(side='left', fill='x', expand=True)
        self.choice_boxes[name] = box
        self.inputs.append(box)

    def _date_row(self, parent, label, name):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=5)
        ttk.Label(row, text=label, width=25).pack(side='left')
        check = ttk.Checkbutton(row, text='额外汇总，截止日', variable=self.recent_enabled,
                                command=self._sync_recent)
        check.pack(side='left')
        self.inputs.append(check)
        today = date.today()
        for key, start, end, width, value in [('year', 2023, today.year + 2, 6, today.year),
                                              ('month', 1, 12, 4, today.month), ('day', 1, 31, 4, today.day)]:
            self.recent_parts[key].set(f'{value:02d}')
            box = ttk.Spinbox(row, from_=start, to=end, width=width, format='%02.0f', wrap=key != 'year',
                              textvariable=self.recent_parts[key], command=self._sync_recent)
            box.pack(side='left', padx=(8 if key == 'year' else 2, 0))
            box.bind('<KeyRelease>', lambda event: self._sync_recent())
            ttk.Label(row, text={'year': '年', 'month': '月', 'day': '日'}[key]).pack(side='left')
            self.recent_boxes.append(box)
            self.inputs.append(box)

    def _sync_recent(self):
        enabled = self.recent_enabled.get()
        busy = bool(self.worker and self.worker.is_alive())
        for box in self.recent_boxes:
            self.idle_states[box] = 'normal' if enabled else 'disabled'
            if not busy:
                box.configure(state=self.idle_states[box])
        parts = [self.recent_parts[key].get().strip() for key in ('year', 'month', 'day')]
        self.paths['recent_year'].set('-'.join(part.zfill(2) for part in parts) if enabled else '')

    def _restore_recent(self):
        try:
            chosen = date.fromisoformat(self.paths['recent_year'].get().strip())
        except ValueError:
            chosen = None
        self.recent_enabled.set(chosen is not None)
        if chosen:
            for key, part in zip(('year', 'month', 'day'), (chosen.year, chosen.month, chosen.day)):
                self.recent_parts[key].set(f'{part:02d}')
        self._sync_recent()

    def _choice_changed(self, name):
        text = self.choice_text[name].get().strip()
        self.paths[name].set(self.choice_maps[name].get(text, text))

    def refresh_choices(self):
        """Read option lists from the cached masterdata off the UI thread (decoding takes seconds)."""
        cache = self.paths['cache'].get().strip()
        if cache == self.choice_cache:
            return
        self.choice_cache = cache
        self.choice_hint.set('正在从已下载的游戏数据读取可选项…')

        def work():
            try:
                choices = self.choice_loader(cache)
            except Exception as error:
                choices = {'error': f'{type(error).__name__}: {error}'}
            self.queue.put(('choices', (cache, choices)))
        Thread(target=work, name='wiki-choices', daemon=True).start()

    def _apply_choices(self, cache, choices):
        if cache != self.choice_cache:
            return  # An older cache path finished after the user changed it.
        lists = None
        if choices and 'error' not in choices:
            lists = {'cycle': [('', '全部轮次')] + choices['cycles'],
                     'subject': [('', '不另出表')] + choices['subjects']}
            self.choice_hint.set(f"生日轮次 {len(choices['cycles'])} 轮、语音主体 {len(choices['subjects'])} 个，"
                                 '取自最近一次下载的游戏数据。')
        elif not choices:
            self.choice_hint.set('还没有下载过游戏数据，轮次和主体暂时只能手填：先联网更新一次，之后会变成下拉框。')
        else:
            self.choice_hint.set(f"读取游戏数据失败，轮次和主体暂时只能手填：{choices['error']}")
        busy = bool(self.worker and self.worker.is_alive())
        for name, box in self.choice_boxes.items():
            current = self.paths[name].get().strip()
            options = lists[name] if lists else []
            self.choice_maps[name] = {label: value for value, label in options}
            box.configure(values=[label for _, label in options])
            self.idle_states[box] = 'readonly' if lists else 'normal'
            if not busy:
                box.configure(state=self.idle_states[box])
            label = next((label for value, label in options if value == current), None)
            if lists and label is None:
                label = options[0][1]
                if current:
                    self.choice_hint.set(self.choice_hint.get() + f'上次填写的“{current}”已不在列表中，已改回默认。')
            self.choice_text[name].set(label if lists else current)

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
        self.use_local.set(True)
        self._mode_changed()
        self.status.set(f'已添加 {Path(path).name}；生成时会校验文件内容。')

    def mode_code(self):
        return 'local' if self.use_local.get() else MODES.get(self.mode.get(), 'online')

    def apply_preset(self, names):
        for name, variable in self.selected.items():
            variable.set(name in names)
        self.task_hint.set(f'已选 {len(names)} 项。' if names else TASK_HINT)

    def _mode_changed(self):
        mode = self.mode_code()
        self.mode_hint.configure(text={
            'online': '检查正式服更新，只下载所选任务需要的资源。',
            'offline': '只用已下载过的资源，不联网。',
            'local': '已在“输入与高级设置”中改用本地文件，资源来源选项不生效。',
        }[mode])
        self.mode_box.configure(state='disabled' if mode == 'local' else 'readonly')
        self.start_button.configure(text={'online': '同步并生成', 'offline': '用缓存生成', 'local': '生成资料'}[mode])
        self.plan_button.configure(text={'online': '先检查资源', 'offline': '先检查缓存', 'local': '检查本地输入'}[mode])
        self.card_audio_check.configure(state='disabled' if mode == 'local' else 'normal')

    def show_task_help(self):
        dialog = tk.Toplevel(self.root)
        dialog.title('任务说明')
        dialog.transient(self.root)
        dialog.geometry('700x480')
        text = tk.Text(dialog, wrap='word', padx=16, pady=12)
        text.pack(fill='both', expand=True)
        for group, names, description in TASK_GROUPS:
            text.insert('end', group + '\n' + description + '\n\n')
            for name in names:
                text.insert('end', TASKS[name] + '：' + TASK_HELP[name] + '\n\n')
        text.configure(state='disabled')
        close = ttk.Button(dialog, text='关闭（Esc）', command=dialog.destroy)
        close.pack(pady=8)
        dialog.bind('<Escape>', lambda event: dialog.destroy())
        dialog.bind('<Destroy>', lambda event: self.help_button.focus_set() if event.widget == dialog else None)
        text.focus_set()

    def request(self):
        values = {name: variable.get().strip() for name, variable in self.paths.items()}
        values['resource_keys'] = [key.strip() for key in values['resource_keys'].split(';') if key.strip()]
        return JobRequest(self.mode_code(), [name for name, value in self.selected.items() if value.get()],
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
            widget.configure(state='disabled' if busy else ('readonly' if widget is self.mode_box
                                                            else self.idle_states.get(widget, 'normal')))
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
                elif kind == 'choices':
                    self._apply_choices(*value)
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
        feedback = feedback_groups(result)
        self._busy(False)
        status = result.get('status', 'FAIL')
        if status == 'PLANNED':
            count = len(result.get('plan', {}).get('resources', []))
            self.status.set(f'资源计划已建立，共 {count} 个资源。可开始同步并生成。' if self.active_request.mode != 'local'
                            else '本地输入路径已检查；可开始生成并校验数据。')
            assessment = result.get('cache_assessment')
            if self.active_request.mode != 'local' and assessment:
                next_step = ('未通过项需先在线同步。' if self.active_request.mode == 'offline'
                             else '生成时尝试取得未通过项。')
                self.status.set(f"资源共 {count} 项：已校验可用 {assessment['verified']} 项，"
                                f"未通过校验 {assessment['not_verified']} 项。{next_step}"
                                '（基础数据准备后的状态）')
        else:
            labels = {'PASS': '生成完成', 'PASS_WITH_WARNINGS': (
                '生成完成，有内容需要核对' if feedback['review'] else '生成完成，有运行提示'),
                'FAIL': '任务未完整完成'}
            if self.cancel_event.is_set():
                label = '任务已取消'
            else:
                label = labels.get(status, status)
                if status == 'FAIL':
                    self.tabs.select(2)
            wiki = [a for a in result.get('artifacts', []) if a['kind'] == 'wiki'
                    or (a['domain'] in {'scripts', 'charts'} and a['path'].endswith('.json'))]
            self.status.set(f'{label} · 本次 {len(wiki)} 个文件，请核对状态。详情见“运行详情”。')
            for index, artifact in enumerate(wiki):
                row = str(index)
                self.artifacts[row] = artifact
                self.results.insert('', 'end', iid=row, values=(Path(artifact['path']).name,
                                    TASKS.get(artifact['domain'], ARTIFACT_LABELS.get(artifact['domain'], artifact['domain'])),
                                    '不完整' if artifact.get('domain_status') == 'FAIL' else
                                    '已生成，请核对' if artifact_needs_review(artifact, feedback) else '已生成'))
        if result.get('warnings') or result.get('errors'):
            for key, heading in [('errors', '运行失败'), ('review', '内容与数据需要核对'),
                                 ('information', '资源与运行提示')]:
                if feedback[key]:
                    self._log(f'{heading}（{len(feedback[key])} 项）：')
                    for issue in feedback[key]:
                        self._log('• ' + issue_text(issue))
            if feedback['review']:
                self._log('\n以上需要核对的内容已汇总到 待核对汇总.xlsx。\n')
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
        atomic_json(self.settings_path, {'mode': self.mode.get(), 'local': self.use_local.get(), 'paths': {k: v.get() for k, v in self.paths.items()},
                    'tasks': [k for k, v in self.selected.items() if v.get()], 'card_audio': self.include_card_audio.get()})

    def _restore(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding='utf-8'))
            mode = LEGACY_MODES.get(data.get('mode'), data.get('mode'))
            if mode in MODES:
                self.mode.set(mode)
            self.use_local.set(bool(data.get('local', data.get('mode') == '使用本地资源')))
            for key, value in data.get('paths', {}).items():
                if key in self.paths and isinstance(value, str):
                    self.paths[key].set(value)
            if isinstance(data.get('tasks'), list):
                tasks = {LEGACY_TASKS.get(name, name) for name in data['tasks']}
                for key, variable in self.selected.items():
                    variable.set(key in tasks)
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
    if os.name == 'nt':
        try:  # Crisp text on scaled displays; the window sizes itself to fit.
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    app = ToolkitApp(root)
    if initial_path:
        app.use_local.set(True)
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
            app = ToolkitApp(root, settings_path=Path(directory) / 'settings.json', choice_loader=lambda cache: None)
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
