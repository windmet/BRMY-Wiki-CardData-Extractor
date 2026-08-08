"""Build Wiki-oriented home voice tables from character ACBs and masterdata."""
from __future__ import annotations

import os
import re
from collections import Counter, defaultdict

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

    character_names = {
        row["CharacterId"]: row.get("CharacterNameJpn", f"角色{row['CharacterId']}")
        for row in _active_rows(tables, "mst_character")
        if row.get("CharacterId") in expected_character_ids
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
            flags.append("masterdata_missing")
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
            flags.append("duplicate_source_package")
        if record.get("MetadataMatchStatus") != "matched_by_acb_utf":
            flags.append("metadata_fallback")
        if not record.get("StableRead", True):
            flags.append("unstable_read")
        record["AuditFlags"] = flags
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
            if row.get("TitleRaw") and row["TitleRaw"] != canonical_title:
                row["AuditFlags"].append("title_outlier")

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
