# asc_to_csv/multi_asc_converter.py
"""
多ASC文件转换器模块

本模块实现多ASC模式下的转换架构，采用"分别转换+CSV拼接"的方案。

架构流程：
    1. 按文件名时间戳排序ASC文件
    2. 循环处理每个ASC文件：
       2.1 解析ASC文件
       2.2 数据处理
       2.3 按分组输出临时CSV文件
    3. 按分组拼接临时CSV为最终CSV
    4. 清理临时文件

特性：
    - 单ASC模式不受影响
    - 临时文件自动管理
    - 进度实时反馈
    - 错误恢复机制

使用示例：
    >>> from multi_asc_converter import MultiASCConverter
    >>> from config import Config
    >>> config = Config(
    ...     asc_files=['file2.asc', 'file1.asc'],
    ...     multi_file_mode=True,
    ...     dbc_files=['test.dbc'],
    ...     output_dir='./output'
    ... )
    >>> converter = MultiASCConverter(config)
    >>> result = converter.convert()
"""

import os
import shutil
import tempfile
from typing import Optional, Callable, List, Dict, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from config import Config
from dbc_loader import DBCLoader
from asc_parser import ASCParser
from enhanced_data_processor import EnhancedDataProcessor
from enhanced_csv_writer import EnhancedCSVWriter
from asc_file_merger import ASCFileMerger
from csv_merger import CSVFileMerger


@dataclass
class MultiASCResult:
    """
    多ASC转换结果数据类

    Attributes:
        success: 转换是否成功
        created_files: 创建的最终CSV文件列表
        temp_files: 临时CSV文件列表（已清理）
        discovered_groups: 发现的分组列表
        group_statistics: 分组统计信息
        error_message: 错误信息（如果有）
        total_rows: 拼接后的总行数
        output_dir: 输出目录
    """
    success: bool = False
    created_files: List[str] = field(default_factory=list)
    temp_files: List[str] = field(default_factory=list)
    discovered_groups: List[str] = field(default_factory=list)
    group_statistics: Dict[str, int] = field(default_factory=dict)
    error_message: str = ""
    total_rows: int = 0
    output_dir: str = ""


