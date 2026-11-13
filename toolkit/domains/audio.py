"""CRI ACB 音频清单与语音文本提取。

二进制扫描提供稳定索引，供卡牌、生日等业务模块消费；run 导出时再关联 masterdata，
补齐卡牌名称、角色和逐句说话人，身份关联不改变底层解析结果。
"""
from __future__ import annotations

import os
from ..core.output import output_directory, record_warning
import re
from collections import Counter
from datetime import datetime

from ..core.exporter import write_workbook
from ..core.console import safe_print
from ..core.scanner import save_json
from ..core.cri_utf import CriUtfError, extract_acb_cue_rows, extract_acb_cue_clips


CARD_FILE_RE = re.compile(r"^voice_(\d+)\.acb$", re.IGNORECASE)
METADATA_RE = re.compile(rb"title:\{(.*?)\}text:\{(.*)\}", re.DOTALL)

CARD_TITLE_TO_CUE = {
    "ホームボイス①": "card_vo_home_1",
    "ホームボイス②": "card_vo_home_2",
    "ホームボイス③": "card_vo_home_3",
    "ホームボイス④": "card_vo_home_4",
    "ホームボイス⑤": "card_vo_home_5",
    "スキルボイス": "card_vo_skill",
    "コンビボイス": "card_vo_skill_combi",
    "ガチャボイス": "card_vo_gacha",
}

CARD_CUE_ORDER = {
    "card_vo_home_1": 1,
    "card_vo_home_2": 2,
    "card_vo_home_3": 3,
    "card_vo_home_4": 4,
    "card_vo_home_5": 5,
    "card_vo_skill": 10,
    "card_vo_skill_combi": 20,
    "card_vo_gacha": 30,
}

OUTPUT_DIRECTORY_NAMES = {"json_output", "xlsx_output", "audit_output", "wiki_output"}


def text_to_html(text):
    """把游戏文本换行转换成 Wiki 可直接使用的 ``<br>``。"""
    if not text:
        return ""
    return text.replace("\\n", "<br>").replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")


def _read_stable_bytes(path):
    """读取可能仍在下载的文件；若读取期间发生变化则重试一次。"""
    last_data = None
    for _ in range(2):
        before = os.stat(path)
        with open(path, "rb") as stream:
            data = stream.read()
        after = os.stat(path)
        last_data = data
        if before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns:
            return data, True
    return last_data, False


def extract_text_metadata(path):
    """提取 ACB 文本；优先使用 @UTF cue 关系，旧文件回退到字符串池。"""
    data, stable = _read_stable_bytes(path)
    try:
        cue_rows = extract_acb_cue_rows(data)
    except CriUtfError:
        cue_rows = []

    entries = []
    for cue in cue_rows:
        user_data = cue.get("UserData", "")
        if not isinstance(user_data, str):
            continue
        match = re.fullmatch(r"title:\{(.*?)\}text:\{(.*)\}", user_data, re.DOTALL)
        if not match:
            continue
        entries.append({
            "CueName": cue.get("CueName", ""),
            "CueIndex": cue.get("CueIndex"),
            "CueId": cue.get("CueId"),
            "MatchStatus": "matched_by_acb_utf",
            "Title": match.group(1),
            "Text": match.group(2),
        })

    if entries:
        return entries, stable

    for chunk in data.split(b"\x00"):
        if b"title:{" not in chunk or b"}text:{" not in chunk:
            continue
        match = METADATA_RE.search(chunk)
        if match:
            entries.append({
                "Title": match.group(1).decode("utf-8", errors="replace"),
                "Text": match.group(2).decode("utf-8", errors="replace"),
                "MatchStatus": "matched_by_title_fallback",
            })
    return entries, stable


