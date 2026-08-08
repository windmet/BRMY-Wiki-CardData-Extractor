"""Build Wiki-oriented home voice tables from character ACBs and masterdata."""
from __future__ import annotations

import os
import re
from collections import Counter, defaultdict

from ..core.exporter import write_workbook
from ..core.scanner import load_json, save_json
from ..core.tables import TableCatalog
from .audio import extract_text_metadata, text_to_html


CHARACTER_ACB_STEMS = {
    1: "kosaka", 2: "kise", 3: "suoh", 4: "ayato", 5: "ukyo",
    6: "hinomiya", 7: "kanno", 8: "tsukimoto", 9: "ichikawa", 10: "okiya",
    11: "fushimi", 12: "mikado", 13: "shinkai", 14: "aizawa", 15: "arima",
    16: "shido", 17: "tateshina", 18: "onda", 19: "nina", 20: "kamiya",
    21: "manami",
}
STEM_TO_CHARACTER_ID = {stem: character_id for character_id, stem in CHARACTER_ACB_STEMS.items()}
CHARACTER_PACKAGE_RE = re.compile(
    r"^voice_(?P<stem>[a-z]+?)_(?P<bucket>general|[123])\.acb$",
    re.IGNORECASE,
)
BIRTHDAY_CUE_RE = re.compile(r"^vo_home_(?P<target>\d+)_(?P<number>\d+)$")
CATEGORY_NAMES = {
    2: "玩家生日",
    3: "角色本人生日",
    4: "角色生日祝福",
    6: "期间限定",
    7: "季节",
    9: "时间问候",
    10: "主页常驻",
    11: "双人主页",
}
EXPECTED_CHARACTER_IDS = tuple(range(1, 22))


def scan_character_home_voice_packages(acb_root):
    """Read the 21 character package families and retain cue-level audit fields."""
    acb_root = os.path.abspath(acb_root)
    records = []
    warnings = []
    for base, _, filenames in os.walk(acb_root):
        for filename in sorted(filenames):
            match = CHARACTER_PACKAGE_RE.fullmatch(filename)
            if not match:
                continue
            speaker_id = STEM_TO_CHARACTER_ID.get(match.group("stem").lower())
            if speaker_id is None:
                continue
            path = os.path.join(base, filename)
            try:
                if os.path.getsize(path) == 0:
                    warnings.append(f"空文件，已跳过: {os.path.relpath(path, acb_root)}")
                    continue
                metadata, stable = extract_text_metadata(path)
            except OSError as exc:
                warnings.append(f"读取失败: {os.path.relpath(path, acb_root)} ({exc})")
                continue

            relative_path = os.path.relpath(path, acb_root)
            bucket_name = match.group("bucket").lower()
            bucket = 0 if bucket_name == "general" else int(bucket_name)
            for item in metadata:
                cue_name = item.get("CueName", "")
                if not cue_name.startswith("vo_home_") or cue_name.startswith("vo_home_duo_"):
                    continue
                records.append({
                    "SpeakerCharacterId": speaker_id,
                    "AcbFile": relative_path,
                    "AcbBucket": bucket,
                    "CueName": cue_name,
                    "CueIndex": item.get("CueIndex"),
                    "CueId": item.get("CueId"),
                    "TitleRaw": item.get("Title", ""),
                    "TextRaw": item.get("Text", ""),
                    "TextWiki": text_to_html(item.get("Text", "")),
                    "MetadataMatchStatus": item.get("MatchStatus", ""),
                    "StableRead": stable,
                })
    records.sort(
        key=lambda row: (
            row["SpeakerCharacterId"], row["CueName"], row["AcbBucket"], row["AcbFile"]
        )
    )
    deduplicated = []
    for record in records:
        if (
            deduplicated
            and record["SpeakerCharacterId"] == deduplicated[-1]["SpeakerCharacterId"]
            and record["CueName"] == deduplicated[-1]["CueName"]
        ):
            deduplicated[-1].setdefault("AlternateAcbFiles", []).append(record["AcbFile"])
            continue
        record["AlternateAcbFiles"] = []
        deduplicated.append(record)
    deduplicated.sort(key=lambda row: (row["CueName"], row["SpeakerCharacterId"], row["AcbFile"]))
    return deduplicated, warnings


