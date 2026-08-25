# asc_to_csv/csv_merger.py
"""
CSV文件拼接模块

本模块负责将多个CSV文件按时间顺序拼接为一个完整的CSV文件。

主要功能：
    - 按文件名时间戳排序CSV文件
    - 拼接时按列名对齐：表头取所有文件列的并集，缺失列留空
    - 时间基准不一致的文件（'Time'与'Time[s]'混用）跳过并警告
    - 保持各文件内部数据行的原有顺序
    - 确保整体CSV文件格式正确

使用示例：
    >>> from csv_merger import CSVFileMerger
    >>> merger = CSVFileMerger()
    >>> result = merger.merge_csv_files(['file2.csv', 'file1.csv'], 'output.csv')
    >>> print(f"成功: {result.success}, 行数: {result.total_rows}")
"""

import os
import csv
import re
from typing import List, Optional, Callable, Tuple, Any
from dataclasses import dataclass


@dataclass
class CSVMergeResult:
    """
    CSV拼接结果数据类

    Attributes:
        success: 拼接是否成功
        output_path: 输出文件路径
        total_rows: 总行数（不含表头）
        total_files: 处理的CSV文件数量
        first_csv_header: 第一个CSV文件的表头
        error_message: 错误信息（如果有）
    """
    success: bool = False
    output_path: str = ""
    total_rows: int = 0
    total_files: int = 0
    first_csv_header: Optional[List[str]] = None
    error_message: str = ""


