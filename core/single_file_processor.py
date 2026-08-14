# asc_to_csv/core/single_file_processor.py
"""
单文件处理器模块

负责处理单文件模式的ASC到CSV转换，包括单个ASC文件的解析和转换。

职责：
    - 解析单个ASC文件
    - 处理进度回调
    - 返回解析结果统计
"""

import os
from typing import Optional, Callable, Tuple

from config import Config
from dbc_loader import DBCLoader
from asc_parser import ASCParser
from enhanced_data_processor import EnhancedDataProcessor
from enhanced_csv_writer import EnhancedCSVWriter


class SingleFileProcessor:
    """
    单文件模式处理器

    处理单个ASC文件的完整转换流程。

    Attributes:
        config: 配置对象
        dbc_loader: DBC文件加载器
        asc_parser: ASC文件解析器
        data_processor: 数据处理器
        csv_writer: CSV写入器
    """

    def __init__(self, config: Config):
        """
        初始化单文件处理器

        Args:
            config: 配置对象
        """
        self.config = config
        self.dbc_loader: Optional[DBCLoader] = None
        self.asc_parser: Optional[ASCParser] = None
        self.data_processor: Optional[EnhancedDataProcessor] = None
        self.csv_writer: Optional[EnhancedCSVWriter] = None

    def process(
        self,
        progress_callback: Optional[Callable[[float, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        overwrite: bool = False
    ) -> Tuple[bool, dict]:
        """
        处理单文件转换

        Args:
            progress_callback: 进度回调函数 (progress: float, line_count: int)
            log_callback: 日志回调函数 (message: str)
            overwrite: 是否覆盖已存在的文件

        Returns:
            Tuple[bool, dict]: (是否成功, 结果字典)
                - success: 是否成功
                - created_files: 创建的文件列表
                - skipped_files: 跳过的文件列表
                - discovered_groups: 发现的分组列表
                - group_statistics: 分组统计
                - original_count: 原始数据点数
                - sampled_count: 采样后时间点数
                - signal_count: 实际信号数
        """
        result = {
            'success': False,
            'created_files': [],
            'skipped_files': [],
            'discovered_groups': [],
            'group_statistics': {},
            'original_count': 0,
            'sampled_count': 0,
            'signal_count': 0,
            'error_message': ''
        }

        try:
            if not self._load_dbc(log_callback):
                result['error_message'] = "DBC文件加载失败"
                return False, result

            if not self._parse_asc(progress_callback, log_callback):
                result['error_message'] = "ASC文件解析失败"
                return False, result

            self._process_data(log_callback)

            statistics = self._get_statistics()
            result['original_count'] = statistics['original_count']
            result['sampled_count'] = statistics['sampled_count']
            result['signal_count'] = statistics['signal_count']

            write_result = self._write_csv(log_callback, overwrite)
            result['created_files'] = write_result.get('created_files', [])
            result['skipped_files'] = write_result.get('skipped_files', [])

            result['discovered_groups'] = self.data_processor.sorted_groups
            result['group_statistics'] = self.data_processor.get_group_statistics()
            result['success'] = True

        except Exception as e:
            result['error_message'] = f"{type(e).__name__}: {e}"

        return result['success'], result

    def _log(self, callback: Optional[Callable[[str], None]], message: str):
        """输出日志消息"""
        if callback:
            callback(message)
        else:
            print(message)

    def _load_dbc(self, log_callback: Optional[Callable[[str], None]]) -> bool:
        """
        加载DBC文件

        Args:
            log_callback: 日志回调函数

        Returns:
            bool: 加载是否成功
        """
        self._log(log_callback, "正在加载DBC文件...")

        self.dbc_loader = DBCLoader()
        if not self.dbc_loader.load(self.config.dbc_files):
            return False

        self._log(log_callback, f"总消息定义数: {self.dbc_loader.get_message_count()}")
        self._log(log_callback, f"总信号定义数: {self.dbc_loader.get_signal_count()}")
        self._log(log_callback, "")

        return True

    def _parse_asc(
        self,
        progress_callback: Optional[Callable[[float, int], None]],
        log_callback: Optional[Callable[[str], None]]
    ) -> bool:
        """
        解析ASC文件

        Args:
            progress_callback: 进度回调函数
            log_callback: 日志回调函数

        Returns:
            bool: 解析是否成功
        """
        self._log(log_callback, "正在解析ASC文件...")
        self._log(log_callback, "进度: 0%")

        self.asc_parser = ASCParser(
            sample_interval=self.config.sample_interval,
            debug=self.config.debug
        )

        def internal_progress_callback(progress: float, line_count: int):
            if progress_callback:
                progress_callback(progress, line_count)
            if log_callback and progress % 10 < 1:
                self._log(log_callback, f"进度: {progress:.1f}% (已处理 {line_count:,} 行)")

        if not self.asc_parser.parse(
            self.config.single_asc_file,
            self.dbc_loader.message_map,
            internal_progress_callback
        ):
            return False

        original_count, sampled_count, signal_count = self.asc_parser.get_statistics()
        self._log(log_callback, f"解析完成：原始数据点数: {original_count}, 采样后时间点数: {sampled_count}, 实际信号数: {signal_count}")
        self._log(log_callback, "")

        return True

    def _process_data(self, log_callback: Optional[Callable[[str], None]]):
        """
        处理数据

        Args:
            log_callback: 日志回调函数
        """
        self._log(log_callback, "正在处理数据...")

        self.data_processor = EnhancedDataProcessor()
        self.data_processor.aggregate(self.asc_parser.sampled_data)
        self.data_processor.classify_signals(self.asc_parser.found_signals)

        self._log(log_callback, "分组结果：")
        for group_name, count in self.data_processor.get_group_statistics().items():
            self._log(log_callback, f"  {group_name}: {count}个信号")
        self._log(log_callback, "")

    def _get_statistics(self) -> dict:
        """
        获取统计信息

        Returns:
            dict: 统计信息字典
        """
        original_count, sampled_count, signal_count = self.asc_parser.get_statistics()
        return {
            'original_count': original_count,
            'sampled_count': sampled_count,
            'signal_count': signal_count
        }

    def _write_csv(
        self,
        log_callback: Optional[Callable[[str], None]],
        overwrite: bool
    ) -> dict:
        """
        写入CSV文件

        Args:
            log_callback: 日志回调函数
            overwrite: 是否覆盖已存在的文件

        Returns:
            dict: 写入结果
        """
        self._log(log_callback, "正在创建CSV文件...")

        self.csv_writer = EnhancedCSVWriter(
            output_dir=self.config.output_dir,
            encoding=self.config.csv_encoding,
            overwrite=overwrite,
            start_time=self.asc_parser.start_time if self.asc_parser else 0.0
        )

        write_result = self.csv_writer.write_all_groups(
            classified_signals=self.data_processor.classified_signals,
            sorted_timestamps=self.data_processor.get_sorted_timestamps(),
            aggregated_data=self.data_processor.aggregated_data,
            signal_info=self.dbc_loader.signal_info
        )

        self.csv_writer.write_summary_file(
            classified_signals=self.data_processor.classified_signals,
            sorted_timestamps=self.data_processor.get_sorted_timestamps(),
            result_stats=write_result
        )

        return write_result

    def cleanup(self):
        """清理资源"""
        if self.asc_parser:
            self.asc_parser.clear()
        if self.data_processor:
            self.data_processor.clear()
