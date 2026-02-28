# asc_to_csv/asc_parser.py
"""
ASC文件解析模块
负责解析ASC文件并提取CAN帧数据
性能优化版本
"""

import re
import gc
import os
from typing import Dict, Set, Tuple, Optional, Callable
from collections import defaultdict
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
    MAX_MEMORY_SIGNALS = 10000
    MAX_MEMORY_TIMESTAMPS = 100000
    PROGRESS_UPDATE_INTERVAL = 10000
    MEMORY_CHECK_INTERVAL = 50000
    
    def __init__(self, sample_interval: float = 0.1, debug: bool = False):
        """
        初始化ASC解析器
        
        Args:
            sample_interval: 采样间隔（秒）
            debug: 是否启用调试模式
        """
        self.sample_interval = sample_interval
        self.debug = debug
        self.sampled_data: Dict[float, Dict[str, list]] = {}
        self.found_signals: Set[str] = set()
        self.original_count: int = 0
        self._memory_warning_shown = False
        self._line_count: int = 0
        self._file_size: int = 0
        self._last_progress: float = 0.0
    
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
            
            for encoding in encodings:
                try:
                    file_handle = open(asc_file, 'r', encoding=encoding, buffering=8192*4)
                    file_handle.read(1024)
                    file_handle.seek(0)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    if file_handle:
                        file_handle.close()
                    continue
            
            if file_handle is None:
                print(f"错误：无法识别文件编码 - {asc_file}")
                return False
            
            with file_handle as f:
                bytes_read = 0
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
                print(f"  数据格式错误: {e}")
        except KeyError as e:
            if self.debug:
                print(f"  消息映射错误: {e}")
        except Exception as e:
            if self.debug:
                print(f"  解码错误: {type(e).__name__}: {e}")
    
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
    
    def __del__(self):
        """析构函数，确保资源释放"""
        if hasattr(self, 'sampled_data'):
            self.sampled_data.clear()
        if hasattr(self, 'found_signals'):
            self.found_signals.clear()
