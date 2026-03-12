import re

def normalize_condition(row_data):
    """
    清洗传入的 Excel 搜索条件，对齐猎聘的前端枚举值体系。
    """
    cleaned = dict(row_data) # 防止污染原字典
    
    # === 1. 性别要求优化 (优先扫描需求人数，其次岗位要求) ===
    gender_final = None
    gender_sources = [
        str(cleaned.get("需求人数", "")),
        str(cleaned.get("岗位要求", ""))
    ]
    
    exclude_keywords = ["男女不限", "不限性别", "不限", "无论男女"]
    
    for source_text in gender_sources:
        if not source_text or source_text.lower() == "nan":
            continue
            
        if any(ex in source_text for ex in exclude_keywords):
            gender_final = None
            break
            
        male_hits = re.findall(r'男|男性|男士', source_text)
        female_hits = re.findall(r'女|女性|女士', source_text)
        
        if male_hits and not female_hits:
            gender_final = "男"
            break
        elif female_hits and not male_hits:
            gender_final = "女"
            break
        elif male_hits and female_hits:
            gender_final = None
            break
            
    cleaned["性别要求"] = gender_final

    # === 2. 薪资归一化 ===
    salary_raw = str(cleaned.get("薪资范围", "")).strip()
    if salary_raw and salary_raw.lower() != "nan":
        cleaned["薪资范围"] = normalize_salary(salary_raw)
    else:
        cleaned["薪资范围"] = None

    # === 学历清洗 (提取核心词汇) ===
    edu = str(cleaned.get("学历要求", "")).strip()
    if edu and edu.lower() != "nan":
        if "博士" in edu:
            cleaned["学历要求"] = "博士/博士后"
        elif "硕士" in edu:
            cleaned["学历要求"] = "硕士"
        elif "本科" in edu:
            cleaned["学历要求"] = "本科"
        elif "大专" in edu or "专科" in edu:
            cleaned["学历要求"] = "大专"
        elif "高中" in edu:
            cleaned["学历要求"] = "高中"
        elif "中专" in edu or "中技" in edu:
            cleaned["学历要求"] = "中专/中技"
        elif "初中" in edu:
            cleaned["学历要求"] = "初中及以下"
        else:
            cleaned["学历要求"] = None

    # === 工作经验清洗 ===
    exp = str(cleaned.get("经验要求", "")).strip()
    if exp and exp.lower() != "nan":
        if "不限" in exp:
            cleaned["经验要求"] = "经验不限"
        elif "应届" in exp:
            cleaned["经验要求"] = "应届生"
        elif exp == "自定义":
            cleaned["经验要求"] = "自定义"
        else:
            nums = re.findall(r'\d+', exp)
            if len(nums) == 1:
                if "以下" in exp or "以内" in exp:
                    cleaned["经验要求"] = f"0-{nums[0]}"
                elif "以上" in exp:
                    cleaned["经验要求"] = f"{nums[0]}-99"
                else: 
                     cleaned["经验要求"] = f"{nums[0]}-{nums[0]}"
            elif len(nums) >= 2:
                cleaned["经验要求"] = f"{nums[0]}-{nums[1]}"
            else:
                 cleaned["经验要求"] = "自定义"
                 
    # === 年龄要求清洗 ===
    age = str(cleaned.get("年龄要求", "")).strip()
    if age and age.lower() != "nan":
        nums = re.findall(r'\d+', age)
        if len(nums) == 1:
            if "以下" in age or "内" in age:
                cleaned["年龄要求"] = f"16-{nums[0]}"
            elif "以上" in age:
                cleaned["年龄要求"] = f"{nums[0]}-65" 
            else:
                cleaned["年龄要求"] = f"{nums[0]}-{nums[0]}"
        elif len(nums) >= 2:
            cleaned["年龄要求"] = f"{nums[0]}-{nums[1]}"
        else:
             cleaned["年龄要求"] = None
             
    # 处理基础清洗
    if pd_isna_mock(cleaned.get("工作城市")): cleaned["工作城市"] = None
    if pd_isna_mock(cleaned.get("职位名称")): cleaned["职位名称"] = None

    if cleaned.get("职位名称"):
        job_title = str(cleaned["职位名称"]).strip()
        cleaned["职位名称"] = job_title

    return cleaned

def normalize_salary(salary_str):
    """
    薪资归一化
    """
    if not salary_str: return None
    salary_str = salary_str.upper()
    has_w = 'W' in salary_str
    parts = re.split(r'[-~]', salary_str)
    normalized_nums = []
    for part in parts:
        num_match = re.search(r'(\d+(\.\d+)?)', part)
        if num_match:
            val = float(num_match.group(1))
            if has_w: val *= 10
            normalized_nums.append(str(int(round(val))))
    if len(normalized_nums) == 1:
        return normalized_nums[0]
    elif len(normalized_nums) >= 2:
        return f"{normalized_nums[0]}-{normalized_nums[1]}"
    return None

def pd_isna_mock(val):
    return val is None or str(val).strip().lower() in ('nan', '', 'none')
