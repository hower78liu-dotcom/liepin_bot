"""
模块名称: data_cleaner
文件: schema.py
功能: 定义 Source → Output 字段映射常量
"""

# ============================================================
# Source 字段名 (Project_list.xlsx 表头)
# ============================================================
SRC_COMPANY = "招聘企业："
SRC_JOB_TITLE = "招聘岗位"
SRC_RESPONSIBILITIES = "岗位职责"
SRC_REQUIREMENTS = "岗位要求"
SRC_HEADCOUNT = "需求人数"
SRC_HARD_CONDITIONS = "简历满足哪些硬性条件可安排面试"
SRC_ADDRESS = "工作地址"
SRC_EDUCATION = "学历要求"
SRC_BENCHMARK = "对标公司"
SRC_SALARY = "薪资"
SRC_SCHEDULE = "作息"
SRC_REMARK = "备注"

# Source Sheet 名称
SRC_SHEET_NAME = "进行中的项目"

# 关键字段 — 若为空则跳过该行
KEY_FIELD = SRC_JOB_TITLE

# ============================================================
# Output 字段名 (Data_Cleaned.xlsx 表头)
# ============================================================
OUT_COMPANY = "公司名称"
OUT_TITLE_ORIGINAL = "职位名称 Original"
OUT_TITLE_CLEANED = "职位名称 Cleaned"
OUT_TITLE_CATEGORY = "职位名称 Category"
OUT_SEARCH_KEYWORDS = "搜索关键词/摘要"
OUT_EXPERIENCE = "经验要求"
OUT_AGE = "年龄要求"
OUT_GENDER = "性别要求"
OUT_CITY = "工作城市"
OUT_EDUCATION = "学历要求"
OUT_SALARY_MONTHLY = "薪资范围 (月)"
OUT_SALARY_YEARLY = "薪资范围 (年)"
OUT_RESUME_DESC = "简历描述对比"
OUT_ACTIVITY = "活跃度"
OUT_ORIGINAL_ROW_ID = "Original_Row_ID"

# Output 字段顺序
OUTPUT_COLUMNS = [
    OUT_ORIGINAL_ROW_ID,
    OUT_COMPANY,
    OUT_TITLE_ORIGINAL,
    OUT_TITLE_CLEANED,
    OUT_TITLE_CATEGORY,
    OUT_SEARCH_KEYWORDS,
    OUT_EXPERIENCE,
    OUT_AGE,
    OUT_GENDER,
    OUT_CITY,
    OUT_EDUCATION,
    OUT_SALARY_MONTHLY,
    OUT_SALARY_YEARLY,
    OUT_RESUME_DESC,
    OUT_ACTIVITY,
]

# 活跃度默认值
DEFAULT_ACTIVITY = "7天内活跃"
