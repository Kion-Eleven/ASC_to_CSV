# asc_to_csv/tests/test_csv_loader.py
"""
CSV数据加载器单元测试
验证优化后的功能正确性和性能提升
"""

import os
import time
import tracemalloc
from typing import Generator

import pytest

from conftest import write_temp_text_file
from core.csv_loader import CSVDataLoader, MULTI_SELECT_COLUMNS


@pytest.fixture
def sample_csv_utf8() -> Generator[str, None, None]:
    """创建UTF-8编码的测试CSV文件"""
    content = "Time[s],PackSOC[%],MaxCellTemp[°C],Status\n"
    for i in range(100):
        content += f"{i*0.1},{80-i*0.1},{25+i*0.05},OK\n"

    path = write_temp_text_file(content, encoding="utf-8-sig")
    yield path
    os.unlink(path)


@pytest.fixture
def sample_csv_gbk() -> Generator[str, None, None]:
    """创建GBK编码的测试CSV文件"""
    content = "时间[s],电池SOC[%],最高温度[°C],状态\n"
    for i in range(100):
        content += f"{i*0.1},{80-i*0.1},{25+i*0.05},正常\n"

    path = write_temp_text_file(content, encoding="gbk")
    yield path
    os.unlink(path)


@pytest.fixture
def large_csv_file() -> Generator[str, None, None]:
    """创建大型测试CSV文件（用于性能测试）"""
    content = "Time[s],Value1,Value2,Value3,Value4,Value5\n"
    for i in range(10000):
        content += f"{i*0.01},{i*1.5},{i*2.5},{i*3.5},{i*4.5},{i*5.5}\n"

    path = write_temp_text_file(content, encoding="utf-8")
    yield path
    os.unlink(path)


@pytest.fixture
def csv_with_special_values() -> Generator[str, None, None]:
    """创建包含特殊值的测试CSV文件"""
    content = """Time[s],Value,Text
0.0,1.5,text1
0.1,,empty_value
0.2,3.5,
0.3,4.5e-2,scientific
0.4,-10,negative
0.5,0,zero
"""
    path = write_temp_text_file(content, encoding="utf-8")
    yield path
    os.unlink(path)


class TestCSVDataLoaderBasic:
    """基础功能测试"""
    
    def test_load_utf8_file(self, sample_csv_utf8: str):
        """测试加载UTF-8编码文件"""
        loader = CSVDataLoader()
        result = loader.load(sample_csv_utf8)
        
        assert result == True
        assert loader.row_count == 100
        assert len(loader.columns) == 4
        assert "Time[s]" in loader.columns
        assert loader.get_encoding() == 'utf-8-sig'
    
    def test_load_gbk_file(self, sample_csv_gbk: str):
        """测试加载GBK编码文件"""
        loader = CSVDataLoader()
        result = loader.load(sample_csv_gbk)
        
        assert result == True
        assert loader.row_count == 100
        assert loader.get_encoding() == 'gbk'
    
    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        loader = CSVDataLoader()
        result = loader.load("/nonexistent/path/file.csv")
        
        assert result == False
    
    def test_load_with_explicit_encoding(self, sample_csv_utf8: str):
        """测试使用显式编码加载文件"""
        loader = CSVDataLoader()
        result = loader.load(sample_csv_utf8, encoding='utf-8-sig')
        
        assert result == True
        assert loader.get_encoding() == 'utf-8-sig'