def _active_rows(tables, name):
    return [row for row in tables.rows(name) if isinstance(row, dict) and row.get("IsActive", True)]


def _mode(values):
    values = [value for value in values if value]
    if not values:
        return ""
    counts = Counter(values)
    return min(counts, key=lambda value: (-counts[value], value))


def _normalized_text(value):
    return re.sub(r"\\n|\s+", "", value or "")


def _normalized_title(value):
    value = re.sub(r"\s+", " ", (value or "").strip())
    return re.sub(r"\s*\[", " [", value)


def apply_reference_records(scanned_records, reference_records):
    """Repair duplicated current metadata when an older ACB has distinct cue text."""
    duplicate_groups = defaultdict(list)
    for record in scanned_records:
        normalized = _normalized_text(record.get("TextRaw"))
        if normalized:
            duplicate_groups[(record["SpeakerCharacterId"], normalized)].append(record)
    duplicated_keys = {
        (record["SpeakerCharacterId"], record["CueName"])
        for group in duplicate_groups.values()
        if len({record["CueName"] for record in group}) > 1
        for record in group
    }
    reference_index = {
        (record["SpeakerCharacterId"], record["CueName"]): record
        for record in reference_records
    }

    repaired = []
    repair_count = 0
    for source in scanned_records:
        record = dict(source)
        record.setdefault("MetadataRepairStatus", "not_needed")
        record.setdefault("ReferenceAcbFile", "")
        record.setdefault("OriginalTitleRaw", "")
        record.setdefault("OriginalTextRaw", "")
        key = (record["SpeakerCharacterId"], record["CueName"])
        reference = reference_index.get(key)
        if key in duplicated_keys and reference:
            reference_text = reference.get("TextRaw", "")
            if reference_text and _normalized_text(reference_text) != _normalized_text(record.get("TextRaw")):
                record["OriginalTitleRaw"] = record.get("TitleRaw", "")
                record["OriginalTextRaw"] = record.get("TextRaw", "")
                record["TitleRaw"] = reference.get("TitleRaw", record["TitleRaw"])
                record["TextRaw"] = reference_text
                record["TextWiki"] = text_to_html(reference_text)
                record["MetadataRepairStatus"] = "repaired_from_reference_acb"
                record["ReferenceAcbFile"] = reference.get("AcbFile", "")
                repair_count += 1
        repaired.append(record)
    return repaired, repair_count


def apply_reference_acb(scanned_records, reference_acb_root):
    reference_records, warnings = scan_character_home_voice_packages(reference_acb_root)
    repaired, repair_count = apply_reference_records(scanned_records, reference_records)
    return repaired, repair_count, warnings