def classify_acb(filename):
    stem = os.path.splitext(os.path.basename(filename))[0].lower()
    if re.fullmatch(r"voice_\d+", stem):
        return "card_voice"
    if stem.startswith(("event_voice_story_", "voice_story_", "main_story_voice_")):
        return "story_voice"
    if stem.startswith("voice_") or stem.startswith("local_voice"):
        return "character_voice"
    if stem.startswith("bgm_") or stem.endswith("_bgm"):
        return "bgm"
    if stem.startswith("puzzle") or stem.endswith("_se"):
        return "sound_effect"
    if re.fullmatch(r"(?:[a-z]{2,4}|ps2)_\d+(?:_inf)?", stem) or stem.startswith(("rmx_", "sanrio_")):
        return "music_package"
    return "other"


def _walk_source_files(input_path):
    for base, directories, filenames in os.walk(input_path):
        directories[:] = [
            name for name in directories
            if name.lower() not in OUTPUT_DIRECTORY_NAMES
        ]
        for filename in sorted(filenames):
            yield base, filename


def _card_entry(metadata, index):
    title = metadata["Title"]
    cue_name = metadata.get("CueName") or CARD_TITLE_TO_CUE.get(title, f"metadata_{index + 1}")
    text = metadata["Text"]
    return {
        "CueName": cue_name,
        "CueIndex": metadata.get("CueIndex"),
        "CueId": metadata.get("CueId"),
        "MatchStatus": metadata.get("MatchStatus", "matched_by_title_fallback"),
        "Order": _cue_order(cue_name, index),
        "Title": title,
        "Text": text,
        "TextHtml": text_to_html(text),
        "HasText": bool(text),
    }


def _cue_order(cue_name, fallback_index=0):
    if cue_name in CARD_CUE_ORDER:
        return CARD_CUE_ORDER[cue_name]
    match = re.fullmatch(r"card_vo_home_(\d+)", cue_name or "")
    if match:
        return int(match.group(1))
    match = re.fullmatch(r"card_vo_skill_(\d+)", cue_name or "")
    if match:
        return 10 + int(match.group(1)) / 1000
    return 100 + fallback_index


def scan_card_voices(input_path):
    """扫描 ``voice_<cardId>.acb``，返回可供 cards 模块直接关联的字典。"""
    input_path = os.path.abspath(input_path)
    cards = {}
    warnings = []

    for base, filename in _walk_source_files(input_path):
        match = CARD_FILE_RE.match(filename)
        if not match:
            continue
        path = os.path.join(base, filename)
        if os.path.getsize(path) == 0:
            warnings.append(f"空文件，已跳过: {os.path.relpath(path, input_path)}")
            continue
        try:
            metadata, stable = extract_text_metadata(path)
        except OSError as exc:
            warnings.append(f"读取失败: {os.path.relpath(path, input_path)} ({exc})")
            continue

        card_id = int(match.group(1))
        relative_path = os.path.relpath(path, input_path)
        entries = [_card_entry(item, i) for i, item in enumerate(metadata)]
        entries.sort(key=lambda item: item["Order"])
        record = {
            "CharacterCardId": card_id,
            "AcbFile": relative_path,
            "FileSize": os.path.getsize(path),
            "StableRead": stable,
            "Entries": entries,
        }

        key = str(card_id)
        if key in cards:
            previous = cards[key]
            warnings.append(
                f"卡牌 {card_id} 存在重复 ACB: {previous['AcbFile']} / {relative_path}"
            )
            if record["FileSize"] <= previous["FileSize"]:
                continue
        cards[key] = record

    cards = {key: cards[key] for key in sorted(cards, key=int)}
    return cards, warnings