class MultiASCConverter:
    """
    多ASC文件转换器

    采用"分别转换+CSV拼接"架构：
    1. 每个ASC文件独立解析并输出临时CSV
    2. 相同分组的临时CSV按时间顺序拼接
    3. 最终输出多个按分组分类的完整CSV文件

    Attributes:
        config: 配置对象
        dbc_loader: DBC加载器
        temp_dir: 临时文件目录
        temp_csv_groups: 临时CSV分组映射
    """

    def __init__(self, config: Config):
        """
        初始化多ASC转换器

        Args:
            config: 配置对象，包含ASC文件列表、DBC文件列表、输出目录等
        """
        if not config.multi_file_mode:
            raise ValueError("MultiASCConverter只能在多文件模式下使用")

        self.config = config
        self.dbc_loader: Optional[DBCLoader] = None
        self.temp_dir: str = ""
        self.temp_csv_groups: Dict[str, List[str]] = defaultdict(list)
        self._log_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[float, int], None]] = None

    def _log(self, message: str):
        """内部日志函数"""
        if self._log_callback:
            self._log_callback(message)
        else:
            print(message)

    def _setup_temp_dir(self) -> bool:
        """
        设置临时目录

        Returns:
            bool: 是否成功
        """
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="asc_multi_")
            self._log(f"临时目录: {self.temp_dir}")
            return True
        except Exception as e:
            self._log(f"创建临时目录失败: {e}")
            return False

    def _cleanup_temp_dir(self):
        """清理临时目录"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                self._log(f"临时目录已清理: {self.temp_dir}")
            except Exception as e:
                self._log(f"清理临时目录失败: {e}")

    def _load_dbc(self) -> bool:
        """
        加载DBC文件

        Returns:
            bool: 是否成功
        """
        self._log("正在加载DBC文件...")

        self.dbc_loader = DBCLoader()

        try:
            success = self.dbc_loader.load(self.config.dbc_files)
            if success:
                for dbc_file in self.config.dbc_files:
                    self._log(f"  + {dbc_file}")
                self._log(f"DBC加载完成，共 {len(self.dbc_loader.message_map)} 条消息映射")
            return success
        except Exception as e:
            self._log(f"  - 加载失败: {e}")
            return False

    def _sort_asc_files(self) -> List[str]:
        """
        按时间戳排序ASC文件

        Returns:
            List[str]: 排序后的ASC文件路径列表
        """
        self._log("正在排序ASC文件...")

        merger = ASCFileMerger()
        sorted_files = merger.sort_files_by_time(self.config.asc_files)

        for i, f in enumerate(sorted_files):
            ts = merger.extract_time_from_filename(f)
            self._log(f"  [{i+1}] {os.path.basename(f)} -> 时间戳: {ts}")

        return sorted_files

    def _process_single_asc(
        self,
        asc_file: str,
        asc_index: int,
        message_map: Dict
    ) -> Tuple[bool, str, Dict[str, List[str]]]:
        """
        处理单个ASC文件

        Args:
            asc_file: ASC文件路径
            asc_index: ASC文件索引（用于临时文件命名）
            message_map: 消息映射

        Returns:
            Tuple[bool, str, Dict[str, List[str]]]: (是否成功, 错误信息, 分组到临时文件的映射)
        """
        file_temp_csvs: Dict[str, List[str]] = defaultdict(list)

        self._log(f"\n处理ASC文件 [{asc_index}]: {os.path.basename(asc_file)}")

        parser = ASCParser(
            sample_interval=self.config.sample_interval,
            debug=self.config.debug
        )

        def progress_callback(progress: float, line_count: int):
            if self._progress_callback:
                self._progress_callback(progress, line_count)

        if not parser.parse(asc_file, message_map, progress_callback):
            return False, "ASC解析失败", {}

        processor = EnhancedDataProcessor()
        processor.aggregate(parser.sampled_data)
        processor.classify_signals(parser.found_signals)

        temp_output_dir = os.path.join(self.temp_dir, f"asc_{asc_index}")
        os.makedirs(temp_output_dir, exist_ok=True)

        writer = EnhancedCSVWriter(
            output_dir=temp_output_dir,
            encoding=self.config.csv_encoding,
            overwrite=True,
            start_time=parser.start_time
        )

        write_result = writer.write_all_groups(
            classified_signals=processor.classified_signals,
            sorted_timestamps=processor.get_sorted_timestamps(),
            aggregated_data=processor.aggregated_data,
            signal_info=self.dbc_loader.signal_info if self.dbc_loader else {}
        )

        if write_result.get('created_files'):
            for csv_file in write_result['created_files']:
                group_name = os.path.splitext(os.path.basename(csv_file))[0]
                file_temp_csvs[group_name].append(csv_file)

        self._log(f"  解析完成: {parser.original_count} 数据点, {len(processor.classified_signals)} 分组")

        return True, "", file_temp_csvs

    def _merge_group_csvs(
        self,
        group_name: str,
        temp_csvs: List[str],
        output_path: str
    ) -> Tuple[bool, int]:
        """
        拼接单个分组的临时CSV文件

        Args:
            group_name: 分组名称
            temp_csvs: 该分组的临时CSV文件列表
            output_path: 最终输出文件路径

        Returns:
            Tuple[bool, int]: (是否成功, 总行数)
        """
        if not temp_csvs:
            return True, 0

        if len(temp_csvs) == 1:
            shutil.copy(temp_csvs[0], output_path)
            merger = CSVFileMerger()
            rows = merger.get_csv_row_count(output_path)
            return True, rows

        merger = CSVFileMerger()
        result = merger.merge_csv_files(temp_csvs, output_path)

        return result.success, result.total_rows

    def convert(
        self,
        progress_callback: Optional[Callable[[float, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> MultiASCResult:
        """
        执行多ASC文件转换

        流程：
        1. 排序ASC文件
        2. 循环处理每个ASC文件，输出临时CSV
        3. 按分组拼接临时CSV
        4. 清理临时文件

        Args:
            progress_callback: 进度回调函数 (progress: float, line_count: int)
            log_callback: 日志回调函数 (message: str)

        Returns:
            MultiASCResult: 转换结果
        """
        result = MultiASCResult()
        result.output_dir = self.config.output_dir

        self._progress_callback = progress_callback
        self._log_callback = log_callback

        try:
            self._log("=" * 60)
            self._log("多ASC模式转换开始")
            self._log(f"ASC文件数量: {len(self.config.asc_files)}")
            self._log(f"输出目录: {self.config.output_dir}")
            self._log("=" * 60)

            if not self.config.validate():
                result.error_message = "配置验证失败"
                return result

            os.makedirs(self.config.output_dir, exist_ok=True)

            if not self._load_dbc():
                result.error_message = "DBC文件加载失败"
                return result

            sorted_files = self._sort_asc_files()

            if not self._setup_temp_dir():
                result.error_message = "临时目录创建失败"
                return result

            all_group_temp_csvs: Dict[str, List[str]] = defaultdict(list)

            for asc_idx, asc_file in enumerate(sorted_files):
                success, error_msg, file_temp_csvs = self._process_single_asc(
                    asc_file, asc_idx, self.dbc_loader.message_map
                )

                if not success:
                    self._log(f"警告: 处理失败 {asc_file}: {error_msg}")
                    continue

                for group_name, csv_list in file_temp_csvs.items():
                    all_group_temp_csvs[group_name].extend(csv_list)

            self._log("\n" + "=" * 60)
            self._log("开始拼接CSV文件")
            self._log("=" * 60)

            total_rows = 0
            discovered_groups = sorted(all_group_temp_csvs.keys())

            for group_idx, group_name in enumerate(discovered_groups):
                temp_csvs = all_group_temp_csvs[group_name]

                self._log(f"\n拼接分组 [{group_idx + 1}/{len(discovered_groups)}]: {group_name}")
                self._log(f"  临时文件数量: {len(temp_csvs)}")

                output_path = os.path.join(self.config.output_dir, f"{group_name}.csv")

                success, rows = self._merge_group_csvs(group_name, temp_csvs, output_path)

                if success:
                    result.created_files.append(output_path)
                    total_rows += rows
                    result.group_statistics[group_name] = rows
                    self._log(f"  -> 输出: {os.path.basename(output_path)} ({rows} 行)")
                else:
                    self._log(f"  -> 拼接失败: {group_name}")

            result.total_rows = total_rows
            result.discovered_groups = discovered_groups
            result.success = True

            self._log("\n" + "=" * 60)
            self._log("转换完成!")
            self._log(f"输出目录: {result.output_dir}")
            self._log(f"发现分组: {len(discovered_groups)} 个")
            self._log(f"总数据行: {total_rows} 行")
            self._log("=" * 60)

        except Exception as e:
            result.error_message = f"转换失败: {type(e).__name__}: {e}"
            self._log(result.error_message)

        finally:
            self._cleanup_temp_dir()

        return result


def convert_multi_asc(
    config: Config,
    progress_callback: Optional[Callable[[float, int], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> MultiASCResult:
    """
    快捷函数：执行多ASC文件转换

    Args:
        config: 配置对象
        progress_callback: 进度回调函数
        log_callback: 日志回调函数

    Returns:
        MultiASCResult: 转换结果
    """
    converter = MultiASCConverter(config)
    return converter.convert(progress_callback, log_callback)