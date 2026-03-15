"""
核心处理器 — 遍历 DataFrame，逐行调用清洗函数
"""
import pandas as pd
from typing import Dict, Any

from src.core.logger import LoggerFactory

from .schema import (
    SRC_COMPANY, SRC_JOB_TITLE, SRC_RESPONSIBILITIES, SRC_REQUIREMENTS,
    SRC_HEADCOUNT, SRC_HARD_CONDITIONS, SRC_ADDRESS, SRC_EDUCATION, SRC_SALARY,
    OUT_COMPANY, OUT_TITLE_ORIGINAL, OUT_TITLE_CLEANED, OUT_TITLE_CATEGORY,
    OUT_SEARCH_KEYWORDS, OUT_EXPERIENCE, OUT_AGE, OUT_GENDER, OUT_CITY,
    OUT_EDUCATION, OUT_SALARY_MONTHLY, OUT_SALARY_YEARLY, OUT_RESUME_DESC,
    OUT_ACTIVITY, DEFAULT_ACTIVITY, OUT_ORIGINAL_ROW_ID,
)
from .cleaners.job_title import clean_job_title
from .cleaners.experience import extract_experience
from .cleaners.age import extract_age
from .cleaners.city import extract_cities
from .cleaners.education import standardize_education
from .cleaners.gender import extract_gender
from .cleaners.salary import standardize_salary
from .cleaners.resume_desc import merge_resume_description
from .ai_engine import classify_job_category, ai_judge_experience

logger = LoggerFactory.get_logger("data_cleaner")


def _safe_str(val) -> str:
    """安全转字符串，NaN 返空串"""
    if pd.isna(val):
        return ""
    return str(val).strip()


def process(df: pd.DataFrame) -> pd.DataFrame:
    """
    执行全量清洗流程

    :param df: 有效行的原始 DataFrame
    :return: 清洗后的 DataFrame（含 OUTPUT_COLUMNS 所有列）
    """
    import re
    from .cleaners.city import CHINA_CITIES
    results = []
    total = len(df)

    for idx, row in df.iterrows():
        try:
            record = _process_single_row(row, idx)
            results.append(record)

            # 每 10 行输出进度
            if (idx + 1) % 10 == 0:
                logger.info(f"📊 进度: {idx + 1}/{total}")

        except Exception as e:
            logger.error(f"⚠️ 第 {idx + 1} 行处理异常，已跳过: {e}")
            continue

    logger.info(f"✅ 基础清洗完毕，共处理 {len(results)}/{total} 行，开始执行城市二次处理...")
    df_res = pd.DataFrame(results)

    if not df_res.empty and OUT_CITY in df_res.columns:
        import cpca

        # 1. 字符串解析：按中英文逗号、空格分词，转为 list
        df_res[OUT_CITY] = df_res[OUT_CITY].apply(
            lambda x: [c.strip() for c in re.split(r'[，、\s,]+', str(x)) if c.strip()]
            if pd.notna(x) and str(x).lower() != 'nan' else []
        )

        def _normalize_city_list(city_list):
            if not city_list:
                return []
            
            # 使用 cpca 进行地理位置解析
            transformed_df = cpca.transform(city_list)
            normalized_cities = []
            
            for i, row_data in transformed_df.iterrows():
                original_word = city_list[i]
                prov = str(row_data.get('省', '')).strip()
                city = str(row_data.get('市', '')).strip()
                
                # 如果完全无法识别（省市区均为空），则保留原词并报警
                if not prov and not city and not str(row_data.get('区', '')).strip():
                    logger.warning(f"⚠️ 无法识别地理词汇，已保留原词: '{original_word}'")
                    normalized_cities.append(original_word)
                    continue
                
                target_name = ""
                # 直辖市逻辑：北京、上海、天津、重庆 -> 取"省"
                if prov in ['北京市', '上海市', '天津市', '重庆市']:
                    target_name = prov
                # 特别行政区、省直辖县等特殊情况，市为空时取"省"或保留原词
                elif not city or city == '市辖区':
                    target_name = prov if prov else original_word
                else:
                    # 正常的地级市
                    target_name = city

                if target_name:
                    # 剃除后缀
                    clean_name = re.sub(r'(市|区|县|地区|自治州)$', '', target_name)
                    normalized_cities.append(clean_name)
                else:
                    # 兜底
                    normalized_cities.append(original_word)

            # 集合去重 (消除由行政隶属关系产生的重复，保留顺序)
            # 使用 dict.fromkeys 来保持原顺去重
            return list(dict.fromkeys(normalized_cities))

        # 2. 行政层级归并 & 集合去重
        df_res[OUT_CITY] = df_res[OUT_CITY].apply(_normalize_city_list)

        # 3. 分行平铺 (Explode)
        df_res = df_res.explode(OUT_CITY)
        
        # 将空 list 或 NA 统一处理为空字符串并重置索引
        df_res[OUT_CITY] = df_res[OUT_CITY].apply(lambda x: x if pd.notna(x) else "")
        df_res = df_res.reset_index(drop=True)

    logger.info(f"✅ 城市二次处理完毕(CPCA增强版)，最终数据量: {len(df_res)} 行")
    return df_res


