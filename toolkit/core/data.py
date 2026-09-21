"""共享常量：角色映射、稀有度、属性、场景汉化等。"""

CHAR_MAP = {
    1: "皇坂逢", 2: "城瀬由鶴", 3: "須王芦佳", 4: "綾戸恋", 5: "宇京真央",
    6: "樋宮明星", 7: "環野揺", 8: "槻本大河", 9: "壱川春日", 10: "隠岐谷誓",
    11: "節見静", 12: "御門尊", 13: "新開戦", 14: "相沢篠信", 15: "在間樹帆",
    16: "祠堂恭耶", 17: "立科吏来", 18: "恩田灯世", 19: "新名有", 20: "神家",
    21: "麻波麗",
}

NAME_MAP = {
    "皇坂逢": "逢", "城瀬由鶴": "由鶴", "須王芦佳": "芦佳", "綾戸恋": "恋",
    "宇京真央": "真央", "樋宮明星": "明星", "環野揺": "揺", "槻本大河": "大河",
    "壱川春日": "春日", "隠岐谷誓": "誓", "節見静": "静", "御門尊": "尊",
    "新開戦": "戦", "相沢篠信": "篠信", "在間樹帆": "樹帆", "祠堂恭耶": "恭耶",
    "立科吏来": "吏来", "恩田灯世": "灯世", "新名有": "有", "神家": "神家",
    "麻波麗": "麗",
}

# Code 102 was added after the available dump.cs enum. It is the CR rarity used
# by the first Vignette multi-character cards; the raw code is retained in Meta.
RARITY_MAP = {1: "R", 2: "SR", 3: "SSR", 101: "XR", 102: "CR"}
ATTRIBUTE_MAP = {1: "日", 2: "月", 3: "星"}

DEPT_MAP = {
    1: "本部", 2: "交際部", 3: "管理部",
    4: "強行部", 5: "交渉部", 6: "特務部",
}

PIECE_MAP = {
    1: "サンピース（赤色）", 2: "サンピース（桃色）",
    3: "ムーンピース（空色）", 4: "ムーンピース（青色）",
    5: "スターピース（黄色）", 6: "スターピース（緑色）",
}

CHAR_PIECE_MAP = {
    1: "サンピース（赤色）", 6: "サンピース（赤色）", 13: "サンピース（赤色）",
    16: "サンピース（赤色）", 4: "サンピース（桃色）", 10: "サンピース（桃色）",
    19: "サンピース（桃色）", 2: "ムーンピース（空色）", 7: "ムーンピース（空色）",
    8: "ムーンピース（空色）", 11: "ムーンピース（青色）", 17: "ムーンピース（青色）",
    20: "ムーンピース（青色）", 21: "ムーンピース（青色）",
    3: "スターピース（黄色）", 5: "スターピース（黄色）", 9: "スターピース（黄色）",
    12: "スターピース（緑色）", 14: "スターピース（緑色）", 15: "スターピース（緑色）",
    18: "スターピース（緑色）",
}

MAGNITUDE_MAP = {1: "小", 2: "中", 3: "大", 4: "特大", 5: "超特大"}


def translate_scene(raw_scene):
    """场景名汉化。"""
    if not raw_scene or raw_scene == "Unknown_Scene":
        return "通用/无特定场景"

    # 周年特殊场景
    if "2ndBD" in raw_scene:
        return "二周年庆典"
    if "3rdBD" in raw_scene:
        return "三周年庆典"

    area = ""
    if "Bg001" in raw_scene:
        area = "太空赌场"
    elif "Bg002" in raw_scene:
        area = "电玩城"
    elif "Bg003" in raw_scene:
        area = "游乐园"
    elif "Bg004" in raw_scene:
        area = "美式餐厅"

    detail = ""
    if "Slot" in raw_scene:
        detail = "老虎机"
    elif "CardsTower" in raw_scene:
        detail = "扑克塔"
    elif "Roulette" in raw_scene:
        detail = "轮盘赌"
    elif "Sit" in raw_scene:
        detail = "吧台休息"
    elif "Crane" in raw_scene or "Magichand" in raw_scene:
        detail = "抓娃娃机"
    elif "Toy" in raw_scene or "Spring" in raw_scene:
        detail = "摇摇车"
    elif "Talk" in raw_scene:
        detail = "双人聊天"
    elif "BeltConveyor" in raw_scene or "CeilingRail" in raw_scene:
        detail = "传送带"
    elif "IceCream" in raw_scene:
        detail = "冰淇淋车"
    elif "AnimalCar" in raw_scene:
        detail = "动物游览车"
    elif "Panel" in raw_scene:
        detail = "拍照打卡板"
    elif "Viking" in raw_scene:
        detail = "海盗船"
    elif "FerrisWheel" in raw_scene:
        detail = "摩天轮"
    elif "RollerCoaster" in raw_scene:
        detail = "过山车"
    elif "CandyMachine" in raw_scene:
        detail = "糖果机"
    elif "Popcorn" in raw_scene:
        detail = "爆米花机"
    elif "Jukebox" in raw_scene:
        detail = "点唱机"

    if area and detail:
        return f"{area}-{detail}"
    return area or detail or raw_scene


def clean_text(text):
    """统一清洗文本：换行符 → <br>，替换女主名。"""
    import re
    if not text:
        return ""
    text = text.replace('\\n', '<br>').replace('\n', '<br>')
    text = re.sub(r'heroine_?name', '衣都', text, flags=re.IGNORECASE)
    return text


def format_duration(seconds):
    """秒数 → mm:ss 或 h:mm:ss。"""
    if not seconds:
        return "未知"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