class CSVFileMerger:
    """
    CSV文件拼接器

    负责将多个CSV文件按顺序拼接为一个完整的CSV文件。

    拼接规则：
        1. 以首个时间列为 'Time'（绝对时间）的文件表头为基准，
           其余文件的新增列按出现顺序追加，构成完整列集合
        2. 各文件的数据行按列名映射到完整列集合，缺失的列留空
        3. 时间基准不一致的文件（'Time' 与 'Time[s]' 混用）跳过并警告
        4. 按排序后的顺序依次处理每个CSV文件，数据行追加到输出文件
    """

    TIME_PATTERN = re.compile(r'(\d{8}[_-]\d{4}|\d{10,})')

    def __init__(self):
        """初始化CSV文件拼接器"""
        pass

    def extract_timestamp_from_filename(self, filename: str) -> Optional[int]:
        """
        从文件名中提取时间戳数值

        支持格式：
            - log_20260126_2121 → 202601262121
            - 202601262121.csv → 202601262121
            - data_2026-01-26_21-21.csv → 2026012121

        Args:
            filename: 文件名或文件路径

        Returns:
            Optional[int]: 提取的时间戳整数，如果无法提取则返回None
        """
        basename = os.path.basename(filename)
        match = self.TIME_PATTERN.search(basename)

        if match:
            time_str = match.group(1).replace('-', '').replace('_', '')
            try:
                return int(time_str)
            except ValueError:
                pass

        return None

    def sort_csv_files(self, file_paths: List[str]) -> List[str]:
        """
        根据文件名中的时间戳对CSV文件排序

        Args:
            file_paths: CSV文件路径列表

        Returns:
            List[str]: 排序后的文件路径列表

        Raises:
            ValueError: 当文件列表为空时
        """
        if not file_paths:
            raise ValueError("文件列表为空")

        files_with_time = []
        for file_path in file_paths:
            time_value = self.extract_timestamp_from_filename(file_path)
            files_with_time.append((file_path, time_value if time_value else 0))

        files_with_time.sort(key=lambda x: x[1])

        return [f[0] for f in files_with_time]

    def get_csv_header(self, file_path: str) -> Tuple[bool, List[str]]:
        """
        获取CSV文件的表头

        Args:
            file_path: CSV文件路径

        Returns:
            Tuple[bool, List[str]]: (是否成功, 表头列表)
        """
        try:
            with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        return True, row
                return False, []
        except Exception:
            return False, []

    def get_csv_row_count(self, file_path: str) -> int:
        """
        获取CSV文件的数据行数（不含表头）

        Args:
            file_path: CSV文件路径

        Returns:
            int: 数据行数
        """
        try:
            row_count = 0
            with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                reader = csv.reader(f)
                header_read = False
                for row in reader:
                    if row:
                        if not header_read:
                            header_read = True
                            continue
                        row_count += 1
            return row_count
        except Exception:
            return 0

    def validate_csv_file(self, file_path: str) -> Tuple[bool, str, List[str]]:
        """
        验证CSV文件格式

        Args:
            file_path: CSV文件路径

        Returns:
            Tuple[bool, str, List[str]]: (是否有效, 错误信息, 表头列表)
        """
        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}", []

        if not os.path.isfile(file_path):
            return False, f"不是有效文件: {file_path}", []

        if not file_path.lower().endswith('.csv'):
            return False, f"文件不是.csv格式: {file_path}", []

        success, header = self.get_csv_header(file_path)
        if not success:
            return False, f"无法读取CSV文件: {file_path}", []

        if not header:
            return False, f"CSV文件为空或无有效表头: {file_path}", []

        return True, "", header

    def merge_csv_files(
        self,
        csv_files: List[str],
        output_path: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> CSVMergeResult:
        """
        拼接多个CSV文件

        各文件的表头可能因包含的信号集合不同而不完全一致（例如某个报文只在
        部分ASC文件中出现过），拼接时按"列名对齐"策略处理：
            1. 以首个时间列为 'Time'（绝对时间）的文件表头为基准
               （若无则使用第一个文件的表头）
            2. 基准表头 + 其余文件按出现顺序追加的新列，构成完整列集合
            3. 每个文件的数据行按列名映射到完整列集合，缺失的列留空
            4. 时间基准必须一致：'Time'（绝对时间）与 'Time[s]'（相对时间）
               不能混拼，基准不一致的文件会被跳过并给出警告

        Args:
            csv_files: CSV文件路径列表（建议已排序）
            output_path: 输出文件路径
            progress_callback: 进度回调函数

        Returns:
            CSVMergeResult: 拼接结果
        """
        result = CSVMergeResult()
        result.output_path = output_path

        if not csv_files:
            result.error_message = "CSV文件列表为空"
            return result

        if len(csv_files) == 1:
            try:
                import shutil
                shutil.copy(csv_files[0], output_path)
                result.success = True
                result.total_files = 1
                result.total_rows = self.get_csv_row_count(csv_files[0])
                _, header = self.get_csv_header(csv_files[0])
                result.first_csv_header = header
                return result
            except Exception as e:
                result.error_message = f"复制文件失败: {str(e)}"
                return result

        if progress_callback:
            progress_callback(f"开始拼接 {len(csv_files)} 个CSV文件...")

        sorted_files = self.sort_csv_files(csv_files)

        result.total_files = len(sorted_files)

        # 预扫描：校验所有文件并收集表头
        valid_files: List[Tuple[str, List[str]]] = []
        for csv_file in sorted_files:
            success, error_msg, header = self.validate_csv_file(csv_file)
            if not success:
                if progress_callback:
                    progress_callback(f"警告: 跳过无效文件 {os.path.basename(csv_file)}: {error_msg}")
                continue
            valid_files.append((csv_file, header))

        if not valid_files:
            result.error_message = "没有可拼接的有效CSV文件"
            return result

        # 确定基准时间列：优先 'Time'（绝对时间），
        # 避免第一个文件date行未解析（'Time[s]'相对时间）时其余文件被全部跳过
        if any(header and header[0] == 'Time' for _, header in valid_files):
            base_time_col = 'Time'
        else:
            base_time_col = valid_files[0][1][0]

        # 只有时间基准与基准一致的文件才参与合并，完整列集合仅由可合并文件构成
        merge_files = [(f, h) for f, h in valid_files if h[0] == base_time_col]

        # 基准表头：时间基准一致的第一个文件
        base_header = merge_files[0][1]

        # 构建完整列集合：基准表头 + 其余可合并文件按出现顺序追加的新列
        master_header = list(base_header)
        seen_columns = set(master_header)
        for _, header in merge_files:
            for col in header:
                if col not in seen_columns:
                    seen_columns.add(col)
                    master_header.append(col)

        result.first_csv_header = master_header

        if progress_callback:
            progress_callback(f"使用表头（共{len(master_header)}列，按列名对齐）: {master_header[:5]}...")

        try:
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

            with open(output_path, 'w', encoding='utf-8-sig', newline='') as outfile:
                writer = csv.writer(outfile)

                writer.writerow(master_header)

                total_rows = 0
                for file_idx, (csv_file, header) in enumerate(valid_files):
                    if progress_callback:
                        progress_callback(f"处理文件 [{file_idx + 1}/{len(valid_files)}]: {os.path.basename(csv_file)}")

                    # 时间基准一致性检查：'Time'（绝对时间）与 'Time[s]'（相对时间）不能混拼
                    if header[0] != master_header[0]:
                        if progress_callback:
                            progress_callback(
                                f"警告: 跳过 {os.path.basename(csv_file)}"
                                f"（时间列 {header[0]} 与基准 {master_header[0]} 不一致，"
                                f"该文件date行可能未解析成功，时间为相对值）"
                            )
                        continue

                    with open(csv_file, 'r', encoding='utf-8-sig', errors='ignore') as infile:
                        reader = csv.reader(infile)
                        header_read = False

                        if header == master_header:
                            # 快速路径：表头完全一致，直接逐行拷贝
                            for row in reader:
                                if row:
                                    if not header_read:
                                        header_read = True
                                        continue

                                    writer.writerow(row)
                                    total_rows += 1
                        else:
                            # 按列名映射对齐，缺失的列留空
                            col_index = {name: i for i, name in enumerate(header)}
                            indices = [col_index.get(col) for col in master_header]
                            absent_count = sum(1 for idx in indices if idx is None)
                            if progress_callback:
                                progress_callback(
                                    f"  表头不完全一致，按列名对齐"
                                    f"（该文件缺少{absent_count}列，留空处理）"
                                )
                            for row in reader:
                                if row:
                                    if not header_read:
                                        header_read = True
                                        continue

                                    writer.writerow([
                                        row[idx] if idx is not None and idx < len(row) else ''
                                        for idx in indices
                                    ])
                                    total_rows += 1

                    if progress_callback:
                        progress_callback(f"  -> 已添加数据行，当前总计: {total_rows}")

                result.success = True
                result.total_rows = total_rows

                if progress_callback:
                    progress_callback(f"拼接完成！共 {total_rows} 行数据（来自 {len(valid_files)} 个文件）")

        except PermissionError:
            result.error_message = f"权限错误，无法写入文件: {output_path}"
        except Exception as e:
            result.error_message = f"拼接失败: {type(e).__name__}: {str(e)}"

        return result


def merge_csv_files(
    csv_files: List[str],
    output_path: str,
    progress_callback: Optional[Callable[[str], None]] = None
) -> CSVMergeResult:
    """
    快捷函数：拼接多个CSV文件

    Args:
        csv_files: CSV文件路径列表
        output_path: 输出文件路径
        progress_callback: 进度回调函数

    Returns:
        CSVMergeResult: 拼接结果
    """
    merger = CSVFileMerger()
    return merger.merge_csv_files(csv_files, output_path, progress_callback)


def sort_csv_files_by_time(file_paths: List[str]) -> List[str]:
    """
    快捷函数：按时间戳排序CSV文件

    Args:
        file_paths: CSV文件路径列表

    Returns:
        List[str]: 排序后的文件路径列表
    """
    merger = CSVFileMerger()
    return merger.sort_csv_files(file_paths)