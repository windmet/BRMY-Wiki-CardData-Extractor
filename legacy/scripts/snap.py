import json

INPUT_JSON = 'master_data.json'
OUTPUT_JSON = 'intermediate_snaps.json'

CHAR_MAP = {
    1: "皇坂逢", 2: "城瀬由鶴", 3: "須王芦佳", 4: "綾戸恋", 5: "宇京真央",
    6: "樋宮明星", 7: "環野揺", 8: "槻本大河", 9: "壱川春日", 10: "隠岐谷誓",
    11: "節見静", 12: "御門尊", 13: "新開戦", 14: "相沢篠信", 15: "在間樹帆",
    16: "祠堂恭耶", 17: "立科吏来", 18: "恩田灯世", 19: "新名有", 20: "神家",
    21: "麻波麗"
}

def main():
    print(f"[*] 正在加载巨型数据库: {INPUT_JSON} ...")
    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] 读取失败: {e}")
        return

    sticky_notes = {}
    raw_snapshots = []
    
    # 构建三大关系网
    map_spin_set = {}    # SpinSetId -> [SpinMotionId, ...]
    map_motion = {}      # SpinMotionId -> [SpinCharacterMotionId, ...]
    map_char_motion = {} # SpinCharacterMotionId -> FileName

    def scan_obj(obj):
        if isinstance(obj, dict):
            # 抓取便利贴
            if 'StickyNoteId' in obj and 'SnapshotId' not in obj:
                s_id = obj.get('StickyNoteId')
                c_id = obj.get('CharacterId', 0)
                sticky_notes[s_id] = {
                    'text': obj.get('Comment', ''),
                    'char_id': c_id,
                    'char_name': CHAR_MAP.get(c_id, f"未知({c_id})")
                }
            # 抓取相片
            elif 'SnapshotId' in obj and 'Comment' in obj:
                raw_snapshots.append(obj)
            
            # 抓取场景溯源链
            elif 'SpinSetId' in obj and 'SpinMotionIds' in obj:
                map_spin_set[obj['SpinSetId']] = obj.get('SpinMotionIds', [])
            elif 'SpinMotionId' in obj and 'SpinCharacterMotionIds' in obj:
                map_motion[obj['SpinMotionId']] = obj.get('SpinCharacterMotionIds', [])
            elif 'SpinCharacterMotionId' in obj and 'SpinCharacterMotionFileName' in obj:
                map_char_motion[obj['SpinCharacterMotionId']] = obj.get('SpinCharacterMotionFileName', "")
                
            for v in obj.values(): scan_obj(v)
        elif isinstance(obj, list):
            for item in obj: scan_obj(item)

    print("[*] 正在扫描并构建底层穿透映射网络...")
    scan_obj(data)

    processed_snaps = []
    rarity_map = {1: "N", 2: "R", 3: "SR"}

    for snap in raw_snapshots:
        char_ids = snap.get('SnapshotCharacterIds', [])
        main_chars = " & ".join([CHAR_MAP.get(cid, str(cid)) for cid in char_ids]) if isinstance(char_ids, list) else CHAR_MAP.get(char_ids, str(char_ids))

        main_comment = snap.get('Comment', '')
        rarity_code = snap.get('SnapshotRarityCode', 1)
        special_frame = snap.get('SnapshotSpecialFrameId', 0)
        
        # 生日判定
        is_birthday = (special_frame > 0) or ("BirthDay" in main_comment) or ("Birthday" in main_comment)
        
        # 核心修复：链式穿透查找场景（跳过空的动画组）
        scene_raw = "Unknown_Scene"
        spin_set_id = snap.get('SpinSetId', 0)
        motion_ids = map_spin_set.get(spin_set_id, [])
        
        for m_id in motion_ids:
            char_motion_ids = map_motion.get(m_id, [])
            if char_motion_ids: # 如果找到了有角色的动作
                for cm_id in char_motion_ids:
                    if cm_id in map_char_motion and map_char_motion[cm_id]:
                        scene_raw = map_char_motion[cm_id]
                        break # 找到了就立即打破循环
            if scene_raw != "Unknown_Scene":
                break
                
        # 提取文件名最后一部分
        scene_raw = scene_raw.split('/')[-1] if '/' in scene_raw else scene_raw

        snap_data = {
            'snap_id': snap.get('SnapshotId'),
            'main_chars': main_chars,
            'main_text': main_comment,
            'rarity': rarity_map.get(rarity_code, f"未知({rarity_code})"),
            'category': "生日限定" if is_birthday else "常驻",
            'scene_raw': scene_raw,
            'comments': []
        }

        for i in range(1, 5):
            s_id = snap.get(f'StickyNoteId{i}', 0)
            if s_id > 0 and s_id in sticky_notes:
                snap_data['comments'].append(sticky_notes[s_id])

        processed_snaps.append(snap_data)

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(processed_snaps, f, ensure_ascii=False, indent=4)
    print(f"[+] 提取完成！发现了 {len(processed_snaps)} 张相片。请运行 strip_snap_data.py。")

if __name__ == '__main__':
    main()