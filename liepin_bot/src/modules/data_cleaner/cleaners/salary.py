"""
薪资范围标准化 — 双列输出
- 月薪 (K)：纯数字 "Min-Max"
- 年薪 (W)：纯数字 "Min-Max"
- 自动识别 K/月、W/年、年薪XXW、*N薪
- W → K 乘 10，默认 12 月，四舍五入取整
"""
import re
from typing import Tuple, Optional


def _parse_salary_months(text: str) -> int:
    """从文本中提取发薪月数，默认 12"""
    m = re.search(r"\*?\s*(\d+)\s*薪", text)
    if m:
        return int(m.group(1))
    return 12


def _extract_numbers(text: str) -> list:
    """提取文本中的所有数字（含小数）"""
    return [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", text)]


def standardize_salary(salary_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    薪资标准化，返回 (monthly_str, yearly_str)

    :param salary_text: 原始薪资文本
    :return: ("15-25", "18-30") 纯数字格式，单位分别为 K/月 和 W/年
    """
    if not salary_text or str(salary_text).lower() == "nan":
        return (None, None)

    text = str(salary_text).strip().upper()
    months = _parse_salary_months(text)

    # 清理干扰文字
    clean = text.replace("，", ",").replace("、", ",")

    # 提取所有数字
    nums = _extract_numbers(clean)
    if not nums:
        return (None, None)

    # 判断输入单位
    is_yearly_input = bool(re.search(r"年薪|/年|年包", clean))
    is_wan = bool(re.search(r"[W万]", clean))
    is_k = bool(re.search(r"K", clean))

    # 统一转为 K/月 的数值列表
    monthly_vals = []

    if is_yearly_input:
        # 年薪输入：先统一为 W，再转 K/月
        for n in nums[:2]:
            wan_val = n if is_wan else n  # 年薪通常已是万元
            if not is_wan and not is_k:
                wan_val = n  # 纯数字年薪通常就是万
            k_monthly = (wan_val * 10) / 12
            monthly_vals.append(k_monthly)
    elif is_wan:
        # 万/月 输入
        for n in nums[:2]:
            k_val = n * 10  # W → K
            monthly_vals.append(k_val)
    elif is_k:
        # K/月 输入
        monthly_vals = [n for n in nums[:2]]
    else:
        # 无单位标识，尝试按数值大小判断
        if nums[0] >= 100:
            # 可能是元/月，转 K
            monthly_vals = [n / 1000 for n in nums[:2]]
        else:
            # 默认当 K 处理
            monthly_vals = [n for n in nums[:2]]

    if not monthly_vals:
        return (None, None)

    # 确保至少有两个值
    if len(monthly_vals) == 1:
        monthly_vals = [monthly_vals[0], monthly_vals[0]]

    # 四舍五入取整
    m_min = round(monthly_vals[0])
    m_max = round(monthly_vals[1])

    # 计算年薪 (W)
    y_min = round(m_min * months / 10)
    y_max = round(m_max * months / 10)

    monthly_str = f"{m_min}-{m_max}" if m_min != m_max else str(m_min)
    yearly_str = f"{y_min}-{y_max}" if y_min != y_max else str(y_min)

    return (monthly_str, yearly_str)
