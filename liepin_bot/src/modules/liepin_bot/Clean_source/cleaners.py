import re

def clean_gender(needs_num_text, job_req_text):
    """
    性别提取逻辑：优先扫描需求人数，其次岗位要求。
    排除“不限”等中性词。
    """
    gender_final = None
    sources = [str(needs_num_text or ""), str(job_req_text or "")]
    exclude_keywords = ["男女不限", "不限性别", "不限", "无论男女"]
    
    for text in sources:
        if not text or text.lower() == "nan":
            continue
        if any(ex in text for ex in exclude_keywords):
            return None
        
        male_hits = re.findall(r'男|男性|男士', text)
        female_hits = re.findall(r'女|女性|女士', text)
        
        if male_hits and not female_hits:
            return "男"
        if female_hits and not male_hits:
            return "女"
            
    return None

def clean_salary(salary_str):
    """
    薪资归一化：强制移除 "/月"，W 转 K，Round 取整。
    """
    if not salary_str or str(salary_str).lower() == "nan":
        return None
        
    salary_str = str(salary_str).upper().replace("/月", "").replace("/MONTH", "")
    has_w = 'W' in salary_str
    
    parts = re.split(r'[-~至]', salary_str)
    nums = []
    for p in parts:
        match = re.search(r'(\d+(\.\d+)?)', p)
        if match:
            val = float(match.group(1))
            if has_w: val *= 10
            nums.append(str(int(round(val))))
            
    if len(nums) >= 2:
        return f"{nums[0]}-{nums[1]}"
    if len(nums) == 1:
        return nums[0]
    return None

def clean_education(edu_text):
    """
    学历向下兼容提取。
    """
    edu = str(edu_text or "").strip()
    if not edu or edu.lower() == "nan":
        return None
        
    # 定义优先级
    patterns = [
        (r"博士", "博士"),
        (r"硕士|研究生", "硕士"),
        (r"本科|统招|211|985", "本科"),
        (r"大专|专科", "大专"),
        (r"高中", "高中"),
        (r"中专|中技", "中专/中技")
    ]
    
    for pattern, target in patterns:
        if re.search(pattern, edu):
            return target
    return None

def clean_city(city_text):
    """
    仅保留地级市名称（不含行政区后缀）。
    """
    city = str(city_text or "").strip()
    if not city or city.lower() == "nan":
        return None
    
    # 移除省份、区、县后缀
    city = re.split(r'[省市区县]', city)[0]
    return city
