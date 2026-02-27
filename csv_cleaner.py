# asc_to_csv/csv_cleaner.py
"""
CSV文件清理模块
负责移除CSV文件中的空白行
"""

import os
import csv
from typing import List, Tuple


class CSVCleaner:
    """
    CSV文件清理器
    
    负责移除CSV文件中的空白行，保持数据完整性
    """
    
    @staticmethod
    def is_empty_row(row: List[str]) -> bool:
        """
        判断一行是否为空白行
        
        空白行定义：
        - 完全为空的列表 []
        - 所有字段都为空字符串 ['', '', '']
        - 所有字段都只包含空白字符 [' ', '  ', '']
        
        Args:
            row: CSV行数据
            
        Returns:
            bool: 是否为空白行
        """
        if not row:
            return True
        return all(not cell.strip() for cell in row)
    
    def clean_file(self, input_file: str, output_file: str = None) -> Tuple[int, int, int]:
        """
        清理单个CSV文件中的空白行
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径（默认覆盖原文件）
            
        Returns:
            Tuple[int, int, int]: (原始行数, 清理后行数, 移除的空白行数)
        """
        if output_file is None:
            output_file = input_file
        
        original_count = 0
        cleaned_count = 0
        removed_count = 0
        cleaned_rows = []
        
        with open(input_file, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                original_count += 1
                if self.is_empty_row(row):
                    removed_count += 1
                else:
                    cleaned_rows.append(row)
                    cleaned_count += 1
        
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerows(cleaned_rows)
        
        return original_count, cleaned_count, removed_count
    
    def clean_directory(self, directory: str, pattern: str = "*.csv") -> List[dict]:
        """
        清理目录下所有CSV文件中的空白行
        
        Args:
            directory: 目录路径
            pattern: 文件匹配模式
            
        Returns:
            List[dict]: 每个文件的处理结果列表
        """
        import glob
        
        results = []
        csv_files = glob.glob(os.path.join(directory, pattern))
        
        for csv_file in csv_files:
            try:
                original, cleaned, removed = self.clean_file(csv_file)
                results.append({
                    'file': csv_file,
                    'original_rows': original,
                    'cleaned_rows': cleaned,
                    'removed_rows': removed,
                    'success': True
                })
            except Exception as e:
                results.append({
                    'file': csv_file,
                    'error': str(e),
                    'success': False
                })
        
        return results
    
    def print_clean_report(self, results: List[dict]):
        """
        打印清理报告
        
        Args:
            results: 清理结果列表
        """
        print("\n" + "=" * 60)
        print("CSV文件空白行清理报告")
        print("=" * 60)
        
        total_original = 0
        total_cleaned = 0
        total_removed = 0
        
        for result in results:
            if result['success']:
                filename = os.path.basename(result['file'])
                print(f"\n文件: {filename}")
                print(f"  原始行数: {result['original_rows']}")
                print(f"  清理后行数: {result['cleaned_rows']}")
                print(f"  移除空白行: {result['removed_rows']}")
                total_original += result['original_rows']
                total_cleaned += result['cleaned_rows']
                total_removed += result['removed_rows']
            else:
                print(f"\n文件: {result['file']}")
                print(f"  处理失败: {result['error']}")
        
        print("\n" + "-" * 60)
        print("汇总统计:")
        print(f"  处理文件数: {len([r for r in results if r['success']])}")
        print(f"  总原始行数: {total_original}")
        print(f"  总清理后行数: {total_cleaned}")
        print(f"  总移除空白行: {total_removed}")
        print("=" * 60)


def clean_csv_files(output_dir: str):
    """
    清理输出目录中所有CSV文件的空白行
    
    Args:
        output_dir: 输出目录路径
    """
    cleaner = CSVCleaner()
    results = cleaner.clean_directory(output_dir)
    cleaner.print_clean_report(results)
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        target_dir = "."
    
    clean_csv_files(target_dir)
