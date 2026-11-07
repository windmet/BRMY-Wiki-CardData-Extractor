import json
from openpyxl import Workbook

INPUT_JSON = 'intermediate_snaps.json'
OUTPUT_XLSX = 'Snap_Wiki_Data_Clean.xlsx'

# 场景汉化字典 (已全面覆盖 Bg001 ~ Bg004)
def translate_scene(raw_scene):
    if not raw_scene or raw_scene == "Unknown_Scene":
        return "通用/无特定场景"
        
    area = ""
    if "Bg001" in raw_scene: area = "太空赌场"
    elif "Bg002" in raw_scene: area = "电玩城"
    elif "Bg003" in raw_scene: area = "游乐园"
    elif "Bg004" in raw_scene: area = "美式餐厅"
    elif "2ndBD" in raw_scene: return "二周年庆典"
    elif "3rdBD" in raw_scene: return "三周年庆典"
    
    detail = ""
    # Bg001
    if "Slot" in raw_scene: detail = "老虎机"
    elif "CardsTower" in raw_scene: detail = "扑克塔"
    elif "Roulette" in raw_scene: detail = "轮盘赌"
    elif "Sit" in raw_scene: detail = "吧台休息"
    # Bg002
    elif "Crane" in raw_scene or "Magichand" in raw_scene: detail = "抓娃娃机"
    elif "Toy" in raw_scene or "Spring" in raw_scene: detail = "摇摇车"
    elif "Talk" in raw_scene: detail = "双人聊天"
    elif "BeltConveyor" in raw_scene or "CeilingRail" in raw_scene: detail = "传送带"
    # Bg003
    elif "IceCream" in raw_scene: detail = "冰淇淋车"
    elif "AnimalCar" in raw_scene: detail = "动物游览车"
    elif "Panel" in raw_scene: detail = "拍照打卡板"
    elif "Viking" in raw_scene: detail = "海盗船"
    elif "FerrisWheel" in raw_scene: detail = "摩天轮"
    elif "RollerCoaster" in raw_scene: detail = "过山车"
    # Bg004
    elif "CandyMachine" in raw_scene: detail = "糖果机"
    elif "Popcorn" in raw_scene: detail = "爆米花机"
    elif "Jukebox" in raw_scene: detail = "点唱机"
    
    if area and detail:
        return f"{area}-{detail}"
    elif area:
        return area
    elif detail:
        return detail
        
    return raw_scene

def main():
    print(f"[*] 正在读取中间数据: {INPUT_JSON} ...")
    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"[!] 读取失败: {e}")
        return

    unique_snaps = {}

    print("[*] 正在执行语义级去重合并...")
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

        semantic_key = (
            scene_name, category, rarity, main_chars, main_text,
            comments[0][0], comments[0][1],
            comments[1][0], comments[1][1],
            comments[2][0], comments[2][1],
            comments[3][0], comments[3][1]
        )

        if semantic_key not in unique_snaps:
            unique_snaps[semantic_key] = {
                'first_id': snap['snap_id'],
                'merged_count': 1
            }
        else:
            unique_snaps[semantic_key]['merged_count'] += 1

    wb = Workbook()
    ws = wb.active
    ws.title = "Snap图鉴数据"

    headers = [
        "首次出现ID", "互动场景", "所属分类", "稀有度", "相片主角", "主文案",
        "评论1_角色", "评论1_文案",
        "评论2_角色", "评论2_文案",
        "评论3_角色", "评论3_文案",
        "评论4_角色", "评论4_文案",
        "折叠重复数"
    ]
    ws.append(headers)

    sorted_snaps = sorted(unique_snaps.items(), key=lambda x: x[1]['first_id'])

    for key, val in sorted_snaps:
        scene_name, category, rarity, main_chars, main_text, \
        c1_n, c1_t, c2_n, c2_t, c3_n, c3_t, c4_n, c4_t = key
        
        row = [
            val['first_id'], 
            scene_name, category, rarity, main_chars, main_text,
            c1_n, c1_t, c2_n, c2_t, c3_n, c3_t, c4_n, c4_t,
            val['merged_count']
        ]
        ws.append(row)

    wb.save(OUTPUT_XLSX)
    print(f"[+] 导出成功！最干净的数据已保存至: {OUTPUT_XLSX}")

if __name__ == '__main__':
    main()