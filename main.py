# asc_to_csv/main.py
"""
程序入口点
协调各模块完成ASC到CSV的转换
"""

from config import Config, get_default_config
from dbc_loader import DBCLoader
from asc_parser import ASCParser
from data_processor import DataProcessor
from csv_writer import CSVWriter


class ASCToCSVConverter:
    """
    ASC到CSV转换器
    
    协调各模块完成完整的转换流程
    """
    
    def __init__(self, config: Config = None):
        """
        初始化转换器
        
        Args:
            config: 配置对象，如果为None则使用默认配置
        """
        self.config = config or get_default_config()
        self.dbc_loader = DBCLoader()
        self.asc_parser = None
        self.data_processor = DataProcessor()
        self.csv_writer = None
    
    def run(self) -> bool:
        """
        运行转换流程
        
        Returns:
            bool: 是否成功完成转换
        """
        # 打印配置信息
        self._print_config()
        
        # 验证配置
        if not self.config.validate():
            return False
        
        # 创建输出目录
        self.config.create_output_dir()
        
        # 加载DBC文件
        print("\n正在加载DBC文件...")
        if not self.dbc_loader.load(self.config.dbc_files):
            return False
        
        print(f"\n总消息定义数: {self.dbc_loader.get_message_count()}")
        print(f"总信号定义数: {self.dbc_loader.get_signal_count()}")
        
        # 解析ASC文件
        print("\n正在解析ASC文件...")
        self.asc_parser = ASCParser(
            sample_interval=self.config.sample_interval,
            debug=self.config.debug
        )
        if not self.asc_parser.parse(self.config.asc_file, self.dbc_loader.message_map):
            return False
        
        # 打印解析统计
        original_count, sampled_count, signal_count = self.asc_parser.get_statistics()
        print(f"\n解析完成：")
        print(f"  原始数据点数: {original_count}")
        print(f"  采样后时间点数: {sampled_count}")
        print(f"  实际信号数: {signal_count}")
        
        # 处理数据
        print("\n正在处理数据...")
        self.data_processor.aggregate(self.asc_parser.sampled_data)
        self.data_processor.classify_signals(self.asc_parser.found_signals)
        
        # 打印分组结果
        print("\n分组结果：")
        for group_name, count in self.data_processor.get_group_statistics().items():
            print(f"  {group_name}: {count}个信号")
        
        # 写入CSV文件
        print("\n正在创建CSV文件...")
        self.csv_writer = CSVWriter(
            output_dir=self.config.output_dir,
            encoding=self.config.csv_encoding,
            group_size=self.config.group_size
        )
        
        created_files = self.csv_writer.write_all(
            sorted_groups=self.data_processor.sorted_groups,
            classified_signals=self.data_processor.classified_signals,
            sorted_timestamps=self.data_processor.get_sorted_timestamps(),
            aggregated_data=self.data_processor.aggregated_data,
            signal_info=self.dbc_loader.signal_info,
            statistics={
                'original_count': original_count,
                'sampled_count': sampled_count,
                'signal_count': signal_count
            }
        )
        
        # 打印完成信息
        self._print_summary(created_files)
        
        return True
    
    def _print_config(self) -> None:
        """打印配置信息"""
        print("开始转换...")
        print(f"分组规则: 按BatP+数字模式分组")
        print(f"采样间隔: {self.config.sample_interval}秒")
        print(f"分组大小: {self.config.group_size}个数据/组")
        print(f"输出格式: CSV文件")
        print(f"文件编码: {self.config.csv_encoding}")
    
    def _print_summary(self, created_files: list) -> None:
        """
        打印转换摘要
        
        Args:
            created_files: 创建的文件列表
        """
        print(f"\n✅ 转换完成！")
        print(f"输出目录: {self.config.output_dir}")
        print(f"生成文件数: {len(created_files)}")
        
        print(f"\n生成的文件：")
        print(f"  1. Summary.csv - 汇总报告")
        print(f"  2. All_Signals.csv - 所有信号总览")
        for i, group_name in enumerate(self.data_processor.sorted_groups, 3):
            signal_count = len(self.data_processor.classified_signals[group_name])
            print(f"  {i}. {group_name}.csv - {signal_count}个信号")


def main():
    """主函数"""
    # 使用默认配置
    config = get_default_config()
    
    # 创建转换器并运行
    converter = ASCToCSVConverter(config)
    success = converter.run()
    
    if not success:
        print("\n❌ 转换失败！")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())