import json
import time
from deepdiff import DeepDiff
import pprint

# 【配置参数】请把这里的文件名改成你实际的文件名
FILE_1 = "data1.json"
FILE_2 = "data2.json"
OUTPUT_FILE = "diff_result.txt"

def main():
    start_time = time.time()
    
    # 1. 读取文件
    print(f"[{time.strftime('%H:%M:%S')}] 1. 正在加载本地 JSON 文件...")
    try:
        with open(FILE_1, "r", encoding="utf-8") as f1, \
             open(FILE_2, "r", encoding="utf-8") as f2:
            data1 = json.load(f1)
            data2 = json.load(f2)
    except Exception as e:
        print(f"❌ 读取文件失败，请检查文件名和编码。错误信息: {e}")
        return

    # 2. 开始比对
    print(f"[{time.strftime('%H:%M:%S')}] 2. 正在进行深度比对（40MB+ 文件由于结构复杂，可能需要 10-30 秒，请耐心等待）...")
    
    # ignore_order=True: 忽略数组/列表内部的顺序差异（如果只是顺序变了但内容没变，不报错）
    # view='tree': 方便后续高阶处理，默认即可
    diff = DeepDiff(data1, data2, ignore_order=True)

    # 3. 输出结果
    print(f"[{time.strftime('%H:%M:%S')}] 3. 比对完成！正在将差异写入 {OUTPUT_FILE}...")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        if not diff:
            out.write("两个 JSON 文件内容完全一致！\n")
            print("🎉 两个文件完全一致！")
        else:
            # 使用 pprint 让输出的差异结果带缩进，人类可读性极高
            out.write("====== JSON 差异对比报告 ======\n\n")
            out.write(pprint.pformat(diff, indent=2))
            print(f"💾 差异报告已成功生成：{OUTPUT_FILE}")

    end_time = time.time()
    print(f"⏱️ 总共耗时: {end_time - start_time:.2f} 秒")

if __name__ == "__main__":
    main()