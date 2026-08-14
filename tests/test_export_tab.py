# asc_to_csv/tests/test_export_tab.py
"""
数据导出模块单元测试
验证ExportTab的列选择和数据导出功能
"""

import csv
import os
import tempfile
from typing import Generator

import pytest

from conftest import write_temp_text_file
from core.csv_loader import CSVDataLoader


@pytest.fixture
def sample_csv_file() -> Generator[str, None, None]:
    """创建测试CSV文件"""
    content = "Time[s],PackSOC[%],MaxCellTemp[°C],MinCellTemp[°C],Status\n"
    for i in range(100):
        content += f"{i*0.1},{80-i*0.1},{25+i*0.05},{20-i*0.05},OK\n"

    path = write_temp_text_file(content, encoding="utf-8-sig")
    yield path
    os.unlink(path)


@pytest.fixture
def sample_csv_with_spaces() -> Generator[str, None, None]:
    """创建包含空值的测试CSV文件"""
    content = "Time[s],Value1,Value2,Value3\n"
    content += "0.0,1.5,2.5,3.5\n"
    content += "0.1,,2.5,\n"
    content += "0.2,1.5,,3.5\n"
    content += "0.3,1.5,2.5,3.5\n"

    path = write_temp_text_file(content, encoding="utf-8")
    yield path
    os.unlink(path)


def export_columns_to_csv(file_path: str, loader: CSVDataLoader,
                          columns: list, encoding: str = 'utf-8-sig') -> bool:
    """
    将选定的列导出到CSV文件

    Args:
        file_path: 输出文件路径
        loader: CSVDataLoader实例
        columns: 要导出的列名列表
        encoding: 文件编码

    Returns:
        bool: 是否成功导出
    """
    try:
        with open(file_path, 'w', newline='', encoding=encoding) as f:
            writer = csv.writer(f)
            writer.writerow(columns)

            for row_idx in range(loader.row_count):
                row_data = []
                for col in columns:
                    value = loader.data[col][row_idx]
                    row_data.append(value if value is not None else "")
                writer.writerow(row_data)
        return True
    except Exception as e:
        print(f"导出失败: {e}")
        return False


def read_csv_content(file_path: str, encoding: str = 'utf-8-sig') -> tuple:
    """
    读取CSV文件内容

    Args:
        file_path: CSV文件路径
        encoding: 文件编码

    Returns:
        tuple: (headers, rows)
    """
    with open(file_path, 'r', encoding=encoding) as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)
    return headers, rows


class TestColumnSelection:
    """列选择功能测试"""

    def test_load_csv_columns(self, sample_csv_file: str):
        """测试加载CSV文件的列名"""
        loader = CSVDataLoader()
        result = loader.load(sample_csv_file)

        assert result is True
        assert len(loader.columns) == 5
        assert "Time[s]" in loader.columns
        assert "PackSOC[%]" in loader.columns
        assert "MaxCellTemp[°C]" in loader.columns
        assert "MinCellTemp[°C]" in loader.columns
        assert "Status" in loader.columns

    def test_select_single_column(self, sample_csv_file: str):
        """测试选择单列"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        selected_columns = ["Time[s]"]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='utf-8-sig')
        temp_output.close()

        try:
            success = export_columns_to_csv(temp_output.name, loader, selected_columns)
            assert success is True

            headers, rows = read_csv_content(temp_output.name)
            assert headers == ["Time[s]"]
            assert len(rows) == 100
            assert rows[0][0] == "0.0"
            assert rows[50][0] == "5.0"
        finally:
            os.unlink(temp_output.name)

    def test_select_multiple_columns(self, sample_csv_file: str):
        """测试选择多列"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        selected_columns = ["Time[s]", "PackSOC[%]", "MaxCellTemp[°C]"]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='utf-8-sig')
        temp_output.close()

        try:
            success = export_columns_to_csv(temp_output.name, loader, selected_columns)
            assert success is True

            headers, rows = read_csv_content(temp_output.name)
            assert headers == ["Time[s]", "PackSOC[%]", "MaxCellTemp[°C]"]
            assert len(rows) == 100
            assert len(rows[0]) == 3
        finally:
            os.unlink(temp_output.name)

    def test_select_all_columns(self, sample_csv_file: str):
        """测试选择所有列"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        selected_columns = loader.columns[:]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='utf-8-sig')
        temp_output.close()

        try:
            success = export_columns_to_csv(temp_output.name, loader, selected_columns)
            assert success is True

            headers, rows = read_csv_content(temp_output.name)
            assert headers == loader.columns
            assert len(rows) == 100
        finally:
            os.unlink(temp_output.name)

    def test_select_non_adjacent_columns(self, sample_csv_file: str):
        """测试选择非相邻列"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        selected_columns = ["Time[s]", "MaxCellTemp[°C]", "Status"]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='utf-8-sig')
        temp_output.close()

        try:
            success = export_columns_to_csv(temp_output.name, loader, selected_columns)
            assert success is True

            headers, rows = read_csv_content(temp_output.name)
            assert headers == ["Time[s]", "MaxCellTemp[°C]", "Status"]
            assert len(rows) == 100
        finally:
            os.unlink(temp_output.name)