class TestCSVDataLoaderTypeInference:
    """类型推断测试"""
    
    def test_numeric_type_inference(self, sample_csv_utf8: str):
        """测试数值类型推断"""
        loader = CSVDataLoader()
        loader.load(sample_csv_utf8)
        
        time_data = loader.get_column_data("Time[s]")
        soc_data = loader.get_column_data("PackSOC[%]")
        
        assert all(isinstance(v, (int, float)) for v in time_data)
        assert all(isinstance(v, (int, float)) for v in soc_data)
    
    def test_string_type_inference(self, sample_csv_utf8: str):
        """测试字符串类型推断"""
        loader = CSVDataLoader()
        loader.load(sample_csv_utf8)
        
        status_data = loader.get_column_data("Status")
        
        assert all(isinstance(v, str) for v in status_data)
        assert all(v == "OK" for v in status_data)
    
    def test_null_value_handling(self, csv_with_special_values: str):
        """测试空值处理"""
        loader = CSVDataLoader()
        loader.load(csv_with_special_values)
        
        value_data = loader.get_column_data("Value")
        
        assert value_data[0] == 1.5
        assert value_data[1] is None
        assert value_data[2] == 3.5
    
    def test_scientific_notation(self, csv_with_special_values: str):
        """测试科学计数法"""
        loader = CSVDataLoader()
        loader.load(csv_with_special_values)
        
        value_data = loader.get_column_data("Value")
        
        assert value_data[3] == pytest.approx(4.5e-2, rel=1e-9)
    
    def test_negative_numbers(self, csv_with_special_values: str):
        """测试负数处理"""
        loader = CSVDataLoader()
        loader.load(csv_with_special_values)
        
        value_data = loader.get_column_data("Value")
        
        assert value_data[4] == -10
        assert value_data[5] == 0


class TestCSVDataLoaderColumns:
    """列操作测试"""
    
    def test_get_numeric_columns(self, sample_csv_utf8: str):
        """测试获取数值列"""
        loader = CSVDataLoader()
        loader.load(sample_csv_utf8)
        
        numeric_cols = loader.get_numeric_columns()
        
        assert "PackSOC[%]" in numeric_cols
        assert "MaxCellTemp[°C]" in numeric_cols
        assert "Status" not in numeric_cols
    
    def test_get_time_column(self, sample_csv_utf8: str):
        """测试获取时间列"""
        loader = CSVDataLoader()
        loader.load(sample_csv_utf8)
        
        time_col = loader.get_time_column()
        
        assert time_col == "Time[s]"
    
    def test_get_multi_select_columns(self, sample_csv_utf8: str):
        """测试获取多选列"""
        loader = CSVDataLoader()
        loader.load(sample_csv_utf8)
        
        multi_cols = loader.get_multi_select_columns()
        
        assert "PackSOC[%]" in multi_cols
        assert "MaxCellTemp[°C]" in multi_cols


class TestCSVDataLoaderStatistics:
    """统计功能测试"""
    
    def test_get_statistics(self, sample_csv_utf8: str):
        """测试获取统计信息"""
        loader = CSVDataLoader()
        loader.load(sample_csv_utf8)
        
        stats = loader.get_statistics("PackSOC[%]")
        
        assert stats['type'] == 'numeric'
        assert stats['count'] == 100
        assert stats['min'] == pytest.approx(70.1, rel=1e-6)
        assert stats['max'] == pytest.approx(80.0, rel=1e-6)
        assert 'mean' in stats
    
    def test_get_statistics_nonexistent_column(self, sample_csv_utf8: str):
        """测试获取不存在列的统计信息"""
        loader = CSVDataLoader()
        loader.load(sample_csv_utf8)
        
        stats = loader.get_statistics("NonexistentColumn")
        
        assert stats == {}


