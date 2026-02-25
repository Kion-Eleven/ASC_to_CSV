# asc_to_csv/csv_writer.py
"""
CSV文件输出模块
负责将处理后的数据写入CSV文件
"""

import os
import csv
from typing import Dict, List, Set, Any

from utils import safe_value


class CSVWriter:
    """
    CSV文件写入器
    
    负责将数据写入CSV文件
    
    Attributes:
        output_dir: 输出目录
        encoding: 文件编码
        group_size: 分组大小
    """
    
    def __init__(self, output_dir: str, encoding: str = "utf-8-sig", group_size: int = 5):
        """
        初始化CSV写入器
        
        Args:
            output_dir: 输出目录
            encoding: 文件编码
            group_size: 分组大小
        """
        self.output_dir = output_dir
        self.encoding = encoding
        self.group_size = group_size
    
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
        
        # 写入分组文件
        for group_name in sorted_groups:
            signals = classified_signals[group_name]
            filename = self._write_group_file(
                group_name, signals, sorted_timestamps, 
                aggregated_data, signal_info
            )
            created_files.append(filename)
        
        # 写入汇总文件
        summary_file = self._write_summary_file(
            sorted_groups, classified_signals, sorted_timestamps, 
            statistics, signal_info
        )
        
        # 写入总览文件
        all_signals_file = self._write_all_signals_file(
            classified_signals, sorted_timestamps, 
            aggregated_data, signal_info
        )
        
        return created_files + [summary_file, all_signals_file]
    
    def _write_group_file(
        self,
        group_name: str,
        signals: List[str],
        sorted_timestamps: List[float],
        aggregated_data: Dict,
        signal_info: Dict
    ) -> str:
        """
        写入单个分组文件
        
        Args:
            group_name: 分组名称
            signals: 信号列表
            sorted_timestamps: 排序后的时间戳
            aggregated_data: 聚合数据
            signal_info: 信号信息
            
        Returns:
            str: 文件路径
        """
        csv_filename = os.path.join(self.output_dir, f"{group_name}.csv")
        sorted_signals = sorted(signals)
        
        # 生成表头
        header = self._generate_header(sorted_signals, signal_info)
        
        with open(csv_filename, 'w', newline='', encoding=self.encoding) as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            
            group_count = 0
            for timestamp in sorted_timestamps:
                data = aggregated_data[timestamp]
                row = self._build_row(timestamp, sorted_signals, data)
                writer.writerow(row)
                group_count += 1
                
                if group_count >= self.group_size:
                    writer.writerow([])
                    group_count = 0
        
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
            
            # 写入汇总信息
            writer.writerow(["数据转换汇总报告"])
            writer.writerow([])
            writer.writerow(["分组规则", "按BatP+数字模式分组"])
            writer.writerow(["示例", "BatP3_BMS_xxx -> BatP3组"])
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
        aggregated_data: Dict,
        signal_info: Dict
    ) -> str:
        """
        写入所有信号总览文件
        
        Args:
            classified_signals: 分类信号
            sorted_timestamps: 时间戳
            aggregated_data: 聚合数据
            signal_info: 信号信息
            
        Returns:
            str: 文件路径
        """
        all_signals_filename = os.path.join(self.output_dir, "All_Signals.csv")
        
        # 合并所有信号
        all_signals = []
        for signals in classified_signals.values():
            all_signals.extend(signals)
        all_sorted_signals = sorted(all_signals)
        
        header = self._generate_header(all_sorted_signals, signal_info)
        
        with open(all_signals_filename, 'w', newline='', encoding=self.encoding) as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            
            for timestamp in sorted_timestamps:
                data = aggregated_data[timestamp]
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
            data: 数据字典
            
        Returns:
            List[Any]: 数据行
        """
        row = [round(timestamp, 1)]
        for sig_name in signals:
            if sig_name in data:
                row.append(safe_value(data[sig_name]))
            else:
                row.append("")
        return row