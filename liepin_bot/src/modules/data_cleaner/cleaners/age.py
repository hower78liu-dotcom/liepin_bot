"""
年龄要求提取
- 从岗位要求文本中提取年龄限制
"""
import re
from typing import Optional


def extract_age(text: str) -> Optional[str]:
    """
    从岗位要求文本提取年龄限制

    :param text: 岗位要求文本
    :return: 如 "35岁以下"、"28-40岁" 或 None
    """
    if not text or str(text).lower() == "nan":
        return None

    text = str(text)

    # 模式1：X岁以下 / X岁以内
    m = re.search(r"(\d{2})\s*岁?\s*(?:以下|以内|及以下)", text)
    if m:
        return f"{m.group(1)}岁以下"

    # 模式2：X-Y岁
    m = re.search(r"(\d{2})\s*[-~至到]\s*(\d{2})\s*岁", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}岁"

    # 模式3：不超过X岁
    m = re.search(r"不超过\s*(\d{2})\s*岁", text)
    if m:
        return f"{m.group(1)}岁以下"

    # 模式4：年龄X岁
    m = re.search(r"年龄\s*(\d{2})\s*岁", text)
    if m:
        return f"{m.group(1)}岁以下"

    return None