class TestCSVDataLoaderChunkLoading:
    """分块加载测试"""
    
    def test_chunk_loading_basic(self, large_csv_file: str):
        """测试基本分块加载"""
        loader = CSVDataLoader()
        result = loader.load(large_csv_file, chunk_size=1000)
        
        assert result == True
        assert loader.row_count == 1000
        assert loader.is_chunked() == True
        assert loader.has_more_data() == True
    
    def test_load_more(self, large_csv_file: str):
        """测试加载更多数据"""
        loader = CSVDataLoader()
        loader.load(large_csv_file, chunk_size=1000)
        
        initial_count = loader.row_count
        result = loader.load_more()
        
        assert result == True
        assert loader.row_count > initial_count
    
    def test_get_load_progress(self, large_csv_file: str):
        """测试获取加载进度"""
        loader = CSVDataLoader()
        loader.load(large_csv_file, chunk_size=1000)
        
        loaded, total = loader.get_load_progress()
        
        assert loaded == 1000
        assert total >= 10000
    
    def test_chunk_loading_complete(self, large_csv_file: str):
        """测试分块加载完成"""
        loader = CSVDataLoader()
        loader.load(large_csv_file, chunk_size=5000)
        
        while loader.has_more_data():
            loader.load_more()
        
        assert loader.row_count == 10000
        assert loader.has_more_data() == False


class TestCSVDataLoaderFilter:
    """数据过滤测试"""
    
    def test_filter_by_time(self, sample_csv_utf8: str):
        """测试按时间过滤"""
        loader = CSVDataLoader()
        loader.load(sample_csv_utf8)
        
        filtered = loader.filter_by_time(2.0, 5.0)
        
        assert filtered.row_count == 31
        time_data = filtered.get_column_data("Time[s]")
        assert min(time_data) == pytest.approx(2.0, rel=1e-6)
        assert max(time_data) == pytest.approx(5.0, rel=1e-6)


class TestCSVDataLoaderPerformance:
    """性能测试"""
    
    def test_loading_performance(self, large_csv_file: str):
        """测试加载性能"""
        loader = CSVDataLoader()
        
        start_time = time.time()
        loader.load(large_csv_file)
        elapsed = time.time() - start_time
        
        print(f"\n加载10000行数据耗时: {elapsed:.3f}秒")
        assert elapsed < 1.0
    
    def test_memory_usage_chunked(self, large_csv_file: str):
        """测试分块加载内存使用"""
        tracemalloc.start()
        
        loader = CSVDataLoader()
        loader.load(large_csv_file, chunk_size=1000)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"\n分块加载内存使用: 当前={current/1024:.1f}KB, 峰值={peak/1024:.1f}KB")
        assert peak < 1024 * 1024
    
    def test_memory_usage_full(self, large_csv_file: str):
        """测试完整加载内存使用"""
        tracemalloc.start()
        
        loader = CSVDataLoader()
        loader.load(large_csv_file)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"\n完整加载内存使用: 当前={current/1024:.1f}KB, 峰值={peak/1024:.1f}KB")


class TestCSVDataLoaderClear:
    """清理功能测试"""
    
    def test_clear(self, sample_csv_utf8: str):
        """测试清空数据"""
        loader = CSVDataLoader()
        loader.load(sample_csv_utf8)
        
        assert loader.row_count > 0
        
        loader.clear()
        
        assert loader.row_count == 0
        assert len(loader.columns) == 0
        assert len(loader.data) == 0


class TestCSVDataLoaderEdgeCases:
    """边界情况测试"""
    
    def test_empty_file(self):
        """测试空文件"""
        empty_path = write_temp_text_file("", encoding="utf-8")
        loader = CSVDataLoader()
        result = loader.load(empty_path)
        os.unlink(empty_path)
        assert result is False

    def test_header_only(self):
        """测试只有表头的文件"""
        header_path = write_temp_text_file("col1,col2,col3\n", encoding="utf-8")
        loader = CSVDataLoader()
        result = loader.load(header_path)
        os.unlink(header_path)
        assert result is True
        assert loader.row_count == 0
        assert len(loader.columns) == 3

    def test_irregular_rows(self):
        """测试不规则行"""
        content = "col1,col2,col3\n1,2,3\n4,5\n6,7,8,9\n10,11,12\n"
        irregular_path = write_temp_text_file(content, encoding="utf-8")
        loader = CSVDataLoader()
        result = loader.load(irregular_path)
        os.unlink(irregular_path)
        assert result is True
        assert loader.row_count == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
