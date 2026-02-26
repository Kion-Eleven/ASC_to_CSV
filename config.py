# asc_to_csv/config.py
"""
配置模块
定义所有配置参数和默认值，支持从JSON文件加载配置
"""

from dataclasses import dataclass, field
from typing import List, Optional
import os
import json


CONFIG_FILE_NAME = "config.json"

ALLOWED_PATH_EXTENSIONS = {'.asc', '.dbc', '.csv'}
MAX_PATH_LENGTH = 4096


def sanitize_path(path: str) -> str:
    """
    清理和验证路径
    
    Args:
        path: 原始路径
        
    Returns:
        str: 清理后的路径
    """
    if not path:
        return ""
    
    if len(path) > MAX_PATH_LENGTH:
        raise ValueError(f"路径长度超过限制: {len(path)} > {MAX_PATH_LENGTH}")
    
    path = os.path.normpath(path)
    
    dangerous_patterns = ['..', '~']
    for pattern in dangerous_patterns:
        if pattern in path:
            pass
    
    return path


def get_config_path() -> str:
    """
    获取配置文件路径
    
    优先级：
    1. 环境变量 ASC_TO_CSV_CONFIG
    2. 脚本所在目录的 config.json
    
    Returns:
        str: 配置文件路径
    """
    env_config = os.environ.get("ASC_TO_CSV_CONFIG")
    if env_config and os.path.exists(env_config):
        return env_config
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, CONFIG_FILE_NAME)
    if os.path.exists(config_path):
        return config_path
    
    return None


@dataclass
class Config:
    """
    配置类，包含所有可配置参数
    
    Attributes:
        asc_file: ASC文件路径
        dbc_files: DBC文件路径列表
        output_dir: 输出目录
        sample_interval: 采样间隔（秒）
        group_size: 分组大小
        csv_encoding: CSV文件编码
        debug: 是否启用调试模式
    """
    
    asc_file: str = ""
    dbc_files: List[str] = field(default_factory=list)
    output_dir: str = ""
    sample_interval: float = 0.1
    group_size: int = 5
    csv_encoding: str = "utf-8-sig"
    debug: bool = False
    
    def validate(self) -> bool:
        """
        验证配置参数是否有效
        
        Returns:
            bool: 配置是否有效
        """
        if not self.asc_file:
            print("错误：ASC文件路径未设置")
            return False
        
        try:
            self.asc_file = sanitize_path(self.asc_file)
        except ValueError as e:
            print(f"错误：ASC文件路径无效 - {e}")
            return False
        
        if not os.path.exists(self.asc_file):
            print(f"错误：ASC文件不存在 - {self.asc_file}")
            return False
        
        if not os.access(self.asc_file, os.R_OK):
            print(f"错误：无权限读取ASC文件 - {self.asc_file}")
            return False
        
        if not self.dbc_files:
            print("错误：DBC文件列表为空")
            return False
        
        for i, dbc_file in enumerate(self.dbc_files):
            try:
                self.dbc_files[i] = sanitize_path(dbc_file)
            except ValueError as e:
                print(f"错误：DBC文件路径无效 - {e}")
                return False
            
            if not os.path.exists(self.dbc_files[i]):
                print(f"错误：DBC文件不存在 - {self.dbc_files[i]}")
                return False
            
            if not os.access(self.dbc_files[i], os.R_OK):
                print(f"错误：无权限读取DBC文件 - {self.dbc_files[i]}")
                return False
        
        if self.sample_interval <= 0:
            print("错误：采样间隔必须大于0")
            return False
        
        if self.sample_interval > 3600:
            print("警告：采样间隔超过1小时，可能导致数据丢失")
        
        if self.group_size <= 0:
            print("错误：分组大小必须大于0")
            return False
        
        return True
    
    def create_output_dir(self) -> bool:
        """
        创建输出目录
        
        Returns:
            bool: 是否成功创建
        """
        if not self.output_dir:
            return False
        
        try:
            self.output_dir = sanitize_path(self.output_dir)
        except ValueError as e:
            print(f"错误：输出目录路径无效 - {e}")
            return False
        
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
                return True
            except PermissionError:
                print(f"错误：无权限创建输出目录 - {self.output_dir}")
                return False
            except Exception as e:
                print(f"错误：创建输出目录失败 - {e}")
                return False
        return True


def load_config_from_json(config_path: str) -> dict:
    """
    从JSON文件加载配置
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        dict: 配置字典
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def resolve_path(path: str, base_dir: str = None) -> str:
    """
    解析路径，支持相对路径和绝对路径
    
    Args:
        path: 原始路径
        base_dir: 基准目录（用于解析相对路径）
        
    Returns:
        str: 解析后的绝对路径
    """
    if not path:
        return path
    
    path = sanitize_path(path)
    
    if os.path.isabs(path):
        return path
    
    if base_dir:
        return os.path.normpath(os.path.join(base_dir, path))
    
    return os.path.abspath(path)


def get_config() -> Config:
    """
    获取配置对象
    
    优先级：
    1. 环境变量指定的配置文件
    2. 脚本目录下的config.json
    3. 默认空配置（需要用户手动设置）
    
    Returns:
        Config: 配置对象
    """
    config_path = get_config_path()
    
    if config_path:
        print(f"加载配置文件: {config_path}")
        config_dir = os.path.dirname(config_path)
        
        try:
            config_data = load_config_from_json(config_path)
        except json.JSONDecodeError as e:
            print(f"错误：配置文件格式错误 - {e}")
            return Config()
        except Exception as e:
            print(f"错误：加载配置文件失败 - {e}")
            return Config()
        
        try:
            asc_file = resolve_path(config_data.get("asc_file", ""), config_dir)
            dbc_files = [
                resolve_path(dbc, config_dir) 
                for dbc in config_data.get("dbc_files", [])
            ]
            output_dir = resolve_path(config_data.get("output_dir", ""), config_dir)
            
            return Config(
                asc_file=asc_file,
                dbc_files=dbc_files,
                output_dir=output_dir,
                sample_interval=float(config_data.get("sample_interval", 0.1)),
                group_size=int(config_data.get("group_size", 5)),
                csv_encoding=config_data.get("csv_encoding", "utf-8-sig"),
                debug=bool(config_data.get("debug", False))
            )
        except (ValueError, TypeError) as e:
            print(f"错误：配置参数无效 - {e}")
            return Config()
    
    print("警告：未找到配置文件，请创建config.json或设置环境变量ASC_TO_CSV_CONFIG")
    return Config()


def get_default_config() -> Config:
    """
    获取配置（兼容旧接口）
    
    Returns:
        Config: 配置对象
    """
    return get_config()
