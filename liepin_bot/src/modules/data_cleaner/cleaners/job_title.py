"""
职位名称清洗模块
- 正则剔除括号及内容、"备注："后文本
- 职级词汇剥离（仅剥离前缀型修饰词，保护"项目经理"等完整职位名）
- 返回 (cleaned_title, level)
"""
import re
from typing import Tuple, Optional

# 纯前缀型职级词（只在标题开头或作为修饰词出现时才剥离）
_PREFIX_LEVELS = [
    "首席", "总监", "VP", "Director",
    "资深", "高级", "Senior", "Sr.",
    "中级", "中高级",
    "初级", "Junior", "Jr.",
    "Leader", "实习",
]

# 复合职位词保护表 — 这些词虽含职级词但本身是完整职位名，不可拆分
_PROTECTED_TITLES = [
    "项目经理", "产品经理", "客户经理", "总经理", "副总经理",
    "技术经理", "研发经理", "质量经理", "生产经理", "采购经理",
    "销售经理", "市场经理", "财务经理", "人事经理", "运营经理",
    "项目主管", "技术主管", "生产主管", "质量主管",
    "销售助理", "行政助理", "总裁助理", "总经理助理",
    "技术总监", "研发总监", "销售总监", "运营总监", "财务总监",
    "副总工", "总工程师", "副总裁",
]

# 编译前缀职级正则
_PREFIX_PATTERN = re.compile(
    r"^(?:" + "|".join(re.escape(kw) for kw in _PREFIX_LEVELS) + r")\s*",
    re.IGNORECASE,
)


def clean_job_title(raw_title: str) -> Tuple[str, Optional[str]]:
    """
    清洗职位名称

    :param raw_title: 原始职位名称
    :return: (cleaned_title, level) — level 为剥离出的职级词，无则 None
    """
    if not raw_title or str(raw_title).lower() == "nan":
        return ("", None)

    text = str(raw_title).strip()

    # 1. 删除"备注："及之后的所有文本
    text = re.split(r"备注[：:]", text, maxsplit=1)[0].strip()

    # 2. 删除所有括号及其内容  () （）
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"（[^）]*）", "", text)
    text = text.strip()

    # 3. 检查是否属于受保护的完整职位名
    is_protected = False
    for pt in _PROTECTED_TITLES:
        if pt in text:
            is_protected = True
            break

    # 4. 剥离前缀型职级词
    level = None
    cleaned = text

    if not is_protected:
        m = _PREFIX_PATTERN.search(text)
        if m:
            level = m.group(0).strip()
            cleaned = _PREFIX_PATTERN.sub("", text).strip()

    # 5. 清理多余空格和分隔符
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = cleaned.strip("/-、·")

    # 6. 边界保护：如果剥离后核心词过短（<=1字），回退
    if len(cleaned) <= 1:
        cleaned = re.sub(r"\s+", "", text).strip("/-、·")

    return (cleaned, level)
