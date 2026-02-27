# asc_to_csv/csv_writer.py
"""
CSV文件输出模块
负责将处理后的数据写入CSV文件
支持空值填充功能
"""

import os
import csv
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict

from utils import safe_value


class CSVWriter:
    """
    CSV文件写入器
    
    负责将数据写入CSV文件，支持空值填充
    
    Attributes:
        output_dir: 输出目录
        encoding: 文件编码
        group_size: 分组大小
        fill_interval: 填充时间间隔（秒）
    """
    
    def __init__(
        self, 
        output_dir: str, 
        encoding: str = "utf-8-sig", 
        group_size: int = 5,
        fill_interval: float = 0.5
    ):
        """
        初始化CSV写入器
        
        Args:
            output_dir: 输出目录
            encoding: 文件编码
            group_size: 分组大小
            fill_interval: 填充时间间隔（秒），默认0.5秒
        """
        self.output_dir = output_dir
        self.encoding = encoding
        self.group_size = group_size
        self.fill_interval = fill_interval
    
    def _get_time_bucket(self, timestamp: float) -> int:
        """
        计算时间戳所属的时间区间编号
        
        每0.5秒为一个区间：
        - [0, 0.5) -> 0  (即 0.0, 0.1, 0.2, 0.3, 0.4 秒)
        - [0.5, 1.0) -> 1 (即 0.5, 0.6, 0.7, 0.8, 0.9 秒)
        - [1.0, 1.5) -> 2
        ...
        
        Args:
            timestamp: 时间戳
            
        Returns:
            int: 时间区间编号
        """
        return int(timestamp // self.fill_interval)
    
    def _fill_missing_values(
        self,
        sorted_timestamps: List[float],
        aggregated_data: Dict[float, Dict[str, Any]],
        signals: List[str]
    ) -> Dict[float, Dict[str, Any]]:
        """
        填充缺失值
        
        使用同一时间区间内的有效值填充空值：
        1. 首先收集每个时间区间内所有时间戳的所有有效值
        2. 然后使用这些有效值填充该区间内所有时间戳的空值
        
        Args:
            sorted_timestamps: 排序后的时间戳列表
            aggregated_data: 原始聚合数据
            signals: 信号列表
            
        Returns:
            Dict[float, Dict[str, Any]]: 填充后的数据
        """
        bucket_values: Dict[int, Dict[str, Any]] = defaultdict(dict)
        bucket_timestamps: Dict[int, List[float]] = defaultdict(list)
        
        for timestamp in sorted_timestamps:
            bucket = self._get_time_bucket(timestamp)
            bucket_timestamps[bucket].append(timestamp)
            original_data = aggregated_data.get(timestamp, {})
            
            for sig_name in signals:
                if sig_name in original_data and original_data[sig_name] is not None:
                    bucket_values[bucket][sig_name] = original_data[sig_name]
        
        filled_data = {}
        for timestamp in sorted_timestamps:
            bucket = self._get_time_bucket(timestamp)
            original_data = aggregated_data.get(timestamp, {})
            filled_row = {}
            
            for sig_name in signals:
                if sig_name in original_data and original_data[sig_name] is not None:
                    filled_row[sig_name] = original_data[sig_name]
                elif sig_name in bucket_values[bucket]:
                    filled_row[sig_name] = bucket_values[bucket][sig_name]
                else:
                    filled_row[sig_name] = None
            
            filled_data[timestamp] = filled_row
        
        return filled_data
    
    def write_all(
        self,
        sorted_groups: List[str],
        classified_signals: Dict[str, List[str]],
        sorted_timestamps: List[float],
        aggregated_data: Dict[float, Dict[str, Any]],
        signal_info: Dict[str, Dict[str, str]],
        statistics: Dict[str, int]
    ) -> List[str]:
        """
        写入所有CSV文件
        
        Args:
            sorted_groups: 排序后的分组列表
            classified_signals: 分类后的信号
            sorted_timestamps: 排序后的时间戳
            aggregated_data: 聚合后的数据
            signal_info: 信号信息
            statistics: 统计信息
            
        Returns:
            List[str]: 生成的文件列表
        """
        created_files = []
        
        all_signals = []
        for signals in classified_signals.values():
            all_signals.extend(signals)
        all_signals = sorted(set(all_signals))
        
        filled_data = self._fill_missing_values(
            sorted_timestamps, aggregated_data, all_signals
        )
        
        print(f"  已完成空值填充（填充间隔: {self.fill_interval}秒）")
        
        for group_name in sorted_groups:
            signals = classified_signals[group_name]
            filename = self._write_group_file(
                group_name, signals, sorted_timestamps, 
                filled_data, signal_info
            )
            created_files.append(filename)
        
        summary_file = self._write_summary_file(
            sorted_groups, classified_signals, sorted_timestamps, 
            statistics, signal_info
        )
        
        all_signals_file = self._write_all_signals_file(
            classified_signals, sorted_timestamps, 
            filled_data, signal_info
        )
        
        return created_files + [summary_file, all_signals_file]
    
    def _write_group_file(
        self,
        group_name: str,
        signals: List[str],
        sorted_timestamps: List[float],
        filled_data: Dict,
        signal_info: Dict
    ) -> str:
        """
        写入单个分组文件
        
        Args:
            group_name: 分组名称
            signals: 信号列表
            sorted_timestamps: 排序后的时间戳
            filled_data: 填充后的数据
            signal_info: 信号信息
            
        Returns:
            str: 文件路径
        """
        csv_filename = os.path.join(self.output_dir, f"{group_name}.csv")
        sorted_signals = sorted(signals)
        
        header = self._generate_header(sorted_signals, signal_info)
        
        with open(csv_filename, 'w', newline='', encoding=self.encoding) as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            
            for timestamp in sorted_timestamps:
                data = filled_data.get(timestamp, {})
                row = self._build_row(timestamp, sorted_signals, data)
                writer.writerow(row)
        
        print(f"  创建文件: {csv_filename}")
        return csv_filename
    
    def _write_summary_file(
        self,
        sorted_groups: List[str],
        classified_signals: Dict,
        sorted_timestamps: List[float],
        statistics: Dict,
        signal_info: Dict
    ) -> str:
        """
        写入汇总文件
        
        Args:
            sorted_groups: 排序后的分组
            classified_signals: 分类信号
            sorted_timestamps: 时间戳
            statistics: 统计信息
            signal_info: 信号信息
            
        Returns:
            str: 文件路径
        """
        summary_filename = os.path.join(self.output_dir, "Summary.csv")
        
        with open(summary_filename, 'w', newline='', encoding=self.encoding) as csvfile:
            writer = csv.writer(csvfile)
            
            writer.writerow(["数据转换汇总报告"])
            writer.writerow([])
            writer.writerow(["分组规则", "按BatP+数字模式分组"])
            writer.writerow(["示例", "BatP3_BMS_xxx -> BatP3组"])
            writer.writerow(["空值填充间隔", f"{self.fill_interval}秒"])
            writer.writerow([])
            writer.writerow(["数据统计"])
            writer.writerow(["采样后时间点数", len(sorted_timestamps)])
            writer.writerow(["信号总数", sum(len(s) for s in classified_signals.values())])
            writer.writerow(["分组数量", len(sorted_groups)])
            writer.writerow([])
            writer.writerow(["各分组详情"])
            writer.writerow(["分组名称", "信号数量", "文件名"])
            
            for group_name in sorted_groups:
                writer.writerow([
                    group_name,
                    len(classified_signals[group_name]),
                    f"{group_name}.csv"
                ])
        
        print(f"  创建汇总文件: {summary_filename}")
        return summary_filename
    
    def _write_all_signals_file(
        self,
        classified_signals: Dict,
        sorted_timestamps: List[float],
        filled_data: Dict,
        signal_info: Dict
    ) -> str:
        """
        写入所有信号总览文件
        
        Args:
            classified_signals: 分类信号
            sorted_timestamps: 时间戳
            filled_data: 填充后的数据
            signal_info: 信号信息
            
        Returns:
            str: 文件路径
        """
        all_signals_filename = os.path.join(self.output_dir, "All_Signals.csv")
        
        all_signals = []
        for signals in classified_signals.values():
            all_signals.extend(signals)
        all_sorted_signals = sorted(all_signals)
        
        header = self._generate_header(all_sorted_signals, signal_info)
        
        with open(all_signals_filename, 'w', newline='', encoding=self.encoding) as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            
            for timestamp in sorted_timestamps:
                data = filled_data.get(timestamp, {})
                row = self._build_row(timestamp, all_sorted_signals, data)
                writer.writerow(row)
        
        print(f"  创建总览文件: {all_signals_filename}")
        return all_signals_filename
    
    def _generate_header(self, signals: List[str], signal_info: Dict) -> List[str]:
        """
        生成CSV表头
        
        Args:
            signals: 信号列表
            signal_info: 信号信息
            
        Returns:
            List[str]: 表头列表
        """
        header = ["Time[s]"]
        for sig_name in signals:
            unit = signal_info.get(sig_name, {}).get('unit', '')
            short_name = sig_name.split('::')[-1]
            if unit:
                header.append(f"{short_name}[{unit}]")
            else:
                header.append(short_name)
        return header
    
    def _build_row(
        self,
        timestamp: float,
        signals: List[str],
        data: Dict
    ) -> List[Any]:
        """
        构建数据行
        
        Args:
            timestamp: 时间戳
            signals: 信号列表
            data: 数据字典（已填充）
            
        Returns:
            List[Any]: 数据行
        """
        row = [round(timestamp, 1)]
        for sig_name in signals:
            if sig_name in data and data[sig_name] is not None:
                row.append(safe_value(data[sig_name]))
            else:
                row.append("")
        return row
