# asc_to_csv/asc_parser.py
"""
ASC文件解析模块
负责解析ASC文件并提取CAN帧数据
"""

import re
from typing import Dict, Set, Tuple
from collections import defaultdict
import cantools


class ASCParser:
    """
    ASC文件解析器
    
    负责解析ASC文件，提取CAN帧并解码信号
    
    Attributes:
        sampled_data: 采样后的数据
        found_signals: 发现的信号集合
        original_count: 原始数据点数
    """
    
    # ASC行匹配正则表达式
    ASC_PATTERN = r'^(\d+\.\d+)\s+(\d+)\s+([0-9A-Fa-f]+x?)\s+(Rx|Tx)\s+d\s+(\d+)\s+(([0-9A-Fa-f]{2}\s*)+)$'
    
    def __init__(self, sample_interval: float = 0.1, debug: bool = False):
        """
        初始化ASC解析器
        
        Args:
            sample_interval: 采样间隔（秒）
            debug: 是否启用调试模式
        """
        self.sample_interval = sample_interval
        self.debug = debug
        self.sampled_data: Dict[float, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        self.found_signals: Set[str] = set()
        self.original_count: int = 0
    
    def parse(self, asc_file: str, message_map: Dict) -> bool:
        """
        解析ASC文件
        
        Args:
            asc_file: ASC文件路径
            message_map: 消息映射（来自DBCLoader）
            
        Returns:
            bool: 是否成功解析
        """
        try:
            with open(asc_file, 'r', encoding='utf-8') as f:
                for line in f:
                    self._parse_line(line, message_map)
            
            return True
            
        except Exception as e:
            print(f"解析ASC文件失败: {e}")
            return False
    
    def _parse_line(self, line: str, message_map: Dict) -> None:
        """
        解析单行ASC数据
        
        Args:
            line: ASC文件中的一行
            message_map: 消息映射
        """
        line = line.strip()
        
        # 跳过注释和空行
        if not line or line.startswith(';'):
            return
        
        # 匹配ASC格式
        match = re.match(self.ASC_PATTERN, line)
        if not match:
            return
        
        try:
            # 提取字段
            timestamp = float(match.group(1))
            frame_id_str = match.group(3)
            frame_id = int(frame_id_str.replace('x', ''), 16)
            data_hex = match.group(6).replace(' ', '')
            data = bytes.fromhex(data_hex)
            
            # 检查消息是否在DBC中定义
            if frame_id not in message_map:
                return
            
            self.original_count += 1
            
            # 计算采样时间
            sampled_time = round(timestamp / self.sample_interval) * self.sample_interval
            
            # 解码消息
            msg_info = message_map[frame_id]
            msg = msg_info['message']
            dbc_name = msg_info['dbc_name']
            
            decoded = msg.decode(data)
            
            # 存储解码结果
            for signal_name, value in decoded.items():
                full_signal_name = f"{dbc_name}::{msg.name}::{signal_name}"
                self.sampled_data[sampled_time][full_signal_name].append(value)
                self.found_signals.add(full_signal_name)
                
        except Exception as e:
            if self.debug:
                print(f"  解码错误: {e}")
    
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