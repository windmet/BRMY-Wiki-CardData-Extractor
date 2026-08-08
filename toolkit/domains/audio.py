"""CRI ACB 音频清单与语音文本提取。

该模块只负责把音频资源整理成稳定索引；卡牌、生日等业务模块按需消费索引，
避免把二进制解析逻辑继续堆进 masterdata 提取流程。
"""
from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime

from ..core.exporter import write_xlsx
from ..core.scanner import save_json
from ..core.cri_utf import CriUtfError, extract_acb_cue_rows


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

OUTPUT_DIRECTORY_NAMES = {"json_output", "xlsx_output"}


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


def run(input_path=None):
    input_path = os.path.abspath(input_path or os.getcwd())
    if not os.path.isdir(input_path):
        raise ValueError(f"音频输入必须是目录: {input_path}")

    json_dir = os.path.join(input_path, "json_output")
    xlsx_dir = os.path.join(input_path, "xlsx_output")
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(xlsx_dir, exist_ok=True)

    print(f"[*] 扫描 ACB 音频目录: {input_path}")
    inventory = _build_inventory(input_path)
    cards, warnings = scan_card_voices(input_path)
    all_text, unstable = _scan_all_text_metadata(input_path)

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
    for card_id, card in cards.items():
        for entry in card["Entries"]:
            card_rows.append([
                card_id, card["AcbFile"], entry["CueName"], entry["Title"],
                entry["TextHtml"], entry["HasText"], card["StableRead"],
            ])
    write_xlsx(
        card_rows,
        os.path.join(xlsx_dir, "card_voice_texts.xlsx"),
        ["卡牌ID", "ACB文件", "Cue名", "标题", "日文台词", "是否有文本", "读取时文件稳定"],
        sheet_title="card_voice_texts",
        col_widths={"A": 12, "B": 28, "C": 24, "D": 22, "E": 60, "F": 14, "G": 18},
        wrap_cols=[4],
    )

    text_rows = [
        [
            item["AcbFile"], item["Category"], item["MetadataNo"],
            item["CueName"], item["CueIndex"], item["CueId"], item["MatchStatus"],
            item["Title"], item["TextHtml"], item["HasText"], item["StableRead"],
        ]
        for item in all_text
    ]
    write_xlsx(
        text_rows,
        os.path.join(xlsx_dir, "voice_texts.xlsx"),
        [
            "ACB文件", "分类", "元数据序号", "Cue名", "Cue索引", "Cue ID",
            "匹配方式", "标题", "日文台词", "是否有文本", "读取时文件稳定",
        ],
        sheet_title="voice_texts",
        col_widths={
            "A": 34, "B": 20, "C": 14, "D": 28, "E": 12, "F": 12,
            "G": 24, "H": 30, "I": 70, "J": 14, "K": 18,
        },
        wrap_cols=[8],
    )

    print(
        f"[+] 音频清单 {inventory['Summary']['FileCount']} 个文件；"
        f"卡面语音 {len(cards)} 包；可读文本 {text_index['Summary']['TextCount']} 条"
    )
    if warnings or unstable:
        print(f"[!] 扫描警告 {len(warnings)} 条，读取期间变化文件 {len(unstable)} 个")
    return input_path
