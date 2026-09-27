import json
import os

# 配置文件名
INPUT_JSON = 'master_data.json'
OUTPUT_JSON = 'birthday_extract.json'
TARGET_CYCLE = 3  # 目标提取轮次 (三轮)

def main():
    print(f"[*] 正在加载数据库 {INPUT_JSON}...")
    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[+] 数据库加载成功！")
    except Exception as e:
        print(f"[!] 错误: {e}")
        return

    print(f"[*] 正在提取第 {TARGET_CYCLE} 轮角色档案与生日庆典文本...")
    
    characters = {}         # 存储角色信息: {id: {name, month, day}}
    raw_birthday_texts = {} # 临时存储所有生日台词: {id: {year: {text_no: text}}}

    # 深度递归扫描函数
    def scan_obj(obj):
        if isinstance(obj, dict):
            # 1. 抓取角色基础信息 (限定 1~21 号角色)
            if 'CharacterId' in obj and 'CharacterNameJpn' in obj and 'BirthMonth' in obj:
                cid = obj['CharacterId']
                if 1 <= cid <= 21:
                    characters[cid] = {
                        "Name": obj['CharacterNameJpn'],
                        "Month": obj['BirthMonth'],
                        "Day": obj['BirthDay']
                    }
            
            # 2. 抓取所有年份的生日庆典台词
            if 'CharacterBirthdayTextNo' in obj and 'Text' in obj and 'Year' in obj:
                cid = obj.get('CharacterId')
                year = obj.get('Year')
                text_no = obj.get('CharacterBirthdayTextNo')
                if cid and year and text_no:
                    if cid not in raw_birthday_texts:
                        raw_birthday_texts[cid] = {}
                    if year not in raw_birthday_texts[cid]:
                        raw_birthday_texts[cid][year] = {}
                    raw_birthday_texts[cid][year][text_no] = obj['Text']
            
            for v in obj.values():
                scan_obj(v)
        elif isinstance(obj, list):
            for item in obj:
                scan_obj(item)

    scan_obj(data)

    # ========================================================
    # 核心修复逻辑：根据角色生日所在的周期，动态匹配第 3 轮（三轮）的目标年份
    # ========================================================
    # 三轮起航点为 2026年5月14日（祠堂恭耶生日）：
    # - 5月14日 ~ 12月31日 生日的角色：三轮生日年份为 2026 年
    # - 1月1日 ~ 5月13日 生日的角色：三轮生日年份为 2027 年
    # ========================================================
    birthday_texts = {} # 过滤后的第 3 轮台词

    for cid, info in characters.items():
        month = info["Month"]
        day = info["Day"]
        
        # 计算该角色在第 3 轮对应的具体年份
        if (month > 5) or (month == 5 and day >= 14):
            target_year = 2026
        else:
            target_year = 2027
            
        # 获取该角色对应目标年份的台词
        cid_texts = raw_birthday_texts.get(cid, {}).get(target_year, {})
        birthday_texts[cid] = cid_texts

    # 汇总数据
    extracted_data = {
        "TargetCycle": TARGET_CYCLE,
        "Characters": characters,
        "BirthdayTexts": birthday_texts
    }

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)
        
    print(f"[+] 提取完成！共找到 {len(characters)} 个角色的档案，并已动态过滤出第 {TARGET_CYCLE} 轮（三轮）生日台词。")
    print(f"[+] 数据已保存至: {OUTPUT_JSON}")

if __name__ == "__main__":
    main()