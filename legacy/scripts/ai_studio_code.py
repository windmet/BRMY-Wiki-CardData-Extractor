import json
import os
import sys

def extract_hidden_missions(json_path, output_path="hidden_missions_result.txt"):
    print(f"正在读取并解析主数据文件: {json_path} ...")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"读取或解析JSON文件失败。")
        print(f"错误信息: {e}")
        print("请确保传入的是本地完整、格式合规的JSON文件。")
        return

    mission_master = []
    sequence_rewards = []

    # 1. 自动识别多维数组中的“任务主表”与“奖励表”
    # 该逻辑不依赖固定的数组索引，兼容性更强
    if isinstance(data, list):
        for sub_list in data:
            if not isinstance(sub_list, list) or len(sub_list) == 0:
                continue
            first_item = sub_list[0]
            if not isinstance(first_item, dict):
                continue
            
            # 通过特征字段识别
            if "MissionId" in first_item and "Description" in first_item:
                mission_master = sub_list
                print(f"-> 已成功识别到【任务基础主表】(MissionMaster)，共 {len(mission_master)} 条配置。")
            elif "MissionId" in first_item and "IsHidden" in first_item:
                sequence_rewards = sub_list
                print(f"-> 已成功识别到【任务奖励/阶段表】(SequenceReward)，共 {len(sequence_rewards)} 条配置。")
    else:
        print("JSON外层结构不符合预期，请确保其为 [[...], [...]] 的主数据结构。")
        return

    if not mission_master or not sequence_rewards:
        print("未能同时定位到基础主表和奖励表，请检查数据文件完整性。")
        return

    # 2. 建立 MissionId -> 基础配置的映射字典，便于快速检索
    mission_map = {m["MissionId"]: m for m in mission_master}

    hidden_count = 0
    results = []

    # 3. 遍历奖励表，筛选 IsHidden 为 true 的项
    for reward in sequence_rewards:
        is_hidden = reward.get("IsHidden")
        # 兼容布尔值 true 或 数值 1 / "true" 字符串
        if is_hidden is True or is_hidden == 1 or str(is_hidden).lower() == "true":
            # 过滤掉未启用的配置
            if reward.get("IsActive") is False or reward.get("IsActive") == 0:
                continue
                
            mission_id = reward.get("MissionId")
            seq_no = reward.get("MissionSequenceNo")
            border = reward.get("Border")
            
            # 关联主表，获取任务文本
            mission_info = mission_map.get(mission_id)
            if mission_info:
                raw_desc = mission_info.get("Description", "")
                mission_type = mission_info.get("MissionType", "未知")
                
                # 4. 替换文本变量名（游戏通常用 '#' 替换为该阶段的目标数量 Border）
                # 例如将 "ホームで皇坂逢を#回タップした！" 转换为 "ホームで皇坂逢を777回タップした！"
                formatted_desc = raw_desc.replace("#", str(border))
                
                results.append({
                    "MissionId": mission_id,
                    "SequenceNo": seq_no,
                    "MissionType": mission_type,
                    "Border": border,
                    "RawDescription": raw_desc,
                    "FormattedDescription": formatted_desc
                })
                hidden_count += 1

    # 4. 排序并输出结果
    if results:
        # 优先按 MissionId，其次按阶段序号 排序
        results.sort(key=lambda x: (x["MissionId"], x["SequenceNo"]))
        
        try:
            with open(output_path, 'w', encoding='utf-8') as out_f:
                out_f.write(f"=== Break My Case 隐藏任务(Secret)提取结果 (共 {hidden_count} 条) ===\n")
                out_f.write("注：实际明文已将占位符 '#' 替换为对应的隐藏目标值(Border)。\n\n")
                
                for item in results:
                    block = (
                        f"任务ID: {item['MissionId']} (第 {item['SequenceNo']} 阶段) | "
                        f"行为类型(Type): {item['MissionType']} | "
                        f"目标值(Border): {item['Border']}\n"
                        f"原始描述: {item['RawDescription']}\n"
                        f"实际明文: {item['FormattedDescription']}\n"
                        f"{'-'*70}\n"
                    )
                    out_f.write(block)
            print(f"\n[成功] 已提取 {hidden_count} 个隐藏任务节点，明文已写入文件: {output_path}")
        except Exception as e:
            print(f"写入输出文件时失败: {e}")
    else:
        print("\n未在当前数据中检索到有效的隐藏任务记录（IsHidden = true）。")

if __name__ == "__main__":
    # 支持命令行参数，如：python extract_hidden_missions.py my_data.json
    json_file = sys.argv[1] if len(sys.argv) > 1 else "master_data.json"
    
    if os.path.exists(json_file):
        extract_hidden_missions(json_file)
    else:
        print(f"当前目录下未找到文件: '{json_file}'")
        print("使用方法: 请将此脚本置于JSON同级目录下运行，或在命令行中指定路径:")
        print("python extract_hidden_missions.py <您的完整JSON文件名>")