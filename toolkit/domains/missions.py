"""隐藏任务提取 + 导出 XLSX。"""
from ..core.scanner import load_json
from ..core.exporter import write_xlsx, xlsx_path
from ..core.tables import TableCatalog

INPUT_JSON = 'master_data.json'


def run(session=None):
    tables = session.tables if session else TableCatalog(load_json(INPUT_JSON))
    mission_master = tables.require("mst_mission")
    sequence_rewards = tables.require("mst_mission_sequence")

    mission_map = {m["MissionId"]: m for m in mission_master}
    results = []

    for reward in sequence_rewards:
        is_hidden = reward.get("IsHidden")
        if is_hidden is True or is_hidden == 1 or str(is_hidden).lower() == "true":
            if reward.get("IsActive") is False or reward.get("IsActive") == 0:
                continue
            mission_id = reward.get("MissionId")
            seq_no = reward.get("MissionSequenceNo")
            border = reward.get("Border")
            mission_info = mission_map.get(mission_id)
            if mission_info:
                raw_desc = mission_info.get("Description", "")
                results.append({
                    "MissionId": mission_id, "SequenceNo": seq_no,
                    "MissionType": mission_info.get("MissionType", "未知"),
                    "Border": border, "RawDescription": raw_desc,
                    "FormattedDescription": raw_desc.replace("#", str(border)),
                })

    results.sort(key=lambda x: (x["MissionId"], x["SequenceNo"]))

    headers = ["任务ID", "阶段", "行为类型", "目标值", "原始描述", "实际明文"]
    rows = []
    for item in results:
        rows.append([item["MissionId"], item["SequenceNo"], item["MissionType"],
                     item["Border"], item["RawDescription"], item["FormattedDescription"]])

    out = xlsx_path('hidden_missions.xlsx')
    write_xlsx(rows, out, headers, sheet_title="隐藏任务",
               col_widths={'A': 10, 'B': 8, 'C': 14, 'D': 10, 'E': 50, 'F': 50})
    print(f"[+] 提取 {len(results)} 条隐藏任务 → {out}")