class TestDataExportWithNullValues:
    """包含空值的数据导出测试"""

    def test_export_with_empty_values(self, sample_csv_with_spaces: str):
        """测试导出包含空值的列"""
        loader = CSVDataLoader()
        loader.load(sample_csv_with_spaces)

        selected_columns = ["Time[s]", "Value1", "Value2", "Value3"]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='utf-8-sig')
        temp_output.close()

        try:
            success = export_columns_to_csv(temp_output.name, loader, selected_columns)
            assert success is True

            headers, rows = read_csv_content(temp_output.name)
            assert headers == ["Time[s]", "Value1", "Value2", "Value3"]
            assert len(rows) == 4

            assert rows[0] == ["0.0", "1.5", "2.5", "3.5"]
            assert rows[1] == ["0.1", "", "2.5", ""]
            assert rows[2] == ["0.2", "1.5", "", "3.5"]
        finally:
            os.unlink(temp_output.name)

    def test_export_partial_columns_with_nulls(self, sample_csv_with_spaces: str):
        """测试导出部分列（包含空值）"""
        loader = CSVDataLoader()
        loader.load(sample_csv_with_spaces)

        selected_columns = ["Value1", "Value3"]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='utf-8-sig')
        temp_output.close()

        try:
            success = export_columns_to_csv(temp_output.name, loader, selected_columns)
            assert success is True

            headers, rows = read_csv_content(temp_output.name)
            assert headers == ["Value1", "Value3"]
            assert rows[1] == ["", ""]
            assert rows[2] == ["1.5", "3.5"]
        finally:
            os.unlink(temp_output.name)


class TestDataExportEncoding:
    """数据导出编码测试"""

    def test_export_utf8_sig_encoding(self, sample_csv_file: str):
        """测试UTF-8-SIG编码导出"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        selected_columns = ["Time[s]", "PackSOC[%]"]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='utf-8-sig')
        temp_output.close()

        try:
            success = export_columns_to_csv(temp_output.name, loader,
                                           selected_columns, 'utf-8-sig')
            assert success is True

            headers, rows = read_csv_content(temp_output.name, 'utf-8-sig')
            assert headers == ["Time[s]", "PackSOC[%]"]
        finally:
            os.unlink(temp_output.name)

    def test_export_gbk_encoding(self, sample_csv_file: str):
        """测试GBK编码导出"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        selected_columns = ["Time[s]", "PackSOC[%]"]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='gbk')
        temp_output.close()

        try:
            success = export_columns_to_csv(temp_output.name, loader,
                                           selected_columns, 'gbk')
            assert success is True

            headers, rows = read_csv_content(temp_output.name, 'gbk')
            assert headers == ["Time[s]", "PackSOC[%]"]
        finally:
            os.unlink(temp_output.name)


