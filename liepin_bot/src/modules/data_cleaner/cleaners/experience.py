"""
经验要求提取与标准化
- 数字优先提取
- 中文数字转换
- 标准区间映射
"""
import re
from typing import Optional

# 中文数字映射
_CN_NUM = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十五": 15, "二十": 20,
}

# 应届关键词
_FRESH_KEYWORDS = ["应届", "无经验", "25届", "26届", "24届", "毕业生", "实习"]

# 模糊经验关键词（标记为"自定义"）
_VAGUE_KEYWORDS = ["有相关经验", "一定经验", "相关经验", "有经验", "有工作经验"]


def _cn_to_num(text: str) -> Optional[int]:
    """将中文数字转为阿拉伯数字"""
    for cn, num in sorted(_CN_NUM.items(), key=lambda x: -len(x[0])):
        if cn in text:
            return num
    return None


def _classify_years(years: int) -> str:
    """将年限数字归类到标准区间"""
    if years <= 0:
        return "应届生"
    elif years < 3:
        return "1-3年"
    elif years < 5:
        return "3-5年"
    elif years <= 10:
        return "5-10年"
    else:
        return "10年以上"


def extract_experience(text: str) -> Optional[str]:
    """
    从岗位要求文本中提取经验要求

    :param text: 岗位要求文本
    :return: 标准区间 或 "自定义" 或 None
    """
    if not text or str(text).lower() == "nan":
        return None

    text = str(text)

    # 1. 应届关键词
    for kw in _FRESH_KEYWORDS:
        if kw in text:
            return "应届生"

    # 2. 阿拉伯数字优先：匹配 "X年" / "X-Y年" / "至少X年"
    patterns = [
        r"(\d+)\s*[-~至到]\s*(\d+)\s*年",            # X-Y年
        r"(\d+)\s*年\s*(?:以上|及以上|左右|工作经验)",   # X年以上
        r"至少\s*(\d+)\s*年",                          # 至少X年
        r"(\d+)\s*年\s*(?:以上|及以上)",                # X年以上
        r"(\d+)\s*年",                                 # 单独X年
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            groups = m.groups()
            # 取最小年限作为分类基准
            years = int(groups[0])
            return _classify_years(years)

    # 3. 中文数字："三年以上"、"五年"
    cn_patterns = [
        r"([一二两三四五六七八九十]+)\s*年\s*(?:以上|及以上|左右|工作经验|经验)",
        r"([一二两三四五六七八九十]+)\s*年",
    ]
    for pat in cn_patterns:
        m = re.search(pat, text)
        if m:
            cn_text = m.group(1)
            years = _cn_to_num(cn_text)
            if years is not None:
                return _classify_years(years)

    # 4. 模糊关键词
    for kw in _VAGUE_KEYWORDS:
        if kw in text:
            return "自定义"

    # 5. 无任何经验描述
    return None
