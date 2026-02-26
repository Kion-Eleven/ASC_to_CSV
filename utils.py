# asc_to_csv/utils.py
"""
工具函数模块
包含通用工具函数
"""

import re
from typing import Any


def extract_batp_group(signal_name: str) -> str:
    """
    从信号名称中提取BatP分组标识
    
    Args:
        signal_name: 完整的信号名称
        
    Returns:
        str: 分组标识（如BatP3、BatP4等）
    
    Examples:
        >>> extract_batp_group("800V_BMS_PCAN_V2.5.3.dbc::BatP3_BMS_CellVoltMaxMin::P3_AvgCellVlt")
        'BatP3'
    """
    match = re.search(r'(BatP\d+)', signal_name)
    if match:
        return match.group(1)
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
    
    Args:
        name: 分组名称
        
    Returns:
        tuple: 排序键
    
    Examples:
        >>> sort_group_key("BatP3")
        (0, 3)
        >>> sort_group_key("Other")
        (1, 'Other')
    """
    if name.startswith("BatP"):
        return (0, int(name[4:]))
    return (1, name)