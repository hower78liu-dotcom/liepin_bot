"""
学历要求标准化
- 向下兼容：多学历取最低门槛
- 过滤干扰词（经验、985、统招等）
- 映射至：大专、本科、硕士、博士
"""
import re
from typing import Optional

# 学历等级映射（按门槛从低到高排列）
_EDU_LEVELS = [
    (r"大专|专科|高职", "大专"),
    (r"本科|学士|211|985|统招|全日制", "本科"),
    (r"硕士|研究生|MBA", "硕士"),
    (r"博士|博士后", "博士"),
]

# 向下兼容关键词（表示最低要求可以降低）
_DOWNGRADE_KEYWORDS = ["优秀可看", "优秀可以看", "也可考虑", "亦可", "也行", "也可以"]


def standardize_education(text: str) -> Optional[str]:
    """
    将学历描述标准化为四个等级之一

    :param text: 学历要求文本
    :return: 大专 | 本科 | 硕士 | 博士 | None
    """
    if not text or str(text).lower() == "nan":
        return None

    text = str(text).strip()

    # 检测是否有向下兼容描述
    has_downgrade = any(kw in text for kw in _DOWNGRADE_KEYWORDS)

    # 收集所有匹配到的学历等级
    matched = []
    for pattern, level in _EDU_LEVELS:
        if re.search(pattern, text):
            matched.append(level)

    if not matched:
        return None

    # 向下兼容策略：取最低门槛
    if has_downgrade and len(matched) > 1:
        level_order = ["大专", "本科", "硕士", "博士"]
        matched.sort(key=lambda x: level_order.index(x))
        return matched[0]

    # 正常情况：取提到的第一个学历（通常就是要求的最低学历）
    level_order = ["大专", "本科", "硕士", "博士"]
    matched.sort(key=lambda x: level_order.index(x))
    return matched[0]
