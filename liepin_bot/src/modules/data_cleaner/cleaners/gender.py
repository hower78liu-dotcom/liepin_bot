"""
性别要求提取
- 优先扫描"需求人数"，其次"岗位要求"
- 排除"男女不限"等中性词
"""
import re
from typing import Optional

# 排除关键词
_EXCLUDE = ["男女不限", "不限性别", "性别不限", "无论男女", "不限男女"]


def extract_gender(headcount_text: str, requirements_text: str) -> Optional[str]:
    """
    从需求人数和岗位要求中提取性别偏好

    :param headcount_text: 需求人数字段
    :param requirements_text: 岗位要求字段
    :return: "男" | "女" | None
    """
    sources = [str(headcount_text or ""), str(requirements_text or "")]

    for text in sources:
        if not text or text.lower() == "nan":
            continue

        # 先检查排除词
        if any(ex in text for ex in _EXCLUDE):
            return None

        male = bool(re.search(r"男[性士]?(?!\s*女)", text))
        female = bool(re.search(r"女[性士]?(?!\s*男)", text))

        if male and not female:
            return "男"
        if female and not male:
            return "女"

    return None
