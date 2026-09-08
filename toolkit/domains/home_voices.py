"""Build Wiki-oriented home voice tables from character ACBs and masterdata."""
from __future__ import annotations

import os
from ..core.output import output_directory, record_output, record_warning
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

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
SERVICE_YEAR_RE = re.compile(r"[\[\uff3b]\s*(?P<year>\d+)\s*\u5e74\u76ee\s*[\]\uff3d]")
ANNIVERSARY_YEAR_RE = re.compile(
    r"(?<![\d.])(?P<year>\d+)(?:st|nd|rd|th)\s+Anniv(?:ersary)?\.?",
    re.IGNORECASE,
)
SEASON_MONTH_RE = re.compile(r"\((?P<start>\d{1,2})\s*[~～-]\s*(?P<end>\d{1,2})月\)")
SERVICE_YEAR_ONE_START = date(2024, 5, 14)
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


def _title_service_year(value):
    match = SERVICE_YEAR_RE.search(value or "")
    if match:
        return int(match.group("year"))
    match = ANNIVERSARY_YEAR_RE.search(value or "")
    return int(match.group("year")) if match else None


def _infer_service_year(record):
    """Resolve service year without assuming every masterdata family uses one marker."""
    candidates = {}

    def add(source, value):
        if isinstance(value, bool):
            return
        try:
            value = int(value)
        except (TypeError, ValueError):
            return
        if value > 0:
            candidates[source] = value

    category = record.get("HomeVoiceCategory")
    cue_name = record.get("CueName", "")
    if category in (2, 3, 4):
        add("masterdata_key_target", record.get("KeyTargetValue"))
    add("masterdata_product_title", _title_service_year(record.get("ProductDisplayName")))
    add("acb_title", _title_service_year(record.get("TitleRaw")))
    if category in (2, 3, 4, 6) or BIRTHDAY_CUE_RE.fullmatch(cue_name):
        add("acb_package", record.get("AcbBucket"))
    if category == 7:
        add("masterdata_season", record.get("ServiceYears"))

    priority = (
        "masterdata_key_target",
        "masterdata_product_title",
        "acb_title",
        "acb_package",
        "masterdata_season",
    )
    source = next((name for name in priority if name in candidates), "")
    return (candidates.get(source), source, candidates)


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
    year = record.get("ServiceYear") or key_target or bucket or 0

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
    product_lookup = {
        (row.get("HomeVoiceTargetId"), row.get("HomeVoiceNo")): row
        for row in _active_rows(tables, "mst_home_voice_product")
        if row.get("HomeVoiceTypeCode") == 1
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
        product = product_lookup.get((speaker_id, record.get("HomeVoiceNo")), {})
        record["SeasonId"] = season.get("SeasonId")
        record["SeasonName"] = season.get("SeasonName", "")
        record["ServiceYears"] = season.get("ServiceYears")
        record["StartTime"] = limited.get("StartTime")
        record["EndTime"] = limited.get("EndTime")
        record["ProductDisplayName"] = product.get("DisplayName", "")
        record["ProductDescription"] = product.get("Description", "")
        service_year, service_year_source, service_year_candidates = _infer_service_year(record)
        record["ServiceYear"] = service_year
        record["ServiceYearSource"] = service_year_source
        record["ServiceYearCandidates"] = service_year_candidates
        if len(set(service_year_candidates.values())) > 1:
            flags.append("service_year_conflict")

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
            "ServiceYear": subject_records[0].get("ServiceYear"),
            "ServiceYearSources": sorted({
                row.get("ServiceYearSource", "") for row in subject_records
                if row.get("ServiceYearSource")
            }),
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


def _wiki_sheet(records, title="Wiki长表"):
    return {
        "title": title,
        "headers": ["主体", "角色序号", "角色名", "日文台词", "中文翻译"],
        "rows": [
            [
                row["SubjectDisplayName"], row["SpeakerCharacterId"],
                row["SpeakerCharacterName"], row["TextWiki"].replace("<br>", "\n"), "",
            ]
            for row in records
        ],
        "col_widths": {"A": 36, "B": 12, "C": 18, "D": 72, "E": 72},
        "wrap_cols": [1, 4, 5],
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
                "service_year_conflict": "冲突",
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


def _md_cell(value):
    return (
        str(value if value is not None else "")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", "<br>")
    )


def render_audit_markdown(catalog):
    """Render the technical audit outside the Wiki-facing workbook."""
    summary = catalog.get("Summary", {})
    lines = [
        "# 主页语音内部审计报告",
        "",
        f"- ACB 来源：`{catalog.get('SourceRoot', '')}`",
        f"- Masterdata：`{catalog.get('MasterdataPath', '')}`",
        f"- 参考旧 ACB：`{catalog.get('ReferenceAcbRoot') or '未使用'}`",
        f"- 记录数：{summary.get('RecordCount', len(catalog['Records']))}",
        f"- 主体数：{summary.get('SubjectCount', len(catalog['Subjects']))}",
        f"- 完整主体：{summary.get('CompleteSubjectCount', sum(item['Complete'] for item in catalog['Subjects']))}",
        f"- ACB-only 主体：{summary.get('AcbOnlySubjectCount', sum(item['MasterdataStatus'] != 'matched' for item in catalog['Subjects']))}",
        f"- 参考旧包修复：{summary.get('ReferenceRepairCount', 0)}",
        "",
        "## 数据完整度",
        "",
        "| 主体 | CueName | 已有/应有 | 缺失角色序号 | 状态 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for subject in catalog["Subjects"]:
        expected = subject["SpeakerCount"] + len(subject["MissingCharacterIds"])
        lines.append(
            "| " + " | ".join([
                _md_cell(subject["SubjectDisplayName"]),
                _md_cell(subject["CueName"]),
                f"{subject['SpeakerCount']}/{expected}",
                _md_cell(",".join(map(str, subject["MissingCharacterIds"]))),
                "完整" if subject["Complete"] else "不完整",
            ]) + " |"
        )

    repairs = [
        record for record in catalog["Records"]
        if record.get("MetadataRepairStatus") == "repaired_from_reference_acb"
    ]
    lines.extend(["", "## 参考旧包修复", ""])
    if not repairs:
        lines.append("无。")
    else:
        lines.extend([
            "| 角色序号 | 角色名 | CueName | 当前 ACB | 参考 ACB |",
            "| ---: | --- | --- | --- | --- |",
        ])
        for record in repairs:
            lines.append(
                "| " + " | ".join(_md_cell(value) for value in [
                    record["SpeakerCharacterId"], record["SpeakerCharacterName"],
                    record["CueName"], record["AcbFile"], record["ReferenceAcbFile"],
                ]) + " |"
            )

    anomaly = _anomaly_sheet(catalog)
    lines.extend([
        "", "## 待行动异常", "",
        "| " + " | ".join(anomaly["headers"]) + " |",
        "| " + " | ".join("---" for _ in anomaly["headers"]) + " |",
    ])
    for row in anomaly["rows"]:
        lines.append("| " + " | ".join(_md_cell(value) for value in row) + " |")

    info_counts = Counter(flag for record in catalog["Records"] for flag in record["InfoFlags"])
    lines.extend(["", "## 非阻断审计信息", ""])
    if info_counts:
        for flag, count in sorted(info_counts.items()):
            lines.append(f"- `{flag}`：{count}")
    else:
        lines.append("无。")
    lines.append("")
    return "\n".join(lines)


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


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def _service_year_start(service_year):
    return date(SERVICE_YEAR_ONE_START.year + int(service_year) - 1, 5, 14)


def _birthday_occurrence(service_year, month, day):
    cycle_start = _service_year_start(service_year)
    year = cycle_start.year if (month, day) >= (5, 14) else cycle_start.year + 1
    return date(year, month, day)


def _season_months(subject):
    values = [subject.get("SubjectDisplayName", ""), *subject.get("TitleVariants", [])]
    for value in values:
        match = SEASON_MONTH_RE.search(value or "")
        if match:
            return int(match.group("start")), int(match.group("end"))
    return None


def _season_interval(months, year):
    start_month, end_month = months
    start = date(year, start_month, 1)
    end_year = year + (end_month < start_month)
    if end_month == 12:
        end = date(end_year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(end_year, end_month + 1, 1) - timedelta(days=1)
    return start, end


def _season_intervals(subjects):
    """Resolve season periods, including ServiceYears=0 rows bracketed by known cycles."""
    seasons = sorted(
        (subject for subject in subjects if subject.get("SubjectType") == "season"),
        key=lambda subject: subject.get("HomeVoiceNo") or 0,
    )
    resolved = {}
    for subject in seasons:
        months = _season_months(subject)
        service_year = subject.get("ServiceYear")
        if not months or not service_year:
            continue
        cycle_start = _service_year_start(service_year)
        occurrence_year = cycle_start.year if months[0] >= 5 else cycle_start.year + 1
        resolved[subject["SubjectKey"]] = _season_interval(months, occurrence_year)

    for index, subject in enumerate(seasons):
        if subject["SubjectKey"] in resolved:
            continue
        months = _season_months(subject)
        if not months:
            continue
        previous = next(
            (resolved[item["SubjectKey"]] for item in reversed(seasons[:index])
             if item["SubjectKey"] in resolved),
            None,
        )
        following = next(
            (resolved[item["SubjectKey"]] for item in seasons[index + 1:]
             if item["SubjectKey"] in resolved),
            None,
        )
        if not previous or not following:
            continue
        for occurrence_year in range(previous[0].year - 1, following[1].year + 2):
            candidate = _season_interval(months, occurrence_year)
            if candidate[0] > previous[1] and candidate[1] < following[0]:
                resolved[subject["SubjectKey"]] = candidate
                break
    return resolved


def build_recent_year_collection(catalog, tables, as_of_date):
    """Select the preceding 365 days of Wiki-facing home and birthday voices."""
    as_of = _parse_date(as_of_date)
    if not as_of:
        raise ValueError("recent-year requires an end date in YYYY-MM-DD format")
    window_start = as_of - timedelta(days=365)
    if not isinstance(tables, TableCatalog):
        tables = TableCatalog(tables)

    characters = {
        row.get("CharacterId"): row
        for row in _active_rows(tables, "mst_character")
        if row.get("CharacterId") in EXPECTED_CHARACTER_IDS
    }
    records_by_subject = defaultdict(list)
    for record in catalog["Records"]:
        records_by_subject[record["SubjectKey"]].append(record)
    season_intervals = _season_intervals(catalog["Subjects"])

    home_subjects = []
    birthday_subjects = []
    selection = {}
    for subject in catalog["Subjects"]:
        subject_key = subject["SubjectKey"]
        subject_type = subject.get("SubjectType")
        selected_interval = None
        basis = ""

        if subject_type == "birthday":
            character = characters.get(subject.get("SubjectCharacterId"), {})
            service_year = subject.get("ServiceYear")
            month, day = character.get("BirthMonth"), character.get("BirthDay")
            if service_year and month and day:
                occurrence = _birthday_occurrence(service_year, month, day)
                selected_interval = (occurrence, occurrence)
                basis = "character_birthday_and_service_year"
            target = birthday_subjects
        else:
            target = home_subjects
            if subject_type == "season":
                selected_interval = season_intervals.get(subject_key)
                basis = "season_month_range"
            elif subject_type == "limited":
                rows = records_by_subject[subject_key]
                starts = [_parse_date(row.get("StartTime")) for row in rows]
                ends = [_parse_date(row.get("EndTime")) for row in rows]
                starts = [value for value in starts if value]
                ends = [value for value in ends if value]
                if starts:
                    selected_interval = (min(starts), max(ends or starts))
                    basis = "masterdata_limited_period"
            elif subject_type in {"acb_only", "user_birthday"} and subject.get("ServiceYear"):
                released = _service_year_start(subject["ServiceYear"])
                selected_interval = (released, released)
                basis = "service_year_release"

        if not selected_interval:
            continue
        if selected_interval[1] < window_start or selected_interval[0] > as_of:
            continue
        target.append(subject)
        selection[subject_key] = {
            "SelectionBasis": basis,
            "OccurrenceStart": selected_interval[0].isoformat(),
            "OccurrenceEnd": selected_interval[1].isoformat(),
        }

    home_keys = {subject["SubjectKey"] for subject in home_subjects}
    birthday_keys = {subject["SubjectKey"] for subject in birthday_subjects}
    home_records = [record for record in catalog["Records"] if record["SubjectKey"] in home_keys]
    birthday_records = [record for record in catalog["Records"] if record["SubjectKey"] in birthday_keys]
    return {
        "WindowStart": window_start.isoformat(),
        "WindowEnd": as_of.isoformat(),
        "HomeRecords": home_records,
        "BirthdayRecords": birthday_records,
        "HomeSubjects": home_subjects,
        "BirthdaySubjects": birthday_subjects,
        "Selection": selection,
    }


def export_recent_year_collection(collection, output_dir):
    start = collection["WindowStart"].replace("-", "")
    end = collection["WindowEnd"].replace("-", "")
    path = os.path.join(output_dir, f"home_voice_recent_year_{start}_{end}.xlsx")
    return write_workbook(path, [
        _wiki_sheet(collection["HomeRecords"], title="主页与季节语音"),
        _wiki_sheet(collection["BirthdayRecords"], title="生日祝福语音"),
    ]) or path


def recent_year_audit(collection):
    def subjects(items):
        return [
            {
                "SubjectKey": item["SubjectKey"],
                "SubjectDisplayName": item["SubjectDisplayName"],
                "SubjectType": item["SubjectType"],
                "CueName": item["CueName"],
                "HomeVoiceNo": item.get("HomeVoiceNo"),
                "ServiceYear": item.get("ServiceYear"),
                "RowCount": item["RowCount"],
                "SpeakerCount": item["SpeakerCount"],
                "Complete": item["Complete"],
                **collection["Selection"][item["SubjectKey"]],
            }
            for item in items
        ]

    return {
        "WindowStart": collection["WindowStart"],
        "WindowEnd": collection["WindowEnd"],
        "HomeSubjectCount": len(collection["HomeSubjects"]),
        "HomeRecordCount": len(collection["HomeRecords"]),
        "BirthdaySubjectCount": len(collection["BirthdaySubjects"]),
        "BirthdayRecordCount": len(collection["BirthdayRecords"]),
        "HomeSubjects": subjects(collection["HomeSubjects"]),
        "BirthdaySubjects": subjects(collection["BirthdaySubjects"]),
    }


def export_home_voice_catalog(catalog, output_dir, selected_subject=None):
    """Export the Wiki workbook and an optional single-subject workbook."""
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    workbook_path = os.path.join(output_dir, "home_voice_catalog.xlsx")
    workbook_path = write_workbook(workbook_path, [
        _wiki_sheet(catalog["Records"]),
    ]) or workbook_path
    paths = {"catalog": workbook_path}

    if selected_subject:
        selected = select_subject_records(catalog, selected_subject)
        cue_name = selected[0]["CueName"]
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", cue_name).strip("_") or "subject"
        subject_path = os.path.join(output_dir, f"home_voice_subject_{safe_name}.xlsx")
        subject_path = write_workbook(
            subject_path, [_wiki_sheet(selected, title="Wiki主体表")]
        ) or subject_path
        paths["subject"] = subject_path
    return paths


def run(
    acb_root,
    masterdata_path=None,
    selected_subject=None,
    reference_acb_root=None,
    recent_year_end=None,
    session=None,
):
    """Scan ACBs, join masterdata, and write Wiki/audit outputs beside masterdata."""
    acb_root = os.path.abspath(acb_root)
    masterdata_path = session.json_path if session else os.path.abspath(
        masterdata_path or "master_data.json"
    )
    if not os.path.isdir(acb_root):
        raise ValueError(f"ACB 输入必须是目录: {acb_root}")
    if not os.path.isfile(masterdata_path):
        raise ValueError(f"未找到 master_data.json: {masterdata_path}")

    tables = session.tables if session else TableCatalog(load_json(masterdata_path))
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
        "SubjectCountsByServiceYear": dict(sorted(Counter(
            subject["ServiceYear"] for subject in catalog["Subjects"]
            if subject.get("ServiceYear")
        ).items())),
        "BirthdaySubjectCountsByYear": dict(sorted(Counter(
            subject["ServiceYear"] for subject in catalog["Subjects"]
            if subject["SubjectType"] == "birthday" and subject.get("ServiceYear")
        ).items())),
    }

    base_dir = os.path.dirname(masterdata_path)
    json_dir = output_directory("audit", os.path.join(base_dir, "audit_output"))
    xlsx_dir = output_directory("wiki", os.path.join(base_dir, "xlsx_output"))
    os.makedirs(json_dir, exist_ok=True)
    save_json(catalog, os.path.join(json_dir, "Home_Voice_Catalog.json"))
    audit_path = os.path.join(json_dir, "home_voice_audit.md")
    with open(audit_path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(render_audit_markdown(catalog))
    record_output(audit_path)
    paths = export_home_voice_catalog(catalog, xlsx_dir, selected_subject=selected_subject)
    if recent_year_end:
        recent = build_recent_year_collection(catalog, tables, recent_year_end)
        paths["recent_year"] = export_recent_year_collection(recent, xlsx_dir)
        recent_audit = recent_year_audit(recent)
        recent_name = (
            f"home_voice_recent_year_{recent['WindowStart'].replace('-', '')}_"
            f"{recent['WindowEnd'].replace('-', '')}_audit.json"
        )
        recent_audit_path = os.path.join(json_dir, recent_name)
        save_json(recent_audit, recent_audit_path)
        paths["recent_year_audit"] = recent_audit_path
    paths["audit"] = audit_path
    incomplete = catalog['Summary']['SubjectCount'] - catalog['Summary']['CompleteSubjectCount']
    if incomplete or warnings:
        record_warning(f"主页语音有 {incomplete} 个主体不完整，扫描警告 {len(warnings)} 条；详见语音审计")
    print(
        f"[+] 主页语音 {catalog['Summary']['RecordCount']} 行，"
        f"{catalog['Summary']['SubjectCount']} 个主体，"
        f"完整 {catalog['Summary']['CompleteSubjectCount']} 个"
    )
    return paths