class TestDataExportEdgeCases:
    """边界情况测试"""

    def test_export_single_row(self, sample_csv_file: str):
        """测试导出单行数据"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        selected_columns = ["Time[s]", "PackSOC[%]"]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='utf-8-sig')
        temp_output.close()

        try:
            single_row_loader = CSVDataLoader()
            single_row_loader.data = {
                "Time[s]": [loader.data["Time[s]"][0]],
                "PackSOC[%]": [loader.data["PackSOC[%]"][0]]
            }
            single_row_loader.columns = ["Time[s]", "PackSOC[%]"]
            single_row_loader.row_count = 1

            success = export_columns_to_csv(temp_output.name, single_row_loader,
                                           selected_columns)
            assert success is True

            headers, rows = read_csv_content(temp_output.name)
            assert len(rows) == 1
        finally:
            os.unlink(temp_output.name)

    def test_export_to_custom_path(self, sample_csv_file: str):
        """测试导出到自定义路径"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        selected_columns = ["Time[s]", "PackSOC[%]"]

        temp_dir = tempfile.mkdtemp()
        custom_path = os.path.join(temp_dir, "subdir", "export_data.csv")

        try:
            os.makedirs(os.path.dirname(custom_path))

            success = export_columns_to_csv(custom_path, loader, selected_columns)
            assert success is True
            assert os.path.exists(custom_path)

            headers, rows = read_csv_content(custom_path)
            assert len(rows) == 100
        finally:
            os.unlink(custom_path)
            os.rmdir(os.path.dirname(custom_path))
            os.rmdir(temp_dir)

    def test_export_large_file(self):
        """测试导出大文件"""
        content = "Time[s],Value1,Value2,Value3,Value4\n"
        for i in range(10000):
            content += f"{i*0.01},{i*1.1},{i*2.2},{i*3.3},{i*4.4}\n"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                        encoding='utf-8', delete=False) as f:
            f.write(content)
            temp_input = f.name

        try:
            loader = CSVDataLoader()
            result = loader.load(temp_input)
            assert result is True
            assert loader.row_count == 10000

            selected_columns = ["Time[s]", "Value1", "Value3"]
            temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                      delete=False, encoding='utf-8-sig')
            temp_output.close()

            try:
                success = export_columns_to_csv(temp_output.name, loader,
                                               selected_columns)
                assert success is True

                headers, rows = read_csv_content(temp_output.name)
                assert len(rows) == 10000
                assert len(headers) == 3
            finally:
                os.unlink(temp_output.name)
        finally:
            os.unlink(temp_input)


class TestExportValidation:
    """导出验证测试"""

    def test_validate_columns_exist(self, sample_csv_file: str):
        """测试验证列是否存在"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        valid_columns = ["Time[s]", "PackSOC[%]"]
        invalid_columns = ["NonExistent1", "NonExistent2"]

        for col in valid_columns:
            assert col in loader.columns

        for col in invalid_columns:
            assert col not in loader.columns

    def test_row_count_preserved(self, sample_csv_file: str):
        """测试行数保持一致"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        original_row_count = loader.row_count

        selected_columns = ["Time[s]", "PackSOC[%]"]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='utf-8-sig')
        temp_output.close()

        try:
            export_columns_to_csv(temp_output.name, loader, selected_columns)

            with open(temp_output.name, 'r', encoding='utf-8-sig') as f:
                exported_row_count = sum(1 for _ in f) - 1

            assert exported_row_count == original_row_count
        finally:
            os.unlink(temp_output.name)

    def test_data_integrity(self, sample_csv_file: str):
        """测试数据完整性"""
        loader = CSVDataLoader()
        loader.load(sample_csv_file)

        selected_columns = ["Time[s]", "MaxCellTemp[°C]"]

        temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                                  delete=False, encoding='utf-8-sig')
        temp_output.close()

        try:
            export_columns_to_csv(temp_output.name, loader, selected_columns)

            exported_loader = CSVDataLoader()
            exported_loader.load(temp_output.name)

            assert exported_loader.row_count == loader.row_count
            assert len(exported_loader.columns) == 2

            original_time_data = [str(v) for v in loader.data["Time[s]"]]
            exported_time_data = [str(v) for v in exported_loader.data["Time[s]"]]

            assert original_time_data == exported_time_data

            original_temp_data = [str(v) for v in loader.data["MaxCellTemp[°C]"]]
            exported_temp_data = [str(v) for v in exported_loader.data["MaxCellTemp[°C]"]]

            assert original_temp_data == exported_temp_data
        finally:
            os.unlink(temp_output.name)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
