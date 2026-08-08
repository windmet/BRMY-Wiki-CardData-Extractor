"""Snap 拍立得数据提取 + 导出。"""
from collections import defaultdict

from ..core.scanner import walk, load_json, save_json
from ..core.exporter import write_xlsx, json_path, xlsx_path
from ..core.data import CHAR_MAP, NAME_MAP, translate_scene

INPUT_JSON = 'master_data.json'


def extract():
    """从 master_data.json 提取 Snap 数据 → json_output/intermediate_snaps.json"""
    data = load_json(INPUT_JSON)

    sticky_notes = {}
    raw_snapshots = []
    map_spin_set = {}
    map_motion = {}
    map_char_motion = {}

    for obj in walk(data):
        if 'StickyNoteId' in obj and 'SnapshotId' not in obj:
            s_id = obj.get('StickyNoteId')
            c_id = obj.get('CharacterId', 0)
            sticky_notes[s_id] = {
                'text': obj.get('Comment', ''),
                'char_id': c_id,
                'char_name': CHAR_MAP.get(c_id, f"未知({c_id})"),
            }
        elif 'SnapshotId' in obj and 'Comment' in obj:
            raw_snapshots.append(obj)
        elif 'SpinSetId' in obj and 'SpinMotionIds' in obj:
            map_spin_set[obj['SpinSetId']] = obj.get('SpinMotionIds', [])
        elif 'SpinMotionId' in obj and 'SpinCharacterMotionIds' in obj:
            map_motion[obj['SpinMotionId']] = obj.get('SpinCharacterMotionIds', [])
        elif 'SpinCharacterMotionId' in obj and 'SpinCharacterMotionFileName' in obj:
            map_char_motion[obj['SpinCharacterMotionId']] = obj.get('SpinCharacterMotionFileName', '')

    rarity_map = {1: "N", 2: "R", 3: "SR"}
    processed = []

    for snap in raw_snapshots:
        char_ids = snap.get('SnapshotCharacterIds', [])
        if not isinstance(char_ids, list):
            char_ids = [char_ids] if char_ids else []
        main_chars = " & ".join([CHAR_MAP.get(cid, str(cid)) for cid in char_ids])

        main_comment = snap.get('Comment', '')
        special_frame = snap.get('SnapshotSpecialFrameId', 0)
        is_birthday = (special_frame > 0) or "BirthDay" in main_comment or "Birthday" in main_comment

        scene_raw = "Unknown_Scene"
        spin_set_id = snap.get('SpinSetId', 0)
        for m_id in map_spin_set.get(spin_set_id, []):
            for cm_id in map_motion.get(m_id, []):
                if cm_id in map_char_motion and map_char_motion[cm_id]:
                    scene_raw = map_char_motion[cm_id]
                    break
            if scene_raw != "Unknown_Scene":
                break
        scene_raw = scene_raw.split('/')[-1] if '/' in scene_raw else scene_raw

        snap_data = {
            'snap_id': snap.get('SnapshotId'),
            'char_ids': char_ids,
            'spin_set_id': spin_set_id,
            'main_chars': main_chars,
            'main_text': main_comment,
            'rarity': rarity_map.get(snap.get('SnapshotRarityCode', 1), "未知"),
            'category': "生日限定" if is_birthday else "常驻",
            'scene_raw': scene_raw,
            'comments': [],
        }

        for i in range(1, 5):
            s_id = snap.get(f'StickyNoteId{i}', 0)
            if s_id > 0 and s_id in sticky_notes:
                snap_data['comments'].append(sticky_notes[s_id])

        processed.append(snap_data)

    out = json_path('intermediate_snaps.json')
    save_json(processed, out)
    print(f"[+] 提取 {len(processed)} 张相片 → {out}")
    return processed


def export(json_file=None):
    """intermediate_snaps.json → xlsx_output/Snap_Wiki_Data_Clean.xlsx"""
    if json_file is None:
        json_file = json_path('intermediate_snaps.json')
    raw_data = load_json(json_file)

    unique_snaps = {}
    for snap in raw_data:
        main_chars = snap['main_chars']
        main_text = snap['main_text'].replace('\n', '<br>')
        category = snap['category']
        rarity = snap['rarity']
        scene_name = translate_scene(snap['scene_raw'])

        comments = [(c['char_name'], c['text']) for c in snap['comments']]
        comments.sort(key=lambda x: (x[0], x[1]))
        while len(comments) < 4:
            comments.append(("", ""))

        key = (scene_name, category, rarity, main_chars, main_text,
               comments[0][0], comments[0][1], comments[1][0], comments[1][1],
               comments[2][0], comments[2][1], comments[3][0], comments[3][1])

        if key not in unique_snaps:
            unique_snaps[key] = {'first_id': snap['snap_id'], 'merged_count': 1}
        else:
            unique_snaps[key]['merged_count'] += 1

    headers = [
        "首次出现ID", "互动场景", "所属分类", "稀有度", "相片主角", "主文案",
        "评论1_角色", "评论1_文案", "评论2_角色", "评论2_文案",
        "评论3_角色", "评论3_文案", "评论4_角色", "评论4_文案", "折叠重复数",
    ]
    rows = []
    for key, val in sorted(unique_snaps.items(), key=lambda x: x[1]['first_id']):
        scene_name, category, rarity, main_chars, main_text, \
            c1_n, c1_t, c2_n, c2_t, c3_n, c3_t, c4_n, c4_t = key
        rows.append([
            val['first_id'], scene_name, category, rarity, main_chars, main_text,
            c1_n, c1_t, c2_n, c2_t, c3_n, c3_t, c4_n, c4_t, val['merged_count'],
        ])

    out = xlsx_path('Snap_Wiki_Data_Clean.xlsx')
    write_xlsx(rows, out, headers, sheet_title="Snap图鉴数据")
    print(f"[+] 去重后 {len(rows)} 条 → {out}")


def run():
    extract()
    export()