def _subject_identity(record, names, season_lookup):
    cue_name = record["CueName"]
    category = record.get("HomeVoiceCategory")
    home_voice_no = record.get("HomeVoiceNo")
    key_target = record.get("KeyTargetValue")
    bucket = record.get("AcbBucket", 0)
    year = key_target or bucket or 0

    birthday = BIRTHDAY_CUE_RE.fullmatch(cue_name)
    if category in (3, 4) or birthday:
        target_id = int(birthday.group("target")) if birthday else record["SpeakerCharacterId"]
        target_name = names.get(target_id, f"角色{target_id}")
        suffix = f" [{year}年目]" if year else ""
        return (
            f"birthday:character={target_id}:year={year}",
            "birthday",
            f"{target_name}的生日全员祝福{suffix}",
            target_id,
        )

    if category == 2 or cue_name.startswith("vo_home_user_"):
        suffix = f" [{year}年目]" if year else ""
        return f"user_birthday:year={year}", "user_birthday", f"你的生日{suffix}", None

    if category == 7:
        season = season_lookup.get((record["SpeakerCharacterId"], home_voice_no), {})
        season_id = season.get("SeasonId")
        season_name = season.get("SeasonName", "")
        key = f"season:{season_id or 'unknown'}:home_voice_no={home_voice_no}"
        display = season_name or f"季节语音 {home_voice_no}"
        return key, "season", display, None

    if category == 6:
        return f"limited:home_voice_no={home_voice_no}", "limited", f"期间限定语音 {home_voice_no}", None
    if category == 9:
        return f"time:home_voice_no={home_voice_no}", "time", f"时间问候 {home_voice_no}", None
    if category == 10:
        return f"standard:home_voice_no={home_voice_no}", "standard", f"主页语音 {home_voice_no}", None
    if category is not None:
        return (
            f"category={category}:home_voice_no={home_voice_no}",
            f"category_{category}",
            f"{CATEGORY_NAMES.get(category, '分类语音')} {home_voice_no}",
            None,
        )
    return f"acb_only:cue={cue_name}", "acb_only", cue_name, None


