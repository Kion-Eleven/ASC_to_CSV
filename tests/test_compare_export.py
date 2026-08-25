# asc_to_csv/tests/test_compare_export.py
"""
数据对比导出模块单元测试
验证时间格式化、列名解析、列请求匹配和宽表导出写入逻辑
"""

import csv
import os
import tempfile
from datetime import datetime
from typing import Generator

import pytest

from conftest import write_temp_text_file
from core.csv_loader import CSVDataLoader
from core.compare_export import (
    format_export_time,
    is_time_column,
    read_csv_header,
    resolve_matching_column,
    strip_column_prefix,
    write_export_csv,
)


def read_rows(path: str) -> list:
    """读取CSV全部行"""
    with open(path, 'r', newline='', encoding='utf-8-sig') as f:
        return list(csv.reader(f))


@pytest.fixture
def loader_file() -> Generator[str, None, None]:
    """创建用于列匹配测试的CSV文件"""
    content = (
        "Time[s],P5_AvgCellTemp[C],P5_PackSOC[%],P5_Mode,Unit\n"
        "0.0,25.5,80.5,Drive,km/h\n"
    )
    path = write_temp_text_file(content, encoding="utf-8-sig")
    yield path
    os.unlink(path)


@pytest.fixture
def loaded_loader(loader_file: str) -> CSVDataLoader:
    """加载测试CSV的加载器"""
    loader = CSVDataLoader()
    assert loader.load(loader_file)
    return loader


class TestStripColumnPrefix:
    def test_strips_prefix(self):
        assert strip_column_prefix('P5_AvgCellTemp[C]') == 'AvgCellTemp[C]'

    def test_no_underscore(self):
        assert strip_column_prefix('AvgCellTemp') == 'AvgCellTemp'


class TestIsTimeColumn:
    def test_time_variants(self):
        assert is_time_column('Time')
        assert is_time_column('Time[s]')
        assert is_time_column('TIME')
        assert is_time_column('Times')

    def test_non_time(self):
        assert not is_time_column('TimeMs')
        assert not is_time_column('PackSOC')


class TestFormatExportTime:
    def test_epoch_to_readable(self):
        dt = datetime(2026, 8, 13, 13, 52, 11)
        assert format_export_time(dt.timestamp() + 0.5) == "2026/08/13 13:52:11.5"

    def test_epoch_frac_rounding(self):
        dt = datetime(2026, 8, 13, 13, 52, 11)
        # 0.96 -> 进位到下一秒
        assert format_export_time(dt.timestamp() + 0.96) == "2026/08/13 13:52:12.0"

    def test_relative_seconds_unchanged(self):
        assert format_export_time(12.3) == "12.3"
        assert format_export_time(0) == "0"

    def test_empty_values(self):
        assert format_export_time(None) == ""
        assert format_export_time("") == ""

    def test_string_passthrough(self):
        assert format_export_time("abc") == "abc"


class TestReadCsvHeader:
    def test_reads_bom_header(self):
        path = write_temp_text_file("Time[s],A,B\n1,2,3\n", encoding="utf-8-sig")
        try:
            assert read_csv_header(path) == ["Time[s]", "A", "B"]
        finally:
            os.unlink(path)

    def test_unreadable_path(self):
        # 目录路径无法按文件读取，应返回空列表
        assert read_csv_header(tempfile.gettempdir()) == []


class TestResolveMatchingColumn:
    def test_fixed_substring(self, loaded_loader):
        col = resolve_matching_column(loaded_loader, 'fixed', 'PackSOC', 'Time[s]')
        assert col == 'P5_PackSOC[%]'

    def test_unified_exact(self, loaded_loader):
        col = resolve_matching_column(loaded_loader, 'unified', 'AvgCellTemp[C]', 'Time[s]')
        assert col == 'P5_AvgCellTemp[C]'

    def test_unified_skips_time_column(self, loaded_loader):
        assert resolve_matching_column(loaded_loader, 'unified', 'Time[s]', 'Time[s]') is None

    def test_unified_skips_non_numeric(self, loaded_loader):
        # P5_Mode首值为字符串'Drive'，即使公有名匹配也应跳过
        assert resolve_matching_column(loaded_loader, 'unified', 'Mode', 'Time[s]') is None

    def test_no_match(self, loaded_loader):
        assert resolve_matching_column(loaded_loader, 'fixed', 'XYZ', 'Time[s]') is None
        assert resolve_matching_column(loaded_loader, 'unified', 'XYZ', 'Time[s]') is None


class TestWriteExportCsv:
    def test_wide_table_alignment_and_padding(self):
        path = write_temp_text_file("", encoding="utf-8-sig")
        try:
            columns = [
                ("BATP3", "P3_AvgTemp", [1.0, 2.0]),
                ("BATP5", "P5_AvgTemp", [10.0, 20.0, 30.0]),
            ]
            rows, cols = write_export_csv(path, "Time[s]", [0.0, 0.1], columns)
            assert (rows, cols) == (3, 3)
            data = read_rows(path)
            assert data[0] == ["Time[s]", "P3_AvgTemp", "P5_AvgTemp"]
            assert data[1] == ["0.0", "1.0", "10.0"]
            assert data[2] == ["0.1", "2.0", "20.0"]
            # 第三个文件行数更多：时间列和短列留空
            assert data[3] == ["", "", "30.0"]
        finally:
            os.unlink(path)

    def test_duplicate_column_names_deduplicated(self):
        path = write_temp_text_file("", encoding="utf-8-sig")
        try:
            columns = [
                ("FileA", "Shared", [1, 2]),
                ("FileB", "Shared", [3, 4]),
            ]
            rows, cols = write_export_csv(path, None, [], columns)
            assert (rows, cols) == (2, 2)
            data = read_rows(path)
            assert data[0] == ["Shared", "Shared(FileB)"]
            assert data[1] == ["1", "3"]
            assert data[2] == ["2", "4"]
        finally:
            os.unlink(path)

    def test_none_values_as_empty(self):
        path = write_temp_text_file("", encoding="utf-8-sig")
        try:
            columns = [("F", "Col", [1.0, None])]
            write_export_csv(path, "Time[s]", [0.0, 0.1], columns)
            data = read_rows(path)
            assert data[2] == ["0.1", ""]
        finally:
            os.unlink(path)

    def test_time_epoch_formatted(self):
        path = write_temp_text_file("", encoding="utf-8-sig")
        try:
            dt = datetime(2026, 8, 13, 13, 52, 11)
            columns = [("F", "Col", [1.0])]
            write_export_csv(path, "Time", [dt.timestamp() + 0.5], columns)
            data = read_rows(path)
            assert data[1][0] == "2026/08/13 13:52:11.5"
        finally:
            os.unlink(path)

    def test_progress_callback(self):
        path = write_temp_text_file("", encoding="utf-8-sig")
        try:
            calls = []
            columns = [("F", "Col", list(range(5)))]
            write_export_csv(path, "Time[s]", [0.1, 0.2], columns,
                             progress_callback=lambda cur, total: calls.append((cur, total)))
            assert calls
            assert calls[-1] == (5, 5)
            assert all(cur <= 5 and total == 5 for cur, total in calls)
        finally:
            os.unlink(path)

    def test_no_time_column(self):
        path = write_temp_text_file("", encoding="utf-8-sig")
        try:
            columns = [("F", "Col", [1.0, 2.0])]
            rows, cols = write_export_csv(path, None, [], columns)
            assert (rows, cols) == (2, 1)
            data = read_rows(path)
            assert data[0] == ["Col"]
            assert data[2] == ["2.0"]
        finally:
            os.unlink(path)
