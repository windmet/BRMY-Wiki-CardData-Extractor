import sys
import os
import decrypt_s2b
import card
import data_strip

def run():
    print("========================================")
    print("      Wiki 卡牌数据全自动提取工具       ")
    print("========================================\n")

    if len(sys.argv) > 1:
        s2b_file = sys.argv[1]
    else:
        s2b_file = input("请把 master_data.s2b 拖拽到这里，然后按回车：").strip('\"\'')
        
    if not os.path.exists(s2b_file):
        print(f"[!] 找不到文件: {s2b_file}")
        os.system("pause")
        return

    out_dir = os.path.dirname(s2b_file) or "."
    base_name = os.path.splitext(os.path.basename(s2b_file))[0]
    
    master_json = os.path.join(out_dir, "master_data.json")
    all_cards_json = os.path.join(out_dir, "All_Cards_Database.json")
    xlsx_out = os.path.join(out_dir, f"{base_name}_cards_data.xlsx")

    try:
        print("\n[步骤 1/3] 解密 s2b 源文件...")
        decrypt_s2b.main(s2b_file, master_json)
        
        print("\n[步骤 2/3] 提取并精修卡牌技能数据库...")
        card.main(master_json, all_cards_json)
        
        print("\n[步骤 3/3] 生成原生 Excel 表格...")
        data_strip.main(all_cards_json, xlsx_out)
        
        print(f"\n[√] 完美搞定！")
        print(f"所有数据已整理在 {out_dir} 目录下。")
        
    except Exception as e:
        print(f"\n[!] 发生错误: {e}")
        
    print("\n按任意键退出...")
    os.system("pause")

if __name__ == "__main__":
    run()