def build_home_voice_catalog(tables, scanned_records, expected_character_ids=EXPECTED_CHARACTER_IDS):
    """Join scanned ACB metadata and return normalized records plus subject summaries."""
    if not isinstance(tables, TableCatalog):
        tables = TableCatalog(tables)

    character_rows = {
        row["CharacterId"]: row
        for row in _active_rows(tables, "mst_character")
        if row.get("CharacterId") in expected_character_ids
    }
    character_names = {
        row["CharacterId"]: row.get("CharacterNameJpn", f"角色{row['CharacterId']}")
        for row in character_rows.values()
    }
    home_index = defaultdict(list)
    for row in _active_rows(tables, "mst_home_voice"):
        if row.get("HomeVoiceTypeCode") == 1:
            home_index[(row.get("HomeVoiceTargetId"), row.get("VoiceCueName"))].append(row)

    season_names = {
        row.get("SeasonId"): row.get("SeasonName", "")
        for row in _active_rows(tables, "mst_season")
    }
    season_lookup = {}
    for row in _active_rows(tables, "mst_character_home_voice_season"):
        enriched = dict(row)
        enriched["SeasonName"] = season_names.get(row.get("SeasonId"), "")
        season_lookup[(row.get("CharacterId"), row.get("HomeVoiceNo"))] = enriched

    limited_lookup = {
        (row.get("CharacterId"), row.get("HomeVoiceNo")): row
        for row in _active_rows(tables, "mst_character_home_voice_limited")
    }

    records = []
    for scanned in scanned_records:
        record = dict(scanned)
        speaker_id = record["SpeakerCharacterId"]
        record["SpeakerCharacterName"] = character_names.get(speaker_id, f"角色{speaker_id}")
        matches = home_index.get((speaker_id, record["CueName"]), [])
        flags = []
        info_flags = []
        if len(matches) == 1:
            master = matches[0]
            record.update({
                "HomeVoiceNo": master.get("HomeVoiceNo"),
                "HomeVoiceCategory": master.get("HomeVoiceCategory"),
                "KeyTargetValue": master.get("KeyTargetValue"),
                "MotionCharacterId": master.get("MotionCharacterId"),
                "MasterdataMatchStatus": "matched",
            })
        elif not matches:
            record.update({
                "HomeVoiceNo": None,
                "HomeVoiceCategory": None,
                "KeyTargetValue": None,
                "MotionCharacterId": None,
                "MasterdataMatchStatus": "acb_only",
            })
            info_flags.append("masterdata_missing")
        else:
            master = matches[0]
            record.update({
                "HomeVoiceNo": master.get("HomeVoiceNo"),
                "HomeVoiceCategory": master.get("HomeVoiceCategory"),
                "KeyTargetValue": master.get("KeyTargetValue"),
                "MotionCharacterId": master.get("MotionCharacterId"),
                "MasterdataMatchStatus": "ambiguous",
            })
            flags.append("masterdata_ambiguous")

        season = season_lookup.get((speaker_id, record.get("HomeVoiceNo")), {})
        limited = limited_lookup.get((speaker_id, record.get("HomeVoiceNo")), {})
        record["SeasonId"] = season.get("SeasonId")
        record["SeasonName"] = season.get("SeasonName", "")
        record["ServiceYears"] = season.get("ServiceYears")
        record["StartTime"] = limited.get("StartTime")
        record["EndTime"] = limited.get("EndTime")

        subject_key, subject_type, display_name, target_id = _subject_identity(
            record, character_names, season_lookup
        )
        record["SubjectKey"] = subject_key
        record["SubjectType"] = subject_type
        record["SubjectDisplayName"] = display_name
        record["SubjectCharacterId"] = target_id
        if (
            record.get("HomeVoiceCategory") in (2, 3, 4)
            and record.get("KeyTargetValue")
            and record.get("AcbBucket") != record.get("KeyTargetValue")
        ):
            flags.append("package_year_mismatch")
        if record.get("AlternateAcbFiles"):
            info_flags.append("duplicate_source_package")
        if record.get("MetadataMatchStatus") != "matched_by_acb_utf":
            flags.append("metadata_fallback")
        if not record.get("StableRead", True):
            flags.append("unstable_read")
        record["AuditFlags"] = flags
        record["InfoFlags"] = info_flags
        records.append(record)

    by_subject = defaultdict(list)
    for record in records:
        by_subject[record["SubjectKey"]].append(record)

    # Titles are source metadata, so use the majority only as a display fallback and flag outliers.
    for subject_records in by_subject.values():
        canonical_title = _mode(row.get("TitleRaw") for row in subject_records)
        generated_name = subject_records[0]["SubjectDisplayName"]
        if subject_records[0]["SubjectType"] not in ("birthday", "user_birthday") and canonical_title:
            generated_name = canonical_title
        for row in subject_records:
            row["CanonicalTitle"] = canonical_title
            row["SubjectDisplayName"] = generated_name
            raw_title = row.get("TitleRaw", "")
            title_matches = _normalized_title(raw_title) == _normalized_title(canonical_title)
            if row["SubjectType"] == "birthday" and row.get("SubjectCharacterId"):
                character = character_rows.get(row["SubjectCharacterId"], {})
                aliases = {
                    character.get("CharacterNameJpn", ""),
                    character.get("CharacterLastNameJpn", ""),
                }
                year = row.get("KeyTargetValue") or row.get("AcbBucket") or 0
                expected_titles = {
                    _normalized_title(f"{alias}の誕生日 [{year}年目]")
                    for alias in aliases if alias
                }
                title_matches = _normalized_title(raw_title) in expected_titles
            if raw_title and not title_matches:
                row["AuditFlags"].append("title_conflict")

    by_speaker_text = defaultdict(list)
    for record in records:
        text = record.get("TextRaw", "").strip()
        if text:
            by_speaker_text[(record["SpeakerCharacterId"], text)].append(record)
    for duplicates in by_speaker_text.values():
        if len({row["CueName"] for row in duplicates}) > 1:
            for row in duplicates:
                row["AuditFlags"].append("duplicate_text_other_cue")

    subjects = []
    expected = set(expected_character_ids)
    for subject_key, subject_records in by_subject.items():
        speaker_counts = Counter(row["SpeakerCharacterId"] for row in subject_records)
        present = set(speaker_counts)
        missing = sorted(expected - present)
        duplicate_speakers = sorted(speaker for speaker, count in speaker_counts.items() if count > 1)
        statuses = Counter(row["MasterdataMatchStatus"] for row in subject_records)
        subjects.append({
            "SubjectKey": subject_key,
            "SubjectType": subject_records[0]["SubjectType"],
            "SubjectDisplayName": subject_records[0]["SubjectDisplayName"],
            "SubjectCharacterId": subject_records[0]["SubjectCharacterId"],
            "HomeVoiceNo": subject_records[0].get("HomeVoiceNo"),
            "HomeVoiceCategory": subject_records[0].get("HomeVoiceCategory"),
            "SeasonId": subject_records[0].get("SeasonId"),
            "ServiceYears": subject_records[0].get("ServiceYears"),
            "CueName": subject_records[0]["CueName"],
            "RowCount": len(subject_records),
            "SpeakerCount": len(present),
            "MissingCharacterIds": missing,
            "DuplicateSpeakerIds": duplicate_speakers,
            "Complete": not missing and not duplicate_speakers,
            "MasterdataStatus": "matched" if set(statuses) == {"matched"} else ",".join(sorted(statuses)),
            "TitleVariants": sorted({row.get("TitleRaw", "") for row in subject_records if row.get("TitleRaw")}),
        })

    records.sort(key=lambda row: (row["SubjectKey"], row["SpeakerCharacterId"], row["CueName"]))
    subjects.sort(key=lambda row: (row["SubjectType"], row["SubjectCharacterId"] or 0, row["HomeVoiceNo"] or 0, row["SubjectKey"]))
    return {"Records": records, "Subjects": subjects}


