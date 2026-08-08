"""通用 JSON 加载 & 深度递归扫描。"""
import json


def load_json(path):
    """加载 JSON 文件。"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, path):
    """保存 JSON 文件。"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def walk(obj):
    """深度遍历嵌套结构，逐个 yield 每个 dict。

    用法:
        for d in walk(data):
            if 'MusicId' in d and 'DisplayName' in d:
                # 处理音乐数据
    """
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)
