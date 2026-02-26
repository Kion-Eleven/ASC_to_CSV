# asc_to_csv/dbc_loader.py
"""
DBC文件加载模块
负责加载和解析DBC文件
"""

import os
from typing import Dict, Any
import cantools


class DBCLoader:
    """
    DBC文件加载器
    
    负责加载DBC文件并创建消息映射和信号信息
    
    Attributes:
        message_map: 消息ID到消息对象的映射
        signal_info: 信号名称到信号信息的映射
    """
    
    def __init__(self):
        """初始化DBC加载器"""
        self.message_map: Dict[int, Dict[str, Any]] = {}
        self.signal_info: Dict[str, Dict[str, str]] = {}
    
    def load(self, dbc_files: list) -> bool:
        """
        加载DBC文件列表
        
        Args:
            dbc_files: DBC文件路径列表
            
        Returns:
            bool: 是否成功加载所有文件
        """
        for dbc_file in dbc_files:
            if not os.path.exists(dbc_file):
                print(f"错误：DBC文件不存在 - {dbc_file}")
                return False
            
            if not self._load_single_dbc(dbc_file):
                return False
        
        return True
    
    def _load_single_dbc(self, dbc_file: str) -> bool:
        """
        加载单个DBC文件
        
        Args:
            dbc_file: DBC文件路径
            
        Returns:
            bool: 是否成功加载
        """
        try:
            dbc_name = os.path.basename(dbc_file)
            db = cantools.database.load_file(dbc_file, strict=False)
            
            for msg in db.messages:
                # 存储消息对象
                self.message_map[msg.frame_id] = {
                    'message': msg,
                    'dbc_name': dbc_name
                }
                
                # 存储信号信息
                for signal in msg.signals:
                    full_name = f"{dbc_name}::{msg.name}::{signal.name}"
                    self.signal_info[full_name] = {
                        'unit': signal.unit if signal.unit else '',
                        'message': msg.name,
                        'dbc': dbc_name
                    }
            
            print(f"  已加载DBC: {dbc_file} - 消息数: {len(db.messages)}")
            return True
            
        except Exception as e:
            print(f"  加载DBC文件失败: {dbc_file} - 错误: {e}")
            return False
    
    def get_message_count(self) -> int:
        """获取消息总数"""
        return len(self.message_map)
    
    def get_signal_count(self) -> int:
        """获取信号总数"""
        return len(self.signal_info)