def _build_inventory(input_path):
    extensions = Counter()
    categories = Counter()
    files = []
    total_size = 0

    for base, filename in _walk_source_files(input_path):
        path = os.path.join(base, filename)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        extension = os.path.splitext(filename)[1].lower() or "(none)"
        category = classify_acb(filename) if extension == ".acb" else "support_file"
        extensions[extension] += 1
        categories[category] += 1
        total_size += stat.st_size
        files.append({
            "Path": os.path.relpath(path, input_path),
            "Extension": extension,
            "Category": category,
            "Size": stat.st_size,
            "ModifiedTime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })

    return {
        "SourceRoot": input_path,
        "GeneratedAt": datetime.now().isoformat(timespec="seconds"),
        "Summary": {
            "FileCount": len(files),
            "TotalSize": total_size,
            "Extensions": dict(sorted(extensions.items())),
            "Categories": dict(sorted(categories.items())),
        },
        "Files": files,
    }


def _scan_all_text_metadata(input_path):
    records = []
    unstable = []
    for base, filename in _walk_source_files(input_path):
        if not filename.lower().endswith(".acb"):
            continue
        path = os.path.join(base, filename)
        try:
            if os.path.getsize(path) == 0:
                continue
            metadata, stable = extract_text_metadata(path)
        except OSError:
            continue
        if not stable:
            unstable.append(os.path.relpath(path, input_path))
        category = classify_acb(filename)
        for index, item in enumerate(metadata, start=1):
            records.append({
                "AcbFile": os.path.relpath(path, input_path),
                "Category": category,
                "MetadataNo": index,
                "CueName": item.get("CueName", ""),
                "CueIndex": item.get("CueIndex"),
                "CueId": item.get("CueId"),
                "MatchStatus": item.get("MatchStatus", ""),
                "Title": item["Title"],
                "Text": item["Text"],
                "TextHtml": text_to_html(item["Text"]),
                "HasText": bool(item["Text"]),
                "StableRead": stable,
            })
    return records, unstable


def run(input_path=None, *, session=None):
    input_path = os.path.abspath(input_path or os.getcwd())
    if not os.path.isdir(input_path):
        raise ValueError(f"音频输入必须是目录: {input_path}")

    json_dir = output_directory("audit", os.path.join(input_path, "audit_output"))
    xlsx_dir = output_directory("wiki", os.path.join(input_path, "xlsx_output"))
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(xlsx_dir, exist_ok=True)

    safe_print(f"[*] 扫描 ACB 音频目录: {input_path}")
    inventory = _build_inventory(input_path)
    cards, warnings = scan_card_voices(input_path)
    all_text, unstable = _scan_all_text_metadata(input_path)

    from .audio_labels import AudioLabels, voice_category
    labels = AudioLabels(session.tables if session else None)
    clip_evidence = {}

    def clips(relative):
        if relative not in clip_evidence:
            try:
                data, stable = _read_stable_bytes(os.path.join(input_path, relative))
                clip_evidence[relative] = {'Stable': stable, 'Counts': {
                    cue['CueName']: len(cue['Clips']) for cue in extract_acb_cue_clips(data)
                    if not cue.get('UnknownCommands')}}
            except (OSError, CriUtfError) as error:
                clip_evidence[relative] = {'Stable': False, 'Counts': {}, 'Error': str(error)}
        return clip_evidence[relative]

    for card_id, card in cards.items():
        card.update(labels.card(int(card_id)))
        card['ClipEvidence'] = clips(card['AcbFile'])
        for entry in card['Entries']:
            entry['ClipCount'] = card['ClipEvidence']['Counts'].get(entry['CueName'])
            entry['Identity'] = labels.label(card['AcbFile'], entry['CueName'],
                stable=card['StableRead'], match_status=entry['MatchStatus'],
                clip_count=entry['ClipCount'] if card['ClipEvidence']['Stable'] else None)
            entry['VoiceCategory'] = voice_category(entry['CueName'], 'card_voice')
    for item in all_text:
        cue = item['CueName'] or (CARD_TITLE_TO_CUE.get(item['Title'], '')
                                  if item['Category'] == 'card_voice' else '')
        clip_info = clips(item['AcbFile']) if item['Category'] == 'card_voice' else None
        item['ClipCount'] = clip_info['Counts'].get(cue) if clip_info and clip_info['Stable'] else None
        item['Identity'] = labels.label(item['AcbFile'], cue, stable=item['StableRead'],
                                       match_status=item['MatchStatus'], clip_count=item['ClipCount'])
        item['VoiceCategory'] = voice_category(cue, item['Category'])

    card_index = {
        "SourceRoot": input_path,
        "GeneratedAt": datetime.now().isoformat(timespec="seconds"),
        "Summary": {
            "CardFileCount": len(cards),
            "MetadataCount": sum(len(card["Entries"]) for card in cards.values()),
            "TextCount": sum(
                entry["HasText"] for card in cards.values() for entry in card["Entries"]
            ),
        },
        "Warnings": warnings,
        "Cards": cards,
    }
    text_index = {
        "SourceRoot": input_path,
        "GeneratedAt": datetime.now().isoformat(timespec="seconds"),
        "Summary": {
            "MetadataCount": len(all_text),
            "TextCount": sum(item["HasText"] for item in all_text),
            "UnstableFiles": unstable,
        },
        "Entries": all_text,
    }

    save_json(inventory, os.path.join(json_dir, "Audio_Inventory.json"))
    save_json(card_index, os.path.join(json_dir, "Card_Voice_Index.json"))
    save_json(text_index, os.path.join(json_dir, "Voice_Text_Index.json"))

    card_rows = []
    for card in cards.values():
        for entry in card['Entries']:
            if not entry['HasText']:
                continue
            identity = entry['Identity']
            card_rows.append([identity['CharacterCardId'], identity['CharacterCardName'],
                identity['CardCharacterNames'], identity['Speaker'], entry['VoiceCategory'], entry['Title'],
                text_to_html(entry['Text']).replace('<br>', '\n'), '', entry['CueName'], card['AcbFile'],
                identity['Status'], identity['Note']])
    write_workbook(os.path.join(xlsx_dir, 'card_voice_texts.xlsx'), [{
        'title': '卡牌语音', 'headers': ['卡牌编号', '卡牌名', '卡牌角色名', '说话人', '语音分类', '标题',
                                       '日文台词', '中文翻译', '语音标识', '资源文件', '核对状态', '说明'],
        'rows': card_rows, 'col_widths': {'A': 12, 'B': 32, 'C': 26, 'D': 18, 'E': 16, 'F': 24,
                                        'G': 65, 'H': 50, 'I': 28, 'J': 40, 'K': 12, 'L': 55},
        'wrap_cols': [3, 7, 8, 12],
    }])
    text_rows = []
    ordered_text = sorted(all_text, key=lambda item: (
        tuple(item['Identity']['SpeakerCharacterIds']) or (999999,),
        item['Identity']['CharacterCardId'] or 0, item['VoiceCategory'],
        item['CueName'], item['AcbFile'], item['MetadataNo']))
    for item in ordered_text:
        if not item['HasText']:
            continue
        identity = item['Identity']
        text_rows.append([identity['Speaker'], item['VoiceCategory'], item['Title'],
            text_to_html(item['Text']).replace('<br>', '\n'), '', identity['CharacterCardId'],
            identity['CharacterCardName'], identity['CardCharacterNames'], item['CueName'], item['AcbFile'],
            identity['Status'], identity['Note']])
    write_workbook(os.path.join(xlsx_dir, 'voice_texts.xlsx'), [{
        'title': '语音文本', 'headers': ['说话人', '语音分类', '标题', '日文台词', '中文翻译', '卡牌编号',
                                       '卡牌名', '卡牌角色名', '语音标识', '资源文件', '核对状态', '说明'],
        'rows': text_rows, 'col_widths': {'A': 18, 'B': 16, 'C': 24, 'D': 65, 'E': 50, 'F': 12,
                                        'G': 32, 'H': 26, 'I': 28, 'J': 40, 'K': 12, 'L': 55},
        'wrap_cols': [4, 5, 8, 12],
    }])
    unresolved = sum(item['HasText'] and item['Identity']['Status'] != '正常' for item in all_text)
    if unresolved:
        record_warning(f'语音有 {unresolved} 条说话人或文本关联待核对，详见语音表的核对状态和说明列')

    safe_print(
        f"[+] 音频清单 {inventory['Summary']['FileCount']} 个文件；"
        f"卡面语音 {len(cards)} 包；可读文本 {text_index['Summary']['TextCount']} 条"
    )
    if warnings or unstable:
        safe_print(f"[!] 扫描警告 {len(warnings)} 条，读取期间变化文件 {len(unstable)} 个")
        record_warning(f"扫描警告 {len(warnings)} 条，读取期间变化文件 {len(unstable)} 个")
    return input_path