def _subject_index_sheet(subjects):
    headers = [
        "主体Key", "主体类型", "主体", "CueName", "HomeVoiceNo", "分类代码",
        "行数", "角色数", "是否完整", "缺失角色序号", "重复角色序号",
        "masterdata状态", "标题变体",
    ]
    rows = [
        [
            item["SubjectKey"], item["SubjectType"], item["SubjectDisplayName"],
            item["CueName"], item["HomeVoiceNo"], item["HomeVoiceCategory"],
            item["RowCount"], item["SpeakerCount"], "是" if item["Complete"] else "否",
            ",".join(map(str, item["MissingCharacterIds"])),
            ",".join(map(str, item["DuplicateSpeakerIds"])), item["MasterdataStatus"],
            " | ".join(item["TitleVariants"]),
        ]
        for item in subjects
    ]
    return {
        "title": "主体索引", "headers": headers, "rows": rows,
        "col_widths": {"A": 42, "B": 18, "C": 34, "D": 26, "I": 12, "J": 18, "K": 18, "L": 20, "M": 50},
        "wrap_cols": [3, 13],
    }


def _wiki_sheet(records, title="Wiki长表"):
    return {
        "title": title,
        "headers": ["主体", "角色序号", "角色名", "日文台词", "中文翻译"],
        "rows": [
            [
                row["SubjectDisplayName"], row["SpeakerCharacterId"],
                row["SpeakerCharacterName"], row["TextWiki"], "",
            ]
            for row in records
        ],
        "col_widths": {"A": 36, "B": 12, "C": 18, "D": 72, "E": 72},
        "wrap_cols": [1, 4, 5],
    }


