# asc_to_csv/core/compare_export.py
"""
数据对比导出模块

提供数据对比页「导出选中列」功能的数据层逻辑，与UI解耦：

- 时间值格式化：epoch秒浮点数还原为可读字符串
- 公有列名解析：剥离首个下划线前缀
- 列请求匹配：固定复选框列/公有列 -> 实际列名（与绘图逻辑一致）
- 宽表CSV写入：多文件选中列并排、行号对齐、跨文件列名去重
"""

import csv
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from .csv_loader import CSVDataLoader

# 时间列的合法列名（小写比较）
TIME_COLUMN_NAMES = ('time', 'times', 'time[s]')


def strip_column_prefix(column: str) -> str:
    """
    提取数据列的公有名称

    规则：去掉第一个'_'及其之前的部分，
    如 'P5_AvgCellTemp[C]' -> 'AvgCellTemp[C]'；无下划线则保持原名。

    Args:
        column: CSV中的实际列名

    Returns:
        str: 公有列名
    """
    idx = column.find('_')
    if idx >= 0:
        return column[idx + 1:]
    return column


def is_time_column(column: str) -> bool:
    """
    判断列名是否为时间列（Time/Times/Time[s]，不区分大小写）

    Args:
        column: 列名

    Returns:
        bool: 是否为时间列
    """
    return column.lower() in TIME_COLUMN_NAMES


def format_export_time(value) -> str:
    """
    格式化导出的时间值

    epoch秒浮点数（>1e9，即2001年之后）还原为可读字符串
    yyyy/mm/dd h:mm:ss.f；相对秒等其余数值保持原样；
    空值返回空串（兼容Excel）。

    Args:
        value: 时间值（epoch浮点数、相对秒或字符串）

    Returns:
        str: 格式化后的字符串
    """
    if value is None or value == '':
        return ''
    if isinstance(value, (int, float)) and value > 1e9:
        try:
            whole = int(value)
            frac = round((value - whole) * 10)
            if frac == 10:
                whole += 1
                frac = 0
            frac %= 10
            dt = datetime.fromtimestamp(whole)
            date_part = f"{dt.year:04d}/{dt.month:02d}/{dt.day:02d}"
            time_part = f"{dt.hour}:{dt.minute:02d}:{dt.second:02d}"
            return f"{date_part} {time_part}.{frac}"
        except (OSError, OverflowError, ValueError):
            return str(value)
    return str(value)


def read_csv_header(file_path: str) -> List[str]:
    """
    轻量读取CSV表头行（仅第一行）

    按支持的编码依次尝试（与CSVDataLoader一致），用于在导出前
    检查各文件的时间列类型。

    Args:
        file_path: CSV文件路径

    Returns:
        List[str]: 表头列名列表，读取失败返回空列表
    """
    for encoding in CSVDataLoader.SUPPORTED_ENCODINGS:
        try:
            with open(file_path, 'r', newline='', encoding=encoding) as f:
                return next(csv.reader(f), [])
        except (UnicodeDecodeError, UnicodeError):
            continue
        except OSError:
            return []
    return []


def resolve_matching_column(loader: CSVDataLoader, req_type: str, target_col: str,
                            time_col: Optional[str]) -> Optional[str]:
    """
    在已加载文件中解析列请求对应的实际列名（绘图与导出共用）

    Args:
        loader: 已加载的CSV数据加载器
        req_type: 'fixed'（固定复选框列，子串匹配）
            或 'unified'（公有列，剥离规则精确匹配，跳过时间列和非数值列）
        target_col: 目标列名
        time_col: 该文件的时间列名

    Returns:
        Optional[str]: 匹配到的实际列名，未匹配返回None
    """
    if req_type == 'fixed':
        for col in loader.columns:
            if target_col in col:
                return col
        return None
    for col in loader.columns:
        if col == time_col or strip_column_prefix(col) != target_col:
            continue
        values = loader.data[col]
        if values and not isinstance(values[0], (int, float)):
            continue
        return col
    return None


def write_export_csv(output_path: str, time_header: Optional[str], time_values: List,
                     columns: List[Tuple[str, str, List]],
                     progress_callback: Optional[Callable[[int, int], None]] = None) -> Tuple[int, int]:
    """
    将多文件选中列以宽表形式写入CSV文件

    列顺序：共用时间列 + 各文件数据列（按传入顺序）；
    总行数取时间列与各数据列的最大长度，各列按行号对齐，不足留空；
    跨文件原始列名重名时自动追加文件名主干后缀去重。

    Args:
        output_path: 输出文件路径
        time_header: 共用时间列名（None表示不含时间列）
        time_values: 时间数据列表
        columns: [(文件名主干, 原始列名, 数据列表), ...]
        progress_callback: 可选进度回调，参数为 (当前行, 总行数)

    Returns:
        Tuple[int, int]: (总行数, 总列数)
    """
    # 构建表头，跨文件原始列名重名时追加文件名主干后缀
    header = []
    used_names = set()
    if time_header:
        header.append(time_header)
        used_names.add(time_header)
    for stem, raw_name, _ in columns:
        name = raw_name
        if name in used_names:
            candidate = f"{raw_name}({stem})"
            counter = 2
            while candidate in used_names:
                candidate = f"{raw_name}({stem}_{counter})"
                counter += 1
            name = candidate
        used_names.add(name)
        header.append(name)

    # 总行数取所有列的最大长度，行号对齐，不足留空
    lengths = [len(values) for _, _, values in columns]
    if time_header:
        lengths.append(len(time_values))
    max_rows = max(lengths) if lengths else 0

    progress_step = max(1, max_rows // 100)
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row_idx in range(max_rows):
            row = []
            if time_header:
                if row_idx < len(time_values):
                    row.append(format_export_time(time_values[row_idx]))
                else:
                    row.append('')
            for _, _, values in columns:
                if row_idx < len(values):
                    value = values[row_idx]
                    row.append('' if value is None else value)
                else:
                    row.append('')
            writer.writerow(row)
            if progress_callback and row_idx % progress_step == 0:
                progress_callback(row_idx + 1, max_rows)

    return max_rows, len(header)
