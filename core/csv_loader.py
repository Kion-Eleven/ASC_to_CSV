# asc_to_csv/core/csv_loader.py
"""
CSV数据加载器模块
负责加载和解析CSV文件，提供数据访问接口

优化版本：
- 支持多种编码自动检测
- 使用正则预检优化类型推断
- 支持分块加载降低内存占用
"""

import csv
import re
from datetime import datetime
from typing import Dict, List, Optional, Iterator, Tuple


MULTI_SELECT_COLUMNS = [
    'MaxCellTemp', 'MinCellTemp', 'PackSOC', 'HvBusVlt', 
    'BranchCrnt', 'PackFltLvl', 'MaxCellVlt', 'MinCellVlt',
    'PackFltCode', 'PackTotCrnt'
]

# 方案7优化：缓存本地时区偏移，用纯算术替代 timestamp() 的系统调用。
# 注意：不能用 datetime(1970,1,1).timestamp()（Windows 上本地时间早于
# 1970-01-01 会抛 OSError），改用远期参考点推算偏移。
_LOCAL_EPOCH_OFFSET: Optional[float] = None
_EPOCH_BASE = datetime(1970, 1, 1)
_EPOCH_REF = datetime(2020, 1, 1)


def _get_local_epoch_offset() -> float:
    """获取本地时区相对 UTC 的 epoch 偏移（缓存，仅计算一次）"""
    global _LOCAL_EPOCH_OFFSET
    if _LOCAL_EPOCH_OFFSET is None:
        _LOCAL_EPOCH_OFFSET = (_EPOCH_REF.timestamp()
                               - (_EPOCH_REF - _EPOCH_BASE).total_seconds())
    return _LOCAL_EPOCH_OFFSET


def read_csv_column_sample(file_path: str, sample_rows: int = 50) -> Optional[List[str]]:
    """
    轻量读取CSV文件的列信息（仅读取表头和少量采样数据行）

    用于在不加载整个文件的情况下，获取可用于绘图的数值列名（排除时间列）。

    Args:
        file_path: CSV文件路径
        sample_rows: 采样数据行数，用于判断列是否为数值列

    Returns:
        Optional[List[str]]: 数值列名列表（排除时间列），读取失败返回None
    """
    for encoding in CSVDataLoader.SUPPORTED_ENCODINGS:
        try:
            with open(file_path, 'r', newline='', encoding=encoding) as f:
                reader = csv.reader(f)
                try:
                    columns = next(reader)
                except StopIteration:
                    return None

                samples = []
                for i, row in enumerate(reader):
                    if i >= sample_rows:
                        break
                    samples.append(row)

            time_col = None
            for col in columns:
                col_lower = col.lower()
                if col_lower in ('time', 'times', 'time[s]'):
                    time_col = col
                    break

            # 采样值全部可解析为浮点数且至少存在一个非空值的列视为数值列
            numeric_cols = []
            for idx, col in enumerate(columns):
                if col == time_col:
                    continue
                is_numeric = True
                has_value = False
                for row in samples:
                    if idx >= len(row):
                        continue
                    value = row[idx].strip()
                    if not value:
                        continue
                    has_value = True
                    try:
                        float(value)
                    except ValueError:
                        is_numeric = False
                        break
                if has_value and is_numeric:
                    numeric_cols.append(col)
            return numeric_cols
        except UnicodeDecodeError:
            continue
        except Exception:
            return None
    return None