def _process_single_row(row: pd.Series, idx: int) -> Dict[str, Any]:
    """处理单行数据"""
    raw_title = _safe_str(row.get(SRC_JOB_TITLE))
    responsibilities = _safe_str(row.get(SRC_RESPONSIBILITIES))
    requirements = _safe_str(row.get(SRC_REQUIREMENTS))
    headcount = _safe_str(row.get(SRC_HEADCOUNT))
    hard_conditions = _safe_str(row.get(SRC_HARD_CONDITIONS))
    address = _safe_str(row.get(SRC_ADDRESS))
    education = _safe_str(row.get(SRC_EDUCATION))
    salary = _safe_str(row.get(SRC_SALARY))

    # 1. 职位名称清洗
    cleaned_title, level = clean_job_title(raw_title)

    # 2. 职位分类
    category = classify_job_category(cleaned_title, responsibilities, requirements)

    # 3. 搜索关键词
    search_keywords = f"{cleaned_title} {category}" if category else cleaned_title

    # 4. 经验要求
    exp = extract_experience(requirements)
    # 如果是"自定义"，尝试 AI 研判
    if exp == "自定义" and level:
        ai_exp = ai_judge_experience(level, exp, responsibilities)
        if ai_exp:
            exp = ai_exp

    # 5. 年龄要求
    age = extract_age(requirements)

    # 6. 性别要求
    gender = extract_gender(headcount, requirements)

    # 7. 工作城市
    city = extract_cities(address)

    # 8. 学历标准化
    edu = standardize_education(education)

    # 9. 薪资标准化
    monthly, yearly = standardize_salary(salary)

    # 10. 简历描述合并
    resume_desc = merge_resume_description(
        responsibilities, requirements, hard_conditions
    )
    
    # 构造 Original_Row_ID
    # 如: "Row_1_广州，西安、成都郫都区" -> 注意 idx 这里是 0-indexed，一般加2对应 Excel 行号（1表头，2起始），或者简单用 idx+1
    row_id_val = f"Row_{idx + 2}"
    if city and str(city).lower() != "nan":
        row_id_val = f"{row_id_val}_{str(city)}"

    return {
        OUT_ORIGINAL_ROW_ID: row_id_val,
        OUT_COMPANY: _safe_str(row.get(SRC_COMPANY)),
        OUT_TITLE_ORIGINAL: raw_title,
        OUT_TITLE_CLEANED: cleaned_title,
        OUT_TITLE_CATEGORY: category,
        OUT_SEARCH_KEYWORDS: search_keywords,
        OUT_EXPERIENCE: exp,
        OUT_AGE: age,
        OUT_GENDER: gender,
        OUT_CITY: city,
        OUT_EDUCATION: edu,
        OUT_SALARY_MONTHLY: monthly,
        OUT_SALARY_YEARLY: yearly,
        OUT_RESUME_DESC: resume_desc,
        OUT_ACTIVITY: DEFAULT_ACTIVITY,
    }
