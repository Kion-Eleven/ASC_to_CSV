# asc_to_csv/enhanced_csv_writer.py
"""
增强型CSV写入器模块

本模块实现了将分组后的信号数据写入CSV文件的功能。支持为每个唯一组名称
创建独立的CSV文件，并提供空值填充、文件存在性检查等功能。

主要功能：
    - 为每个分组创建独立的CSV文件
    - 空值填充：使用时间区间内的有效值填充缺失数据
    - 文件存在性检查：避免重复创建已存在的文件
    - 汇总报告生成：创建Summary.csv汇总文件

使用示例：
    >>> from enhanced_csv_writer import EnhancedCSVWriter
    >>> writer = EnhancedCSVWriter(output_dir='./output', overwrite=True)
    >>> result = writer.write_all_groups(
    ...     classified_signals={'BATP1': ['sig1', 'sig2'], 'Others': ['sig3']},
    ...     sorted_timestamps=[0.0, 0.1, 0.2],
    ...     aggregated_data={0.0: {'sig1': 1.0, 'sig2': 2.0, 'sig3': 3.0}},
    ...     signal_info={'sig1': {'unit': 'V'}}
    ... )
"""

import os
import re
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict

from utils import safe_value


class EnhancedCSVWriter:
    """
    增强型CSV写入器
    
    为每个唯一组名称创建独立的CSV文件，支持空值填充和文件覆盖控制。
    
    Attributes:
        output_dir (str): 输出目录路径
        encoding (str): CSV文件编码，默认为utf-8-sig
        fill_interval (float): 空值填充时间间隔（秒），默认为0.5秒
        overwrite (bool): 是否覆盖已存在的文件
        created_files (Set[str]): 已创建的文件路径集合
        existing_files (Set[str]): 已存在的文件路径集合（跳过未覆盖）
    
    文件命名规则：
        - 组名称会被清理，移除文件系统不支持的特殊字符
        - 文件名格式：{组名称}.csv
        - 示例：BATP1.csv, BATPS.csv, Others.csv
    
    空值填充算法：
        1. 将时间轴划分为固定间隔的时间区间（默认0.5秒）
        2. 对于每个时间区间，收集该区间内所有有效信号值
        3. 使用同一区间内的有效值填充缺失值
        4. 目的：减少数据缺失，提高数据连续性
    """
    
    def __init__(
        self,
        output_dir: str,
        encoding: str = "utf-8-sig",
        fill_interval: float = 0.5,
        overwrite: bool = False,
        start_time: float = 0.0
    ):
        """
        初始化CSV写入器
        
        Args:
            output_dir: 输出目录路径
                - 必须是有效的目录路径
                - 如果目录不存在，会在写入时自动创建
            encoding: CSV文件编码
                - utf-8-sig（默认）：带BOM的UTF-8，Excel兼容性好
                - utf-8：标准UTF-8编码
                - gbk：中文Windows兼容
            fill_interval: 空值填充时间间隔（秒）
                - 默认0.5秒
                - 较小的值填充更精确，但可能导致更多空值
                - 较大的值填充更宽松，但可能引入不准确的值
            overwrite: 是否覆盖已存在的文件
                - False（默认）：跳过已存在的文件
                - True：覆盖已存在的文件
            start_time: ASC文件起始时间（epoch秒）
                - 默认0.0，表示时间戳从0开始
                - 设置为ASC文件第一行date解析出的时间，则时间戳从该时间开始
        
        Examples:
            >>> writer = EnhancedCSVWriter('./output')
            >>> writer = EnhancedCSVWriter('./output', encoding='gbk', overwrite=True)
        """
        self.output_dir = output_dir
        self.encoding = encoding
        self.fill_interval = fill_interval
        self.overwrite = overwrite
        self.start_time = start_time
        
        self.created_files: Set[str] = set()
        self.existing_files: Set[str] = set()
    
    def _get_time_bucket(self, timestamp: float) -> int:
        """
        计算时间戳所属的时间区间编号
        
        时间区间划分示例（fill_interval=0.5）：
            - [0, 0.5) -> 区间0
            - [0.5, 1.0) -> 区间1
            - [1.0, 1.5) -> 区间2
        
        Args:
            timestamp: 时间戳（秒）
        
        Returns:
            int: 时间区间编号
        
        Examples:
            >>> writer = EnhancedCSVWriter('./output', fill_interval=0.5)
            >>> writer._get_time_bucket(0.3)
            0
            >>> writer._get_time_bucket(0.7)
            1
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
        
        填充策略：
            1. 遍历所有时间戳，将每个时间戳分配到对应的时间区间（默认 0.5s 宽度）
            2. 对于每个时间区间，收集该区间内所有信号的有效值（取最后一个）
            3. **跨区间前向填充（ffill）**：按时间顺序遍历区间，
               若某区间内某信号没有有效值，则使用前一区间该信号的最近值。
               这样保证信号不会因为恰好错过某个 0.5s 窗口而出现整桶空白。
            4. 对于每个时间戳：若原值缺失，使用所在区间的最近有效值填充；
               若区间内完全没出现过且前序区间也没出现过，保持为 None
        
        Args:
            sorted_timestamps: 排序后的时间戳列表
            aggregated_data: 原始聚合数据
                - 键：时间戳
                - 值：{信号名称: 信号值} 字典
            signals: 需要处理的信号名称列表
        
        Returns:
            Dict[float, Dict[str, Any]]: 填充后的数据
        
        Note:
            - 同时间区间内取最后一个有效值
            - 跨时间区间做前向延续（last-observation-carried-forward）
            - 第一个出现有效值之前的所有位置保持为 None（无法向后填充）
        """
        bucket_values: Dict[int, Dict[str, Any]] = defaultdict(dict)
        bucket_timestamps: Dict[int, List[float]] = defaultdict(list)
        
        # 步骤 1：收集每个时间区间内的有效值（最后一个值覆盖）
        for timestamp in sorted_timestamps:
            bucket = self._get_time_bucket(timestamp)
            bucket_timestamps[bucket].append(timestamp)
            original_data = aggregated_data.get(timestamp, {})
            
            for sig_name in signals:
                if sig_name in original_data and original_data[sig_name] is not None:
                    bucket_values[bucket][sig_name] = original_data[sig_name]
        
        # 步骤 2：跨区间前向填充（ffill）——消除"整 0.5s 桶空白"
        if bucket_values:
            sorted_buckets = sorted(bucket_values.keys())
            if sorted_buckets:
                # 还需要把所有真正出现过 timestamp 的桶（即便空）也纳入 ffill 顺序
                all_buckets = sorted(set(bucket_timestamps.keys()))
                last_values: Dict[str, Any] = {}
                # 从最早到最晚的桶依次推进
                min_bucket = min(all_buckets) if all_buckets else sorted_buckets[0]
                max_bucket = max(all_buckets) if all_buckets else sorted_buckets[-1]
                for b in range(min_bucket, max_bucket + 1):
                    cur = bucket_values.get(b)
                    if cur:
                        # 当前桶出现过新值：更新 last_values（只更新当前桶有值的那些信号）
                        # 同时把上一桶有但本桶没有的信号也带入 cur，保证本桶内 fill 可用
                        for sig_name, prev_val in last_values.items():
                            if sig_name not in cur:
                                cur[sig_name] = prev_val
                        # 然后 last_values = cur（全量拷贝，保留所有已知信号）
                        last_values = dict(last_values, **cur)
                    else:
                        # 本桶完全没出现任何信号：把前一桶的所有信号 last_values 灌入 bucket_values[b]
                        if last_values:
                            bucket_values[b] = dict(last_values)
                    # bucket_values[b] 现在对每个信号要么有本桶新值，要么有前向延续值
        
        # 步骤 3：逐行构建填充结果
        filled_data = {}
        for timestamp in sorted_timestamps:
            bucket = self._get_time_bucket(timestamp)
            original_data = aggregated_data.get(timestamp, {})
            filled_row = {}
            
            for sig_name in signals:
                if sig_name in original_data and original_data[sig_name] is not None:
                    filled_row[sig_name] = original_data[sig_name]
                elif bucket in bucket_values and sig_name in bucket_values[bucket]:
                    filled_row[sig_name] = bucket_values[bucket][sig_name]
                else:
                    filled_row[sig_name] = None
            
            filled_data[timestamp] = filled_row
        
        return filled_data
    
    def _sanitize_filename(self, group_name: str) -> str:
        """
        清理组名称，生成有效的文件名
        
        处理Windows文件系统不支持的特殊字符，确保文件名有效。
        
        Args:
            group_name: 原始组名称
        
        Returns:
            str: 清理后的安全文件名
        
        处理规则：
            1. 移除特殊字符：<>:"/\\|?* 和控制字符
            2. 移除首尾的空格和点
            3. 空字符串替换为 "Unknown"
            4. 限制长度为200字符（Windows限制255）
        
        Examples:
            >>> writer = EnhancedCSVWriter('./output')
            >>> writer._sanitize_filename('BATP3')
            'BATP3'
            >>> writer._sanitize_filename('Test<Group>')
            'Test_Group_'
        """
        # 移除文件系统不支持的特殊字符
        invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
        cleaned = re.sub(invalid_chars, '_', group_name)
        
        # 移除首尾空格和点
        cleaned = cleaned.strip('. ')
        
        # 确保不为空
        if not cleaned:
            cleaned = "Unknown"
        
        # 限制长度（Windows文件名限制）
        if len(cleaned) > 200:
            cleaned = cleaned[:200]
        
        return cleaned
    
    def _check_file_exists(self, filename: str) -> bool:
        """
        检查文件是否已存在
        
        Args:
            filename: 文件名（不含路径）
        
        Returns:
            bool: 文件是否存在
        
        Note:
            文件路径相对于 output_dir
        """
        file_path = os.path.join(self.output_dir, filename)
        return os.path.exists(file_path)
    
    def write_group_file(
        self,
        group_name: str,
        signals: List[str],
        sorted_timestamps: List[float],
        filled_data: Dict,
        signal_info: Dict
    ) -> Optional[str]:
        """
        写入单个分组文件
        
        为指定的分组创建CSV文件，包含该分组所有信号的时间序列数据。
        
        Args:
            group_name: 分组名称
                - 用于生成文件名（如 "BATP1" -> "BATP1.csv"）
                - 特殊字符会被自动清理
            signals: 该分组的信号名称列表
                - 决定CSV文件的列
            sorted_timestamps: 排序后的时间戳列表
                - 决定CSV文件的行
            filled_data: 填充后的数据
                - 键：时间戳
                - 值：{信号名称: 信号值} 字典
            signal_info: 信号信息字典
                - 用于获取信号单位，生成表头
        
        Returns:
            Optional[str]: 文件路径
                - 成功创建：返回完整的文件路径
                - 文件已存在且不允许覆盖：返回 None
                - 创建失败：返回 None
        
        Side Effects:
            - 创建CSV文件
            - 更新 created_files 或 existing_files 集合
            - 输出日志信息
        
        Examples:
            >>> writer = EnhancedCSVWriter('./output', overwrite=True)
            >>> path = writer.write_group_file(
            ...     'BATP1',
            ...     ['test.dbc::BatP1_Msg::sig1'],
            ...     [0.0, 0.1, 0.2],
            ...     {0.0: {'test.dbc::BatP1_Msg::sig1': 1.0}},
            ...     {'test.dbc::BatP1_Msg::sig1': {'unit': 'V'}}
            ... )
        """
        # 清理文件名
        safe_group_name = self._sanitize_filename(group_name)
        csv_filename = f"{safe_group_name}.csv"
        file_path = os.path.join(self.output_dir, csv_filename)
        
        # 检查文件是否已存在
        if not self.overwrite and self._check_file_exists(csv_filename):
            print(f"  跳过已存在文件: {csv_filename}")
            self.existing_files.add(file_path)
            return None
        
        # 排序信号
        sorted_signals = sorted(signals)
        
        # 生成表头
        header = self._generate_header(sorted_signals, signal_info)
        
        # 写入文件
        try:
            with open(file_path, 'w', newline='', encoding=self.encoding) as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(header)
                
                for timestamp in sorted_timestamps:
                    data = filled_data.get(timestamp, {})
                    row = self._build_row(timestamp, sorted_signals, data)
                    writer.writerow(row)
            
            print(f"  创建文件: {csv_filename}")
            self.created_files.add(file_path)
            return file_path
            
        except Exception as e:
            print(f"  创建文件失败: {csv_filename} - {e}")
            return None
    
    def write_all_groups(
        self,
        classified_signals: Dict[str, List[str]],
        sorted_timestamps: List[float],
        aggregated_data: Dict[float, Dict[str, Any]],
        signal_info: Dict[str, Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        为所有分组创建CSV文件
        
        遍历所有分组，为每个分组调用 write_group_file 创建独立的CSV文件。
        同时处理空值填充，确保数据连续性。
        
        Args:
            classified_signals: 分类后的信号
                - 键：组名称（如 'BATP1', 'BATPS', 'Others'）
                - 值：属于该组的信号名称列表
            sorted_timestamps: 排序后的时间戳列表
                - 所有CSV文件使用相同的时间轴
            aggregated_data: 聚合数据
                - 键：时间戳
                - 值：{信号名称: 信号值} 字典
            signal_info: 信号信息
                - 键：完整信号名称
                - 值：{'unit': 单位, 'message': 消息名, 'dbc': DBC文件名}
        
        Returns:
            Dict[str, Any]: 结果统计字典，包含：
                - created_files: 创建的文件路径列表
                - skipped_files: 跳过的组名称列表
                - total_groups: 总分组数
                - created_count: 成功创建的文件数
                - skipped_count: 跳过的文件数
        
        Side Effects:
            - 创建多个CSV文件
            - 输出进度日志
        
        Examples:
            >>> writer = EnhancedCSVWriter('./output', overwrite=True)
            >>> result = writer.write_all_groups(
            ...     classified_signals={'BATP1': ['sig1'], 'Others': ['sig2']},
            ...     sorted_timestamps=[0.0, 0.1],
            ...     aggregated_data={0.0: {'sig1': 1.0, 'sig2': 2.0}},
            ...     signal_info={}
            ... )
            >>> print(result['created_count'])
            2
        """
        result = {
            'created_files': [],
            'skipped_files': [],
            'total_groups': len(classified_signals),
            'created_count': 0,
            'skipped_count': 0
        }
        
        # 收集所有信号用于填充
        all_signals = []
        for signals in classified_signals.values():
            all_signals.extend(signals)
        all_signals = sorted(set(all_signals))
        
        # 填充缺失值
        filled_data = self._fill_missing_values(
            sorted_timestamps, aggregated_data, all_signals
        )
        
        print(f"  已完成空值填充（填充间隔: {self.fill_interval}秒）")
        
        # 为每个组创建文件
        for group_name in sorted(classified_signals.keys()):
            signals = classified_signals[group_name]
            file_path = self.write_group_file(
                group_name, signals, sorted_timestamps,
                filled_data, signal_info
            )
            
            if file_path:
                result['created_files'].append(file_path)
                result['created_count'] += 1
            else:
                result['skipped_files'].append(group_name)
                result['skipped_count'] += 1
        
        return result
    
    def write_summary_file(
        self,
        classified_signals: Dict[str, List[str]],
        sorted_timestamps: List[float],
        result_stats: Dict[str, Any]
    ) -> str:
        """
        写入汇总文件
        
        创建Summary.csv文件，包含转换过程的统计信息和各分组的详情。
        
        Args:
            classified_signals: 分类信号字典
            sorted_timestamps: 时间戳列表
            result_stats: write_all_groups 返回的结果统计
        
        Returns:
            str: 汇总文件的完整路径
        
        汇总文件内容：
            1. 转换配置信息（分组模式、填充间隔等）
            2. 数据统计（时间点数、信号数、分组数）
            3. 文件生成统计
            4. 各分组详情（分组名称、信号数量、文件名、状态）
        
        Examples:
            >>> writer = EnhancedCSVWriter('./output')
            >>> path = writer.write_summary_file(
            ...     classified_signals={'BATP1': ['sig1']},
            ...     sorted_timestamps=[0.0, 0.1],
            ...     result_stats={'created_count': 1, 'skipped_count': 0}
            ... )
        """
        summary_filename = os.path.join(self.output_dir, "Summary.csv")
        
        with open(summary_filename, 'w', newline='', encoding=self.encoding) as csvfile:
            writer = csv.writer(csvfile)
            
            writer.writerow(["数据转换汇总报告"])
            writer.writerow([])
            writer.writerow(["分组模式", "动态组名称提取"])
            writer.writerow(["分组规则", "BatP+数字 或 BatP+1-2个字母"])
            writer.writerow(["空值填充间隔", f"{self.fill_interval}秒"])
            writer.writerow(["覆盖模式", "是" if self.overwrite else "否"])
            writer.writerow([])
            writer.writerow(["数据统计"])
            writer.writerow(["采样后时间点数", len(sorted_timestamps)])
            writer.writerow(["信号总数", sum(len(s) for s in classified_signals.values())])
            writer.writerow(["分组数量", len(classified_signals)])
            writer.writerow([])
            writer.writerow(["文件生成统计"])
            writer.writerow(["成功创建", result_stats.get('created_count', 0)])
            writer.writerow(["跳过已存在", result_stats.get('skipped_count', 0)])
            writer.writerow([])
            writer.writerow(["各分组详情"])
            writer.writerow(["分组名称", "信号数量", "文件名", "状态"])
            
            for group_name in sorted(classified_signals.keys()):
                signals = classified_signals[group_name]
                safe_group_name = self._sanitize_filename(group_name)
                csv_filename = f"{safe_group_name}.csv"
                
                # 检查文件状态
                file_path = os.path.join(self.output_dir, csv_filename)
                if file_path in self.created_files:
                    status = "已创建"
                elif file_path in self.existing_files:
                    status = "已存在（跳过）"
                else:
                    status = "未创建"
                
                writer.writerow([
                    group_name,
                    len(signals),
                    csv_filename,
                    status
                ])
        
        print(f"  创建汇总文件: {summary_filename}")
        return summary_filename
    
    def _generate_header(self, signals: List[str], signal_info: Dict) -> List[str]:
        """
        生成CSV表头
        
        表头格式：
            - 第一列：Time[s]
            - 后续列：{信号短名称}[{单位}] 或 {信号短名称}
        
        Args:
            signals: 信号名称列表（完整格式）
            signal_info: 信号信息字典
        
        Returns:
            List[str]: 表头列表
        
        Examples:
            >>> writer = EnhancedCSVWriter('./output')
            >>> header = writer._generate_header(
            ...     ['test.dbc::Msg::Voltage'],
            ...     {'test.dbc::Msg::Voltage': {'unit': 'V'}}
            ... )
            >>> print(header)
            ['Time[s]', 'Voltage[V]']
        """
        header = ["Time" if self.start_time > 0 else "Time[s]"]
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
        
        将单个时间戳的所有信号值组织为一行数据。
        
        Args:
            timestamp: 时间戳（秒）
            signals: 信号名称列表（决定列顺序）
            data: 该时间戳的数据字典 {信号名称: 信号值}
        
        Returns:
            List[Any]: 数据行
                - 第一元素：时间戳（保留1位小数）
                - 后续元素：信号值或空字符串
        
        Note:
            - 使用 safe_value() 处理信号值，确保格式正确
            - 缺失值用空字符串表示
        """
        if self.start_time > 0:
            total = timestamp + self.start_time
            whole = int(total)
            frac = round((total - whole) * 10)
            if frac == 10:
                # 向上进位 1 秒
                whole += 1
                frac = 0
            frac %= 10
            dt = datetime.fromtimestamp(whole)
            # 格式: yyyy/mm/dd h:mm:ss.f
            #   - 年 4 位、月/日 2 位补零、小时不补零（1~2 位）
            #   - 分/秒 2 位补零、1 位小数
            date_part = f"{dt.year:04d}/{dt.month:02d}/{dt.day:02d}"
            time_part = f"{dt.hour}:{dt.minute:02d}:{dt.second:02d}"
            row = [f"{date_part} {time_part}.{frac}"]
        else:
            row = [round(timestamp, 1)]
        for sig_name in signals:
            if sig_name in data and data[sig_name] is not None:
                row.append(safe_value(data[sig_name]))
            else:
                row.append("")
        return row
    
    def get_created_files(self) -> List[str]:
        """
        获取所有创建的文件列表
        
        Returns:
            List[str]: 已创建的文件完整路径列表（排序后）
        """
        return sorted(self.created_files)
    
    def get_existing_files(self) -> List[str]:
        """
        获取已存在的文件列表
        
        Returns:
            List[str]: 已存在且被跳过的文件完整路径列表（排序后）
        """
        return sorted(self.existing_files)
    
    def clear(self):
        """
        清空写入器状态
        
        重置已创建文件和已存在文件的记录。
        通常在处理新的数据集之前调用。
        """
        self.created_files.clear()
        self.existing_files.clear()
