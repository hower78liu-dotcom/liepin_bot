import pandas as pd
import os
import sys

# 将机器人目录加入路径以便导入
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from condition_normalizer import normalize_condition
from ai_normalizer import ai_judge_category, ai_judge_experience

def regenerate_data():
    # 核心路径修正
    input_path = r"D:\ljg\Antigravity\Files\Input\Project_list.xlsx"
    output_path = r"D:\ljg\Antigravity\Files\Output\test_search.xlsx"
    
    # 检测并处理输出锁定
    try:
        if os.path.exists(output_path):
            with open(output_path, 'a'): pass
    except IOError:
        print("警告: 目标文件 test_search.xlsx 已打开，将生成至 test_search_optimized.xlsx")
        output_path = r"D:\ljg\Antigravity\Files\Output\test_search_optimized.xlsx"
    
    if not os.path.exists(input_path):
        print(f"错误: 找不到输入文件 {input_path}")
        return

    print(f"正在读取原始数据: {input_path}")
    df = pd.read_excel(input_path)
    
    processed_rows = []
    
    for _, row in df.iterrows():
        raw_data = row.to_dict()
        
        # 1. 基础清洗 (性别、薪资等)
        condition = normalize_condition(raw_data)
        
        # 2. AI 递归研判职位类别
        if not condition.get("职位类别") or condition.get("职位类别") == "其他":
            print(f"正在为职位 '{condition.get('职位名称')}' 研判类别...")
            category = ai_judge_category(
                raw_data.get("岗位职责", ""),
                raw_data.get("岗位要求", ""),
                raw_data.get("硬性条件", "")
            )
            if category:
                condition["职位类别"] = category
        
        # 3. AI 经验深度研判
        if condition.get("经验要求") == "自定义":
            print(f"正在为职位 '{condition.get('职位名称')}' 研判经验...")
            exp_norm = ai_judge_experience(
                raw_data.get("职级", ""),
                raw_data.get("经验要求", ""),
                raw_data.get("岗位职责", "")
            )
            if exp_norm:
                condition["经验要求"] = exp_norm
                
        processed_rows.append(condition)
        
    # 保存结果
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_out = pd.DataFrame(processed_rows)
    df_out.to_excel(output_path, index=False)
    print(f"数据处理完毕，成果已保存至: {output_path}")

if __name__ == "__main__":
    regenerate_data()
