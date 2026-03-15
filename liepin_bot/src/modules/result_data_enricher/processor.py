"""
模块名称: result_data_enricher/processor.py
功能描述: 基于 "职位名称+公司名称+工作城市" 主键组在内存中联接 test_search 简历要求到 Get_result_leipin 数据中。
"""

import pandas as pd
from typing import Tuple
from src.core.logger import LoggerFactory

logger = LoggerFactory.get_logger("result_data_enricher_processor")

def create_join_key(df: pd.DataFrame, title_col: str, company_col: str, city_col: str) -> pd.Series:
    """
    基于三列合并剥离空格统一大写成一个关联键。
    """
    key_series = (df[title_col].astype(str) + df[company_col].astype(str) + df[city_col].astype(str))
    return key_series.str.strip().str.upper()

def process(df_target: pd.DataFrame, df_source: pd.DataFrame) -> Tuple[pd.DataFrame, int, int]:
    """
    合并源表 DataFrame 中 "简历描述对比" 与 "薪资范围" 数据至目标表 DataFrame，利用 df_target 左联。
    
    :return: (合并后的目标表DataFrame, 匹配成功的行数, 未能匹配的行数)
    """
    # 1. 对来源列进行清洗处理 (去除不可见空格)
    df_src_clean = df_source.copy()
    df_src_clean.columns = [str(c).strip() for c in df_src_clean.columns]
    
    # 2. 建立 df_source (test_search) 联接键
    df_src_clean['join_key'] = create_join_key(df_src_clean, "职位名称", "公司名称", "工作城市")
    
    # 3. 准备子集：包含联接键、简历描述对比 以及 薪资范围
    # 检查是否存在 "薪资范围"
    if "薪资范围" not in df_src_clean.columns:
        logger.warning("源文件中缺失 '薪资范围' 列，将无法回填该字段。")
        df_src_subset = df_src_clean[['join_key', '简历描述对比']]
    else:
        df_src_subset = df_src_clean[['join_key', '简历描述对比', '薪资范围']]
    
    # 4. 对源记录基于复合主键去重，保留第一行
    initial_src_len = len(df_src_subset)
    df_src_subset = df_src_subset.drop_duplicates(subset=['join_key'], keep='first')
    if initial_src_len > len(df_src_subset):
        logger.info(f"清洗了 {initial_src_len - len(df_src_subset)} 条原始冗余 test_search.xlsx 复合主键数据。")

    # 5. 建立 df_target (Get_result_leipin) 联接键 
    df_target_clean = df_target.copy()
    df_target_clean.columns = [str(c).strip() for c in df_target_clean.columns]
    df_target_clean['join_key'] = create_join_key(df_target_clean, "职位名称", "公司名称", "工作城市")

    # 6. 执行 Left Join
    df_merged = pd.merge(df_target_clean, df_src_subset, on='join_key', how='left')

    # 7. 计算匹配统计
    matched_count = df_merged['简历描述对比'].notna().sum()
    unmatched_count = len(df_merged) - matched_count

    # 8. 填充空值
    df_merged['简历描述对比'] = df_merged['简历描述对比'].fillna("")
    if "薪资范围" in df_merged.columns:
        # 重命名为目标列名，方便 task.py 读取
        df_merged.rename(columns={"薪资范围": "岗位预算薪资"}, inplace=True)
        df_merged['岗位预算薪资'] = df_merged['岗位预算薪资'].fillna("")

    # 9. 移除临时的 join_key 防污染输出
    if 'join_key' in df_merged.columns:
        df_merged.drop(columns=['join_key'], inplace=True)

    return df_merged, matched_count, unmatched_count