def _audit_sheet(records):
    headers = [
        "主体Key", "主体类型", "主体", "主体角色ID", "角色序号", "角色名",
        "HomeVoiceNo", "分类代码", "KeyTargetValue", "SeasonId", "ServiceYears",
        "StartTime", "EndTime", "ACB文件", "候选重复ACB", "包序号", "CueName",
        "CueIndex", "CueId", "原始标题", "多数标题", "原始文本", "Wiki文本",
        "masterdata匹配", "元数据匹配", "读取稳定", "修复状态", "参考ACB",
        "修复前标题", "修复前文本", "信息标记", "审计标记",
    ]
    rows = [
        [
            row["SubjectKey"], row["SubjectType"], row["SubjectDisplayName"],
            row["SubjectCharacterId"], row["SpeakerCharacterId"], row["SpeakerCharacterName"],
            row["HomeVoiceNo"], row["HomeVoiceCategory"], row["KeyTargetValue"],
            row["SeasonId"], row["ServiceYears"], row["StartTime"], row["EndTime"],
            row["AcbFile"], " | ".join(row.get("AlternateAcbFiles", [])), row["AcbBucket"],
            row["CueName"], row["CueIndex"], row["CueId"], row["TitleRaw"],
            row["CanonicalTitle"], row["TextRaw"], row["TextWiki"],
            row["MasterdataMatchStatus"], row["MetadataMatchStatus"],
            "是" if row["StableRead"] else "否", row.get("MetadataRepairStatus", "not_needed"),
            row.get("ReferenceAcbFile", ""), row.get("OriginalTitleRaw", ""),
            row.get("OriginalTextRaw", ""), ";".join(row["InfoFlags"]),
            ";".join(row["AuditFlags"]),
        ]
        for row in records
    ]
    return {
        "title": "原始审计", "headers": headers, "rows": rows,
        "col_widths": {"A": 42, "C": 34, "F": 18, "N": 30, "O": 30, "Q": 28, "T": 34, "U": 34, "V": 72, "W": 72, "AB": 28, "AC": 30, "AD": 34, "AE": 72, "AF": 34, "AG": 38},
        "wrap_cols": [3, 20, 21, 22, 23, 30, 31, 32, 33],
    }


def _anomaly_sheet(catalog):
    headers = ["级别", "异常类型", "主体Key", "主体", "角色序号", "角色名", "CueName", "ACB文件", "详情"]
    rows = []
    for subject in catalog["Subjects"]:
        if subject["MissingCharacterIds"]:
            rows.append([
                "阻断", "missing_speakers", subject["SubjectKey"], subject["SubjectDisplayName"],
                "", "", subject["CueName"], "",
                "缺失角色序号: " + ",".join(map(str, subject["MissingCharacterIds"])),
            ])
        if subject["DuplicateSpeakerIds"]:
            rows.append([
                "冲突", "duplicate_speakers", subject["SubjectKey"], subject["SubjectDisplayName"],
                "", "", subject["CueName"], "",
                "重复角色序号: " + ",".join(map(str, subject["DuplicateSpeakerIds"])),
            ])
        if subject["MasterdataStatus"] != "matched":
            rows.append([
                "待主数据", "acb_only_subject", subject["SubjectKey"], subject["SubjectDisplayName"],
                "", "", subject["CueName"], "",
                f"ACB 有 {subject['SpeakerCount']} 名角色文本，当前 masterdata 无映射",
            ])
    for record in catalog["Records"]:
        for flag in record["AuditFlags"]:
            level = {
                "title_conflict": "源元数据",
                "duplicate_text_other_cue": "需核听",
                "package_year_mismatch": "冲突",
                "metadata_fallback": "需检查",
                "unstable_read": "需重扫",
            }.get(flag, "需检查")
            rows.append([
                level, flag, record["SubjectKey"], record["SubjectDisplayName"],
                record["SpeakerCharacterId"], record["SpeakerCharacterName"],
                record["CueName"], record["AcbFile"],
                f"原始标题={record['TitleRaw']}; 多数标题={record['CanonicalTitle']}",
            ])
    return {
        "title": "异常", "headers": headers, "rows": rows,
        "col_widths": {"A": 12, "B": 28, "C": 42, "D": 34, "F": 18, "G": 28, "H": 30, "I": 72},
        "wrap_cols": [4, 9],
    }


