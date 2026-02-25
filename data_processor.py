# asc_to_csv/data_processor.py
"""
数据处理模块
负责数据聚合、分组等处理
"""

from typing import Dict, List, Set
from collections import defaultdict

from utils import extract_batp_group, sort_group_key


class DataProcessor:
    """
    数据处理器
    
    负责聚合数据和按规则分组
    
    Attributes:
        aggregated_data: 聚合后的数据
        classified_signals: 分类后的信号
        sorted_groups: 排序后的分组
    """
    
    def __init__(self):
        """初始化数据处理器"""
        self.aggregated_data: Dict[float, Dict[str, any]] = {}
        self.classified_signals: Dict[str, List[str]] = defaultdict(list)
        self.sorted_groups: List[str] = []
    
    def aggregate(self, sampled_data: Dict) -> None:
        """
        聚合采样数据
        
        取每个时间间隔内的最后一个值
        
        Args:
            sampled_data: 采样数据（来自ASCParser）
        """
        for sampled_time, signals in sampled_data.items():
            self.aggregated_data[sampled_time] = {}
            for signal_name, values in signals.items():
                self.aggregated_data[sampled_time][signal_name] = values[-1]
    
    def classify_signals(self, found_signals: Set[str]) -> None:
        """
        按BatP+数字模式分组信号
        
        Args:
            found_signals: 发现的信号集合
        """
        for signal_name in found_signals:
            group_name = extract_batp_group(signal_name)
            self.classified_signals[group_name].append(signal_name)
        
        # 排序分组
        self.sorted_groups = sorted(self.classified_signals.keys(), key=sort_group_key)
    
    def get_sorted_timestamps(self) -> List[float]:
        """
        获取排序后的时间戳列表
        
        Returns:
            List[float]: 排序后的时间戳
        """
        return sorted(self.aggregated_data.keys())
    
    def get_group_statistics(self) -> Dict[str, int]:
        """
        获取各分组的统计信息
        
        Returns:
            Dict[str, int]: 分组名称到信号数量的映射
        """
        return {
            group_name: len(signals) 
            for group_name, signals in self.classified_signals.items()
        }