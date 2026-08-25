# asc_to_csv/asc_parser.py
"""
ASC文件解析模块
负责解析ASC文件并提取CAN帧数据
性能优化版本
"""

import re
import gc
import os
from datetime import datetime
from typing import Dict, Set, Tuple, Optional, Callable
import cantools


class ASCParser:
    """
    ASC文件解析器（性能优化版）
    
    负责解析ASC文件，提取CAN帧并解码信号
    
    Attributes:
        sampled_data: 采样后的数据
        found_signals: 发现的信号集合
        original_count: 原始数据点数
    """
    
    ASC_PATTERN = re.compile(
        r'^(\d+\.\d+)\s+(\d+)\s+([0-9A-Fa-f]+x?)\s+(Rx|Tx)\s+d\s+(\d+)\s+(([0-9A-Fa-f]{2}\s*)+)$'
    )
    DATE_PATTERN = re.compile(r'^date\s+(.+)$')
    DATE_FORMAT = 'date %a %b %d %I:%M:%S %p %Y'
    # 中文格式 date 行，如: "date 周六 8月 15 09:33:39 上午 2026"
    # 容错: 星期/周 前缀、日后的"日"、秒后毫秒、年后的"年"或时区文本(如"中国标准时间")
    CHINESE_DATE_PATTERN = re.compile(
        r'^date\s+(?:周|星期)[一二三四五六日天]\s*'
        r'(\d{1,2})月\s*(\d{1,2})日?\s+'
        r'(\d{1,2}):(\d{2}):(\d{2})(?:\.\d+)?\s+'
        r'(上午|下午|中午|凌晨|清晨|傍晚|晚上)\s+(\d{4})年?(?:\s.*)?$'
    )
    MAX_MEMORY_SIGNALS = 10000
    MAX_MEMORY_TIMESTAMPS = 100000
    PROGRESS_UPDATE_INTERVAL = 10000
    MEMORY_CHECK_INTERVAL = 50000
    
    def __init__(self, sample_interval: float = 0.1, debug: bool = False,
                 debug_callback: Optional[Callable[[str], None]] = None):
        """
        初始化ASC解析器

        Args:
            sample_interval: 采样间隔（秒）
            debug: 是否启用调试模式
            debug_callback: 调试信息回调函数
                - 提供时调试/警告信息通过回调输出（GUI日志可见）
                - 不提供时退回到 print()（仅终端可见）
        """
        self.sample_interval = sample_interval
        self.debug = debug
        self._debug_callback = debug_callback
        self.sampled_data: Dict[float, Dict[str, list]] = {}
        self.found_signals: Set[str] = set()
        self.original_count: int = 0
        self.start_time: float = 0.0
        self._memory_warning_shown: bool = False
        self._line_count: int = 0
        self._file_size: int = 0
        self._last_progress: float = 0.0

    def _debug_log(self, message: str) -> None:
        """输出调试/警告信息：有回调走回调，否则打印到控制台"""
        if self._debug_callback:
            self._debug_callback(message)
        else:
            print(message)
    
    def parse(self, asc_file: str, message_map: Dict, 
              progress_callback: Optional[Callable[[float, int], None]] = None) -> bool:
        """
        解析ASC文件
        
        Args:
            asc_file: ASC文件路径
            message_map: 消息映射（来自DBCLoader）
            progress_callback: 进度回调函数，参数为(进度百分比, 已处理行数)
            
        Returns:
            bool: 是否成功解析
        """
        try:
            self._file_size = os.path.getsize(asc_file)
            self._line_count = 0
            self._last_progress = 0.0
            
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            file_handle = None
            encoding_errors = []

            for encoding in encodings:
                try:
                    file_handle = open(asc_file, 'r', encoding=encoding, buffering=8192*4)
                    file_handle.read(1024)
                    file_handle.seek(0)
                    break
                except (UnicodeDecodeError, UnicodeError) as e:
                    if file_handle:
                        file_handle.close()
                    encoding_errors.append(f"{encoding}: {str(e)}")
                    continue

            if file_handle is None:
                error_detail = "; ".join(encoding_errors)
                print(f"错误：无法识别文件编码 - {asc_file}")
                print(f"尝试的编码: {encodings}")
                print(f"编码错误详情: {error_detail}")
                return False
            
            with file_handle as f:
                # 读取第一行，解析起始时间
                first_line = f.readline()
                self._line_count += 1
                self._parse_date_line(first_line)
                
                bytes_read = len(first_line.encode('utf-8', errors='ignore'))
                for line in f:
                    self._line_count += 1
                    bytes_read += len(line.encode('utf-8', errors='ignore'))
                    
                    self._parse_line(line, message_map)
                    
                    if self._line_count % self.PROGRESS_UPDATE_INTERVAL == 0:
                        if progress_callback and self._file_size > 0:
                            progress = min(99.0, (bytes_read / self._file_size) * 100)
                            if progress - self._last_progress >= 1.0:
                                progress_callback(progress, self._line_count)
                                self._last_progress = progress
                    
                    if self._line_count % self.MEMORY_CHECK_INTERVAL == 0:
                        self._check_memory_usage()
            
            if progress_callback:
                progress_callback(100.0, self._line_count)
            
            return True
            
        except FileNotFoundError:
            print(f"错误：文件不存在 - {asc_file}")
            return False
        except PermissionError:
            print(f"错误：无权限访问文件 - {asc_file}")
            return False
        except MemoryError:
            print("错误：内存不足，请尝试增加采样间隔或处理较小的文件")
            self.clear()
            return False
        except Exception as e:
            print(f"解析ASC文件失败: {type(e).__name__}: {e}")
            return False
    
    def _check_memory_usage(self):
        """检查内存使用情况并发出警告"""
        if self._memory_warning_shown:
            return
        
        signal_count = len(self.found_signals)
        timestamp_count = len(self.sampled_data)
        
        if signal_count > self.MAX_MEMORY_SIGNALS or timestamp_count > self.MAX_MEMORY_TIMESTAMPS:
            print(f"警告：数据量较大（{timestamp_count}个时间点，{signal_count}个信号），可能占用较多内存")
            self._memory_warning_shown = True
    
    def _parse_date_line(self, line: str) -> None:
        """
        解析ASC文件第一行的 date 时间

        支持的格式：
            - 英文: "date Thu Aug 13 01:52:11 PM 2026"
            - 中文: "date 周六 8月 15 09:33:39 上午 2026"
            - 容错: UTF-8 BOM前缀、秒后毫秒、年后时区文本(如"中国标准时间")

        Args:
            line: ASC文件的第一行文本
        """
        # 去除UTF-8 BOM（部分工具导出的文件首行带BOM，会导致 ^date 匹配失败）
        line = line.lstrip('\ufeff').strip()
        match = self.DATE_PATTERN.match(line)
        if not match:
            if self.debug:
                self._debug_log(f"  ASC文件未找到 date 行，将使用时间戳从0开始")
            return

        dt = None
        try:
            dt = datetime.strptime(line, self.DATE_FORMAT)
        except ValueError:
            # 英文格式解析失败，尝试中文格式（如CANoe中文环境导出的ASC文件）
            dt = self._parse_chinese_date(line)

        if dt is not None:
            self.start_time = dt.timestamp()
            if self.debug:
                self._debug_log(f"  解析ASC起始时间: {dt} (epoch: {self.start_time})")
        else:
            # 始终输出警告（含repr以暴露不可见字符），便于定位格式差异
            self._debug_log(f"警告: date行解析失败: {line!r}，该文件时间列将从0开始")

    def _parse_chinese_date(self, line: str) -> Optional[datetime]:
        """
        解析中文格式的 date 行

        格式示例: "date 周六 8月 15 09:33:39 上午 2026"
        （星期几仅作占位，不参与构造时间）

        Args:
            line: date 行文本

        Returns:
            Optional[datetime]: 解析成功返回 datetime，失败返回 None
        """
        match = self.CHINESE_DATE_PATTERN.match(line)
        if not match:
            return None

        month = int(match.group(1))
        day = int(match.group(2))
        hour = int(match.group(3))
        minute = int(match.group(4))
        second = int(match.group(5))
        am_pm = match.group(6)
        year = int(match.group(7))

        # 12小时制转24小时制
        if am_pm in ('下午', '中午', '傍晚', '晚上') and hour < 12:
            hour += 12
        elif am_pm in ('上午', '凌晨', '清晨') and hour == 12:
            hour = 0

        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            return None
    
    def _parse_line(self, line: str, message_map: Dict) -> None:
        """
        解析单行ASC数据
        
        Args:
            line: ASC文件中的一行
            message_map: 消息映射
        """
        line = line.strip()
        
        if not line or line[0] == ';':
            return
        
        match = self.ASC_PATTERN.match(line)
        if not match:
            return
        
        try:
            timestamp = float(match.group(1))
            frame_id_str = match.group(3)
            frame_id = int(frame_id_str.replace('x', ''), 16)
            data_hex = match.group(6).replace(' ', '')
            data = bytes.fromhex(data_hex)
            
            if frame_id not in message_map:
                return
            
            self.original_count += 1
            sampled_time = round(timestamp / self.sample_interval) * self.sample_interval
            
            msg_info = message_map[frame_id]
            msg = msg_info['message']
            dbc_name = msg_info['dbc_name']
            
            decoded = msg.decode(data, decode_choices=False)
            
            if sampled_time not in self.sampled_data:
                self.sampled_data[sampled_time] = {}
            
            time_data = self.sampled_data[sampled_time]
            
            for signal_name, value in decoded.items():
                full_signal_name = f"{dbc_name}::{msg.name}::{signal_name}"
                
                if full_signal_name not in time_data:
                    time_data[full_signal_name] = []
                
                if isinstance(value, (int, float)):
                    time_data[full_signal_name].append(value)
                else:
                    signal_obj = msg.get_signal_by_name(signal_name)
                    if signal_obj and signal_obj.choices:
                        for num_val, str_val in signal_obj.choices.items():
                            if str_val == value:
                                time_data[full_signal_name].append(num_val)
                                break
                        else:
                            time_data[full_signal_name].append(value)
                    else:
                        time_data[full_signal_name].append(value)
                
                self.found_signals.add(full_signal_name)
                
        except ValueError as e:
            if self.debug:
                self._debug_log(f"  数据格式错误: {e}")
        except KeyError as e:
            if self.debug:
                self._debug_log(f"  消息映射错误: {e}")
        except Exception as e:
            if self.debug:
                self._debug_log(f"  解码错误: {type(e).__name__}: {e}")
    
    def get_statistics(self) -> Tuple[int, int, int]:
        """
        获取解析统计信息
        
        Returns:
            Tuple[int, int, int]: (原始数据点数, 采样后时间点数, 信号数)
        """
        return (
            self.original_count,
            len(self.sampled_data),
            len(self.found_signals)
        )
    
    def clear(self):
        """清理内存中的数据"""
        self.sampled_data.clear()
        self.found_signals.clear()
        self.original_count = 0
        self._memory_warning_shown = False
        self._line_count = 0
        gc.collect()

    def parse_multiple(self, asc_files: list, message_map: Dict,
                      progress_callback: Optional[Callable[[float, int], None]] = None) -> bool:
        """
        解析多个ASC文件（用于多文件拼接模式）

        Args:
            asc_files: ASC文件路径列表（已排序）
            message_map: 消息映射（来自DBCLoader）
            progress_callback: 进度回调函数，参数为(进度百分比, 已处理行数)

        Returns:
            bool: 是否成功解析所有文件
        """
        if not asc_files:
            print("错误：ASC文件列表为空")
            return False

        if len(asc_files) == 1:
            return self.parse(asc_files[0], message_map, progress_callback)

        total_files = len(asc_files)
        overall_success = True

        for file_idx, asc_file in enumerate(asc_files):
            file_name = os.path.basename(asc_file)

            if progress_callback:
                progress_callback(file_idx / total_files * 100, 0)

            def partial_progress_callback(progress: float, line_count: int):
                overall_file_progress = (file_idx + progress / 100) / total_files * 100
                if progress_callback:
                    progress_callback(overall_file_progress, line_count)

            if not self.parse(asc_file, message_map, partial_progress_callback):
                print(f"警告：解析文件失败: {asc_file}")
                overall_success = False
                continue

        if progress_callback:
            progress_callback(100.0, self._line_count)

        return overall_success

    def __del__(self):
        """析构函数，确保资源释放"""
        if hasattr(self, 'sampled_data'):
            self.sampled_data.clear()
        if hasattr(self, 'found_signals'):
            self.found_signals.clear()