def select_subject_records(catalog, selector):
    """Select a subject by stable key, cue name, or exact display name."""
    if not selector:
        return []
    subject_keys = {
        subject["SubjectKey"]
        for subject in catalog["Subjects"]
        if selector in (subject["SubjectKey"], subject["CueName"], subject["SubjectDisplayName"])
    }
    if not subject_keys:
        raise KeyError(f"未找到语音主体: {selector}")
    if len(subject_keys) > 1:
        raise ValueError(f"主体选择不唯一: {selector}")
    selected = [row for row in catalog["Records"] if row["SubjectKey"] in subject_keys]
    return sorted(selected, key=lambda row: row["SpeakerCharacterId"])


def export_home_voice_catalog(catalog, output_dir, selected_subject=None):
    """Export the full four-sheet workbook and an optional single-subject workbook."""
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    workbook_path = os.path.join(output_dir, "home_voice_catalog.xlsx")
    write_workbook(workbook_path, [
        _subject_index_sheet(catalog["Subjects"]),
        _wiki_sheet(catalog["Records"]),
        _audit_sheet(catalog["Records"]),
        _anomaly_sheet(catalog),
    ])
    paths = {"catalog": workbook_path}

    if selected_subject:
        selected = select_subject_records(catalog, selected_subject)
        cue_name = selected[0]["CueName"]
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", cue_name).strip("_") or "subject"
        subject_path = os.path.join(output_dir, f"home_voice_subject_{safe_name}.xlsx")
        write_workbook(subject_path, [_wiki_sheet(selected, title="Wiki主体表")])
        paths["subject"] = subject_path
    return paths


def run(acb_root, masterdata_path=None, selected_subject=None, reference_acb_root=None):
    """Scan ACBs, join masterdata, and write Wiki/audit outputs beside masterdata."""
    acb_root = os.path.abspath(acb_root)
    masterdata_path = os.path.abspath(masterdata_path or "master_data.json")
    if not os.path.isdir(acb_root):
        raise ValueError(f"ACB 输入必须是目录: {acb_root}")
    if not os.path.isfile(masterdata_path):
        raise ValueError(f"未找到 master_data.json: {masterdata_path}")

    tables = TableCatalog(load_json(masterdata_path))
    scanned, warnings = scan_character_home_voice_packages(acb_root)
    repair_count = 0
    if reference_acb_root:
        reference_acb_root = os.path.abspath(reference_acb_root)
        if not os.path.isdir(reference_acb_root):
            raise ValueError(f"参考 ACB 输入必须是目录: {reference_acb_root}")
        scanned, repair_count, reference_warnings = apply_reference_acb(
            scanned, reference_acb_root
        )
        warnings.extend(reference_warnings)
    catalog = build_home_voice_catalog(tables, scanned)
    catalog["SourceRoot"] = acb_root
    catalog["MasterdataPath"] = masterdata_path
    catalog["Warnings"] = warnings
    catalog["ReferenceAcbRoot"] = reference_acb_root or ""
    catalog["Summary"] = {
        "RecordCount": len(catalog["Records"]),
        "SubjectCount": len(catalog["Subjects"]),
        "CompleteSubjectCount": sum(subject["Complete"] for subject in catalog["Subjects"]),
        "AcbOnlySubjectCount": sum(subject["MasterdataStatus"] != "matched" for subject in catalog["Subjects"]),
        "ReferenceRepairCount": repair_count,
    }

    base_dir = os.path.dirname(masterdata_path)
    json_dir = os.path.join(base_dir, "json_output")
    xlsx_dir = os.path.join(base_dir, "xlsx_output")
    os.makedirs(json_dir, exist_ok=True)
    save_json(catalog, os.path.join(json_dir, "Home_Voice_Catalog.json"))
    paths = export_home_voice_catalog(catalog, xlsx_dir, selected_subject=selected_subject)
    print(
        f"[+] 主页语音 {catalog['Summary']['RecordCount']} 行，"
        f"{catalog['Summary']['SubjectCount']} 个主体，"
        f"完整 {catalog['Summary']['CompleteSubjectCount']} 个"
    )
    return paths
