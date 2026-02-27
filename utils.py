# asc_to_csv/utils.py
"""
工具函数模块
包含通用工具函数
"""

import re
from typing import Any


def extract_batp_group(signal_name: str) -> str:
    """
    从信号名称中提取分组标识
    
    分组规则：
    - BatP数字模式（如BatP3、BatP4等）-> 对应分组
    - BATPQ模式 -> BATPQ分组
    - BATPS模式 -> BATPS分组
    - 其他 -> Other分组
    
    Args:
        signal_name: 完整的信号名称
        
    Returns:
        str: 分组标识
    
    Examples:
        >>> extract_batp_group("800V_BMS_PCAN_V2.5.3.dbc::BatP3_BMS_CellVoltMaxMin::P3_AvgCellVlt")
        'BatP3'
        >>> extract_batp_group("xxx::BATPQ_xxx::signal")
        'BATPQ'
        >>> extract_batp_group("xxx::BATPS_xxx::signal")
        'BATPS'
    """
    batpq_match = re.search(r'BATPQ', signal_name, re.IGNORECASE)
    if batpq_match:
        return "BATPQ"
    
    batps_match = re.search(r'BATPS', signal_name, re.IGNORECASE)
    if batps_match:
        return "BATPS"
    
    batp_match = re.search(r'(BatP\d+)', signal_name)
    if batp_match:
        return batp_match.group(1)
    
    return "Other"


def safe_value(value: Any) -> Any:
    """
    安全转换值，确保可以写入CSV文件
    
    Args:
        value: 原始值
        
    Returns:
        Any: 转换后的值
    
    Examples:
        >>> safe_value(None)
        ''
        >>> safe_value(123.456)
        123.456
        >>> safe_value('Standby')
        'Standby'
    """
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value
    return str(value)


def sort_group_key(name: str) -> tuple:
    """
    分组排序键函数
    
    排序规则：
    - BatP数字组按数字升序排列
    - BATPQ排在BatP组之后
    - BATPS排在BATPQ之后
    - Other排在最后
    
    Args:
        name: 分组名称
        
    Returns:
        tuple: 排序键
    
    Examples:
        >>> sort_group_key("BatP3")
        (0, 3)
        >>> sort_group_key("BATPQ")
        (1, 0)
        >>> sort_group_key("BATPS")
        (2, 0)
        >>> sort_group_key("Other")
        (3, 'Other')
    """
    if name.startswith("BatP"):
        return (0, int(name[4:]))
    elif name == "BATPQ":
        return (1, 0)
    elif name == "BATPS":
        return (2, 0)
    return (3, name)
