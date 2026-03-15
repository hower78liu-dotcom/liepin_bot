import pandas as pd
from .cleaners import clean_gender, clean_salary, clean_education, clean_city
from .ai_engine import ai_judge_category, ai_judge_experience

class DataProcessor:
    """
    通用的数据清洗与标准化处理器。
    """
    def __init__(self, df):
        self.df = df.copy()

    def process(self):
        """执行全量清洗流程"""
        processed_data = []
        for index, row in self.df.iterrows():
            item = row.to_dict()
            
            # 1. 性别要求
            item["性别要求"] = clean_gender(item.get("需求人数"), item.get("岗位要求"))
            
            # 2. 薪资归一化
            item["薪资范围"] = clean_salary(item.get("薪资范围"))
            
            # 3. 学历与城市
            item["学历要求"] = clean_education(item.get("学历要求"))
            item["工作城市"] = clean_city(item.get("工作城市"))
            
            # 4. 工作经验基础提取与自定义深度研判
            exp = str(item.get("经验要求") or "")
            if "自定义" in exp or (not exp or exp.lower() == "nan"):
                # 尝试 AI 深度研判
                ai_exp = ai_judge_experience(item.get("职级"), exp, item.get("岗位职责"))
                if ai_exp:
                    item["经验要求"] = ai_exp
            
            # 5. 职位类别递归判定
            cat = str(item.get("职位类别") or "")
            if not cat or cat == "其他" or cat.lower() == "nan":
                # 尝试 AI 语义研判
                ai_cat = ai_judge_category(item.get("岗位职责"), item.get("岗位要求"), item.get("硬性条件"))
                if ai_cat:
                    item["职位类别"] = ai_cat
                    
            processed_data.append(item)
            
        return pd.DataFrame(processed_data)
