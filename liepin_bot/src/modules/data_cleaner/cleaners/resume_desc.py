"""
简历描述合并
- 岗位职责 + 岗位要求 + 硬性条件
- 换行符分隔
"""
from typing import Optional


def merge_resume_description(
    responsibilities: str,
    requirements: str,
    hard_conditions: str,
) -> Optional[str]:
    """
    合并三个字段为简历描述

    :return: 换行分隔的合并文本
    """
    parts = []
    for label, text in [
        ("【岗位职责】", responsibilities),
        ("【岗位要求】", requirements),
        ("【硬性条件】", hard_conditions),
    ]:
        val = str(text or "").strip()
        if val and val.lower() != "nan":
            parts.append(f"{label}\n{val}")

    return "\n\n".join(parts) if parts else None