class CSVDataLoader:
    """
    CSV数据加载器

    负责加载CSV文件并解析数据，提供数据访问接口
    
    Attributes:
        data: 列名到数据列表的映射字典
        columns: 列名列表
        row_count: 数据行数
        total_rows: 文件总行数（分块加载时使用）
    """
    
    SUPPORTED_ENCODINGS = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1']
    
    _NUMERIC_PATTERN = re.compile(r'^-?\d+\.?\d*(?:[eE][+-]?\d+)?$')
    _DATETIME_PATTERN = re.compile(
        r'^\d{4}[-/]\d{2}[-/]\d{2} \d{1,2}:\d{2}:\d{2}(?:\.\d+)?$'
    )
    
    def __init__(self):
        """初始化数据加载器"""
        self.data: Dict[str, List] = {}
        self.columns: List[str] = []
        self.row_count: int = 0
        self.total_rows: int = 0
        self._file_path: str = ""
        self._encoding: str = ""
        self._chunk_size: Optional[int] = None
        self._loaded_chunks: int = 0
        self._has_more_data: bool = False
        self._skipped_rows: int = 0
    
    def load(self, file_path: str, encoding: str = None, 
             chunk_size: int = None) -> bool:
        """
        加载CSV文件
        
        Args:
            file_path: CSV文件路径
            encoding: 文件编码，None则自动检测
            chunk_size: 分块大小，None表示全部加载
            
        Returns:
            bool: 是否成功加载
        """
        self._reset_state()
        self._file_path = file_path
        self._chunk_size = chunk_size
        
        if encoding:
            self._encoding = encoding
            if chunk_size:
                return self._load_chunk(0, chunk_size)
            else:
                return self._load_with_encoding(file_path, encoding)
        
        for enc in self.SUPPORTED_ENCODINGS:
            try:
                if chunk_size:
                    if self._load_chunk(0, chunk_size):
                        self._encoding = enc
                        return True
                else:
                    if self._load_with_encoding(file_path, enc):
                        self._encoding = enc
                        return True
            except UnicodeDecodeError:
                continue
            except Exception:
                continue
        
        return False
    
    def _reset_state(self):
        """重置加载器状态"""
        self.data = {}
        self.columns = []
        self.row_count = 0
        self.total_rows = 0
        self._loaded_chunks = 0
        self._has_more_data = False
    
    def _load_with_encoding(self, file_path: str, encoding: str) -> bool:
        """
        使用指定编码加载文件（方案7优化：列式批量解析）

        原实现逐行逐格调用类型推断函数（每格一次函数调用+正则匹配），
        大文件时产生千万次 Python 层调用。现改为：
        1. 先把全部行读成字符串（csv.reader 的 C 级解析）
        2. 再按列批量转换：数值列用 map(float) 批量转换，
           类型不符时自动退回逐值推断，保证行为一致

        Args:
            file_path: 文件路径
            encoding: 文件编码

        Returns:
            bool: 是否成功加载
        """
        self._skipped_rows = 0
        try:
            with open(file_path, 'r', newline='', encoding=encoding) as f:
                reader = csv.reader(f)
                try:
                    self.columns = next(reader)
                except StopIteration:
                    return False

                for col in self.columns:
                    self.data[col] = []

                # 一次性读取全部数据行（字符串形式）
                all_rows = list(reader)

            if not all_rows:
                self.row_count = 0
                self.total_rows = 0
                self._normalize_time_column()
                return True

            n_cols = len(self.columns)
            # 过滤列数不符的行
            valid_rows = []
            skipped = 0
            for row in all_rows:
                if len(row) == n_cols:
                    valid_rows.append(row)
                else:
                    skipped += 1
            self._skipped_rows = skipped

            row_count = len(valid_rows)
            self.row_count = row_count
            self.total_rows = row_count

            # 按列批量转换（列式处理，比逐格推断快数倍）
            for col_idx, col_name in enumerate(self.columns):
                raw_col = [row[col_idx] for row in valid_rows]
                self.data[col_name] = self._convert_column(raw_col)

            self._normalize_time_column()
            return True
        except IOError as e:
            print(f"文件读写错误: {e}")
            return False

    def _convert_column(self, raw_col: List[str]) -> List:
        """
        批量转换一列字符串数据（方案7优化）

        通过 try/except 分层处理，避免逐值做正则预检：
        - 快路径1：全列直接 float() 转换（无空值/无空格时命中）
        - 快路径2：strip + 占位转换（数值列含空值时命中，空值还原为 None）
        - 慢路径：混有非数值时退回逐值推断（与原 _infer_value_type 行为一致）

        Args:
            raw_col: 该列的原始字符串列表

        Returns:
            List: 转换后的数据列表（数值/None/字符串）
        """
        # 快路径1：直接批量转换
        try:
            return list(map(float, raw_col))
        except (ValueError, TypeError):
            pass

        # 快路径2：处理空值/空格后批量转换
        cleaned = []
        empty_idx = []
        for i, v in enumerate(raw_col):
            s = v.strip() if v else ''
            if s:
                cleaned.append(s)
            else:
                cleaned.append('0')  # 占位，转换后还原为 None
                empty_idx.append(i)
        try:
            converted = list(map(float, cleaned))
            for i in empty_idx:
                converted[i] = None
            return converted
        except (ValueError, TypeError):
            pass

        # 慢路径：混有非数值内容，逐值推断（保持与原逻辑一致）
        return [self._infer_value_type(v) for v in raw_col]
    
    def _load_chunk(self, start: int, count: int) -> bool:
        """
        加载指定范围的数据块
        
        Args:
            start: 起始行号
            count: 加载行数
            
        Returns:
            bool: 是否成功加载
        """
        encoding = self._encoding or 'utf-8-sig'
        
        with open(self._file_path, 'r', newline='', encoding=encoding) as f:
            reader = csv.reader(f)
            
            try:
                if not self.columns:
                    self.columns = next(reader)
                    for col in self.columns:
                        self.data[col] = []
                else:
                    next(reader)
            except StopIteration:
                return False
            
            skip_count = start
            for _ in range(skip_count):
                try:
                    next(reader)
                except StopIteration:
                    break
            
            loaded = 0
            for row in reader:
                if loaded >= count:
                    self._has_more_data = True
                    break
                
                if len(row) != len(self.columns):
                    continue
                
                self._parse_row(row)
                self.row_count += 1
                loaded += 1
            else:
                self._has_more_data = False
            
            if start == 0:
                self._count_total_rows()
        
        self._normalize_time_column()
        return loaded > 0
    
    def _count_total_rows(self):
        """计算文件总行数"""
        encoding = self._encoding or 'utf-8-sig'
        try:
            with open(self._file_path, 'r', newline='', encoding=encoding) as f:
                self.total_rows = sum(1 for _ in f) - 1
        except Exception:
            self.total_rows = self.row_count
    
    def _parse_row(self, row: List[str]):
        """
        解析单行数据
        
        Args:
            row: CSV行数据
        """
        for i, value in enumerate(row):
            if i >= len(self.columns):
                break
            col_name = self.columns[i]
            parsed_value = self._infer_value_type(value)
            self.data[col_name].append(parsed_value)
    
    def _infer_value_type(self, value: str):
        """
        快速推断值的类型（使用正则预检优化）
        
        Args:
            value: 字符串值
            
        Returns:
            转换后的值
        """
        if not value or not value.strip():
            return None
        
        stripped = value.strip()
        
        if self._NUMERIC_PATTERN.match(stripped):
            try:
                if '.' in stripped or 'e' in stripped.lower():
                    return float(stripped)
                else:
                    return int(stripped)
            except ValueError:
                return stripped
        
        return stripped
    
    def _parse_datetime_to_epoch(self, value: str) -> Optional[float]:
        """
        将日期时间字符串转换为 epoch 秒数（浮点数）
        
        支持格式（兼容多种分隔符和小时位数）:
            - YYYY-MM-DD HH:MM:SS[.f]
            - YYYY/MM/DD H:MM:SS[.f]   （1 位或 2 位小时）
            - 以及上述分隔符的任意组合
        
        Args:
            value: 日期时间字符串
            
        Returns:
            Optional[float]: epoch 秒数，转换失败返回 None
        """
        if not value or not value.strip():
            return None
        s = value.strip()
        if not self._DATETIME_PATTERN.match(s):
            return None
        try:
            # 拆分日期 / 时间 / 小数秒
            if '.' in s:
                main_str, frac_str = s.rsplit('.', 1)
                # 小数部分转成 float 秒（只取第一位，多余位截断）
                frac_val = float('0.' + frac_str) if frac_str else 0.0
            else:
                main_str = s
                frac_val = 0.0
            
            date_str, time_str = main_str.split()
            # 拆分日期（兼容 - 和 /）
            date_parts = re.split(r'[-/]', date_str)
            y, mo, d = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
            # 拆分时间
            hh, mm, ss = (int(p) for p in time_str.split(':'))
            
            # 方案7优化：缓存本地时区偏移，用纯算术替代 timestamp() 的
            # 系统时区转换（Windows 上每次调用开销较大）
            dt = datetime(y, mo, d, hh, mm, ss)
            epoch = (dt - _EPOCH_BASE).total_seconds() + _get_local_epoch_offset()
            return epoch + frac_val
        except (ValueError, IndexError):
            return None
    
    def _normalize_time_column(self):
        """
        归一化时间列：若时间列为日期时间字符串格式，将其转换为数值型 epoch 秒数，
        以便图表、筛选等功能正常工作。
        """
        time_col = self.get_time_column()
        if not time_col or time_col not in self.data:
            return
        values = self.data[time_col]
        if not values:
            return
        # 如果已经全部是数值类型，无需转换
        sample = [v for v in values[:5] if v is not None]
        if sample and all(isinstance(v, (int, float)) for v in sample):
            return
        # 尝试日期时间转换
        converted = []
        all_ok = True
        for v in values:
            if v is None:
                converted.append(None)
                continue
            if isinstance(v, (int, float)):
                converted.append(float(v))
                continue
            s = str(v)
            epoch = self._parse_datetime_to_epoch(s)
            if epoch is None:
                all_ok = False
                break
            converted.append(epoch)
        if all_ok:
            self.data[time_col] = converted
    
    def load_more(self) -> bool:
        """
        加载下一块数据（仅分块模式有效）
        
        Returns:
            bool: 是否成功加载更多数据
        """
        if self._chunk_size is None or not self._has_more_data:
            return False
        
        start = self._loaded_chunks * self._chunk_size + self.row_count
        result = self._load_chunk(start, self._chunk_size)
        
        if result:
            self._loaded_chunks += 1
        
        return result
    
    def has_more_data(self) -> bool:
        """
        检查是否还有更多数据可加载
        
        Returns:
            bool: 是否还有更多数据
        """
        return self._has_more_data
    
    def get_load_progress(self) -> Tuple[int, int]:
        """
        获取加载进度
        
        Returns:
            Tuple[int, int]: (已加载行数, 总行数)
        """
        return (self.row_count, self.total_rows)
    
    def get_numeric_columns(self) -> List[str]:
        """
        获取数值类型的列名列表
        
        Returns:
            List[str]: 数值列名列表
        """
        numeric_cols = []
        for col in self.columns:
            if col == 'Time':
                continue
            values = [v for v in self.data[col] if v is not None]
            if values and all(isinstance(v, (int, float)) for v in values):
                numeric_cols.append(col)
        return numeric_cols
    
    def get_multi_select_columns(self) -> List[str]:
        """
        获取多列显示时可选择的列
        
        Returns:
            List[str]: 可用于多列对比的列名列表
        """
        numeric_cols = self.get_numeric_columns()
        result = []
        for target in MULTI_SELECT_COLUMNS:
            for col in numeric_cols:
                if target in col:
                    result.append(col)
                    break
        return result
    
    def get_time_column(self) -> Optional[str]:
        """
        获取时间列名
        
        Returns:
            Optional[str]: 时间列名，如果没有则返回None
        """
        for col in self.columns:
            col_lower = col.lower()
            if col_lower == 'time' or col_lower == 'times' or col_lower == 'time[s]':
                return col
        return None
    
    def get_column_data(self, column: str) -> List:
        """
        获取指定列的数据
        
        Args:
            column: 列名
            
        Returns:
            List: 该列的数据列表
        """
        return self.data.get(column, [])
    
    def get_statistics(self, column: str) -> Dict:
        """
        获取指定列的统计信息
        
        Args:
            column: 列名
            
        Returns:
            Dict: 统计信息字典
        """
        if column not in self.data:
            return {}
        
        values = [v for v in self.data[column] if v is not None and isinstance(v, (int, float))]
        
        if not values:
            return {
                'count': 0,
                'null_count': len(self.data[column]),
                'type': 'non-numeric'
            }
        
        return {
            'min': min(values),
            'max': max(values),
            'mean': sum(values) / len(values),
            'count': len(values),
            'null_count': len(self.data[column]) - len(values),
            'type': 'numeric'
        }
    
    def filter_by_time(self, start_time: float, end_time: float) -> 'CSVDataLoader':
        """
        按时间范围过滤数据
        
        Args:
            start_time: 起始时间
            end_time: 结束时间
            
        Returns:
            CSVDataLoader: 包含过滤后数据的新加载器
        """
        time_col = self.get_time_column()
        if not time_col:
            return self
        
        new_loader = CSVDataLoader()
        new_loader.columns = self.columns.copy()
        new_loader._encoding = self._encoding
        
        for col in self.columns:
            new_loader.data[col] = []
        
        for i, t in enumerate(self.data[time_col]):
            if t is not None and start_time <= t <= end_time:
                for col in self.columns:
                    new_loader.data[col].append(self.data[col][i])
                new_loader.row_count += 1
        
        new_loader.total_rows = new_loader.row_count
        return new_loader
    
    def clear(self):
        """清空加载的数据"""
        self.data.clear()
        self.columns.clear()
        self.row_count = 0
        self.total_rows = 0
        self._loaded_chunks = 0
        self._has_more_data = False
        self._skipped_rows = 0

    def get_skipped_rows(self) -> int:
        """
        获取加载时跳过的行数

        Returns:
            int: 跳过的行数
        """
        return self._skipped_rows

    def get_encoding(self) -> str:
        """
        获取当前使用的编码
        
        Returns:
            str: 文件编码
        """
        return self._encoding
    
    def is_chunked(self) -> bool:
        """
        检查是否为分块加载模式
        
        Returns:
            bool: 是否为分块模式
        """
        return self._chunk_size is not None
