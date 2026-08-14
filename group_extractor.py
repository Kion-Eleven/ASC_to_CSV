# asc_to_csv/group_extractor.py
"""
信号分组提取器模块

本模块实现了基于信号命名规则的动态分组功能。通过正则表达式匹配，
从信号名称中提取组标识符，为每个唯一组创建独立的CSV文件。

分组规则：
    - BatP + 数字：BatP1, BatP10, BatP28 等
    - BatP + 1-2个字母：BatPS, BatPQ, BatPL, BatPR 等
    - 不符合以上规则的信号归入 Others 组

使用示例：
    >>> from group_extractor import GroupExtractor
    >>> extractor = GroupExtractor()
    >>> group = extractor.extract_from_signal_name('test.dbc::BatP3_Msg::signal')
    >>> print(group)  # 输出: BATP3
    >>> 
    >>> # 批量分组
    >>> signals = ['test.dbc::BatP1_Msg::sig1', 'test.dbc::FMC_Msg::sig2']
    >>> classified = extractor.classify_signals(signals)
    >>> print(classified)  # {'BATP1': ['test.dbc::BatP1_Msg::sig1'], 'Others': ['test.dbc::FMC_Msg::sig2']}
"""

import re
from typing import List, Set, Dict, Optional, Tuple
from enum import Enum


class ExtractionStrategy(Enum):
    """分组提取策略枚举"""
    AUTO_DISCOVER = "auto_discover"
    MESSAGE_PREFIX = "message_prefix"
    SIGNAL_PREFIX = "signal_prefix"
    BATP_PATTERN = "batp_pattern"
    CUSTOM_PATTERN = "custom_pattern"


class GroupExtractor:
    """
    信号分组提取器
    
    根据信号名称中的特定模式提取组标识符，支持大小写不敏感匹配。
    所有提取的组名称统一转换为大写格式，确保分组一致性。
    
    Attributes:
        discovered_groups (Set[str]): 已发现的组名称集合
        group_mapping (Dict[str, Optional[str]]): 信号名称到组名称的映射缓存
    
    分组规则详情：
        1. 数字组：匹配 "BatP" 后跟一个或多个数字
           - 示例：BatP1, BatP10, BatP28
           - 输出：BATP1, BATP10, BATP28
        
        2. 字母组：匹配 "BatP" 后跟1-2个大写字母
           - 示例：BatPS, BatPQ, BatPL, BatPR
           - 输出：BATPS, BATPQ, BATPL, BATPR
        
        3. Others组：不符合以上规则的信号
           - 示例：FMC_signal, HVMS_signal, BMS_signal
           - 输出：归入 Others 组
    
    边界条件处理：
        - 空信号名称：返回 None
        - 无效字符：替换为下划线
        - 超长名称：截断至200字符
    """
    
    # 正则表达式：匹配有效的组名称模式
    # (?i) - 大小写不敏感
    # (BatP\d+|BatP[A-Z]{1,2}) - 匹配 BatP+数字 或 BatP+1-2个字母
    # (?=_|$|[^a-zA-Z0-9]) - 正向预查：后面必须是下划线、字符串结尾或非字母数字字符
    VALID_GROUP_PATTERN = re.compile(r'(?i)(BatP\d+|BatP[A-Z]{1,2})(?=_|$|[^a-zA-Z0-9])')
    
    # 文件名中的无效字符（Windows文件系统限制）
    INVALID_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

    def __init__(self, strategy: ExtractionStrategy = ExtractionStrategy.AUTO_DISCOVER):
        """
        初始化分组提取器

        Args:
            strategy: 分组提取策略，默认使用AUTO_DISCOVER
        """
        self.strategy = strategy
        self.discovered_groups: Set[str] = set()
        self.group_mapping: Dict[str, Optional[str]] = {}
        self._custom_patterns: List[re.Pattern] = []

    def add_custom_pattern(self, pattern: str) -> None:
        """Register a custom regex pattern (first capture group = group name)."""
        self._custom_patterns.append(re.compile(pattern, re.IGNORECASE))

    def extract_from_signal_name(self, signal_name: str) -> Optional[str]:
        """
        从信号名称中提取组名称
        
        根据预定义的正则表达式模式，从完整的信号名称中提取组标识符。
        提取结果会被缓存以提高后续查询效率。
        
        Args:
            signal_name: 完整的信号名称
                格式通常为：{DBC文件名}::{消息名称}::{信号名称}
                示例：'800V_BMS.dbc::BatP3_BMS_CellVolt::P3_AvgCellVlt'
        
        Returns:
            Optional[str]: 提取的组名称（统一大写格式）
                - 成功匹配：返回组名称，如 'BATP3', 'BATPS'
                - 匹配失败：返回 None（表示应归入 Others 组）
        
        Examples:
            >>> extractor = GroupExtractor()
            >>> extractor.extract_from_signal_name('test.dbc::BatP1_Msg::signal')
            'BATP1'
            >>> extractor.extract_from_signal_name('test.dbc::BatP10_Msg::signal')
            'BATP10'
            >>> extractor.extract_from_signal_name('test.dbc::FMC_Msg::signal')
            None
        
        Note:
            - 匹配结果会被缓存，相同信号名称的后续查询直接返回缓存结果
            - 组名称统一转换为大写，确保 'BatP3' 和 'BATP3' 归入同一组
        """
        if not signal_name:
            return None
        
        if signal_name in self.group_mapping:
            return self.group_mapping[signal_name]

        if self.strategy == ExtractionStrategy.CUSTOM_PATTERN:
            group_name = self._extract_custom_pattern(signal_name)
        elif self.strategy == ExtractionStrategy.SIGNAL_PREFIX:
            group_name = self._extract_signal_prefix(signal_name)
        else:
            group_name = self._extract_batp_pattern(signal_name)

        self.group_mapping[signal_name] = group_name
        if group_name:
            self.discovered_groups.add(group_name)
        return group_name

    def _extract_batp_pattern(self, signal_name: str) -> Optional[str]:
        match = self.VALID_GROUP_PATTERN.search(signal_name)
        if not match:
            return None
        return self._sanitize_group_name(match.group(1).upper())

    def _extract_custom_pattern(self, signal_name: str) -> Optional[str]:
        for pattern in self._custom_patterns:
            match = pattern.search(signal_name)
            if match:
                return self._sanitize_group_name(match.group(1).upper())
        return None

    def _extract_signal_prefix(self, signal_name: str) -> Optional[str]:
        parts = signal_name.split("::")
        if len(parts) < 3:
            return None
        signal_part = parts[-1].strip()
        match = re.match(r"^([A-Za-z]+\d*)", signal_part)
        if not match:
            return None
        return self._sanitize_group_name(match.group(1).upper())
    
    def _sanitize_group_name(self, group_name: str) -> str:
        """
        清理组名称，确保可作为有效的文件名使用
        
        处理以下情况：
        1. 移除文件系统不支持的特殊字符
        2. 移除首尾的空格和点
        3. 处理空字符串情况
        4. 限制文件名长度
        
        Args:
            group_name: 原始组名称
        
        Returns:
            str: 清理后的安全文件名
        
        Examples:
            >>> extractor = GroupExtractor()
            >>> extractor._sanitize_group_name('BATP3')
            'BATP3'
            >>> extractor._sanitize_group_name('BATP<3>')
            'BATP_3_'
            >>> extractor._sanitize_group_name('')
            'Unknown'
        """
        # 移除无效字符
        cleaned = re.sub(self.INVALID_CHARS, '_', group_name)
        # 移除首尾空格和点
        cleaned = cleaned.strip('. ')
        # 处理空字符串
        if not cleaned:
            cleaned = "Unknown"
        # 限制长度（Windows文件名限制为255字符，预留一些余量）
        if len(cleaned) > 200:
            cleaned = cleaned[:200]
        return cleaned
    
    def classify_signals(self, signal_names: List[str]) -> Dict[str, List[str]]:
        """
        对信号列表进行批量分组
        
        遍历信号列表，对每个信号执行分组提取，返回组名到信号列表的映射。
        未匹配任何规则的信号统一归入 "Others" 组。
        
        Args:
            signal_names: 信号名称列表
                每个元素应为完整的信号名称
        
        Returns:
            Dict[str, List[str]]: 分组结果字典
                键：组名称（如 'BATP1', 'BATPS', 'Others'）
                值：属于该组的信号名称列表
        
        Examples:
            >>> extractor = GroupExtractor()
            >>> signals = [
            ...     'test.dbc::BatP1_Msg::sig1',
            ...     'test.dbc::BatP2_Msg::sig2',
            ...     'test.dbc::FMC_Msg::sig3'
            ... ]
            >>> result = extractor.classify_signals(signals)
            >>> print(result)
            {'BATP1': ['test.dbc::BatP1_Msg::sig1'], 
             'BATP2': ['test.dbc::BatP2_Msg::sig2'], 
             'Others': ['test.dbc::FMC_Msg::sig3']}
        
        Note:
            - 即使没有信号归入 Others 组，返回字典中也不会包含 'Others' 键
            - 分组顺序不确定，如需排序请使用 get_discovered_groups()
        """
        classified: Dict[str, List[str]] = {}
        
        for signal_name in signal_names:
            group_name = self.extract_from_signal_name(signal_name)
            
            if group_name:
                # 符合规则的信号
                if group_name not in classified:
                    classified[group_name] = []
                classified[group_name].append(signal_name)
            else:
                # 不符合规则的信号归入 Others
                if "Others" not in classified:
                    classified["Others"] = []
                classified["Others"].append(signal_name)
        
        return classified
    
    def get_discovered_groups(self) -> List[str]:
        """
        获取所有已发现的组名称（排序后）
        
        返回按特定规则排序的组名称列表：
        1. BATP数字组：按数字升序排列（BATP1, BATP2, BATP10, ...）
        2. BATP字母组：按字母顺序排列（BATPL, BATPQ, BATPS, ...）
        3. Others：排在最后
        
        Returns:
            List[str]: 排序后的组名称列表
        
        Examples:
            >>> extractor = GroupExtractor()
            >>> # 假设已提取了多个组
            >>> extractor.discovered_groups = {'BATP10', 'BATP1', 'BATPS', 'BATP2'}
            >>> extractor.get_discovered_groups()
            ['BATP1', 'BATP2', 'BATP10', 'BATPS']
        """
        return sorted(self.discovered_groups, key=self._sort_key)
    
    def _sort_key(self, name: str) -> Tuple[int, int, str]:
        """
        生成组名称的排序键
        
        排序优先级：
        1. BATP数字组（优先级0）：按数字大小排序
        2. BATP字母组（优先级1）：按字母顺序排序
        3. 其他组（优先级50）：按名称排序
        4. Others（优先级99）：排在最后
        
        Args:
            name: 组名称
        
        Returns:
            Tuple[int, int, str]: 排序键元组
                (优先级, 数字值或0, 名称字符串)
        """
        if name == "Others":
            return (99, 0, name)
        elif name.startswith("BATP") and name[4:].isdigit():
            return (0, int(name[4:]), name)
        elif name.startswith("BATP"):
            return (1, 0, name)
        else:
            return (50, 0, name)
    
    def get_group_count(self) -> int:
        """
        获取已发现的组数量
        
        Returns:
            int: 组数量（不包括 Others 组）
        """
        return len(self.discovered_groups)
    
    def clear(self):
        """
        清空提取器状态
        
        重置所有缓存数据，包括：
        - 已发现的组集合
        - 信号到组的映射缓存
        
        通常在处理新的数据集之前调用。
        """
        self.discovered_groups.clear()
        self.group_mapping.clear()
    
    def get_statistics(self) -> Dict[str, any]:
        """
        获取提取器统计信息
        
        Returns:
            Dict[str, any]: 统计信息字典，包含：
                - discovered_groups_count: 已发现的组数量
                - mapped_signals_count: 已映射的信号数量
                - groups: 排序后的组名称列表
        
        Examples:
            >>> extractor = GroupExtractor()
            >>> # 假设已处理一些信号
            >>> stats = extractor.get_statistics()
            >>> print(stats)
            {'discovered_groups_count': 3, 'mapped_signals_count': 10, 'groups': ['BATP1', 'BATP2', 'BATPS']}
        """
        return {
            'discovered_groups_count': len(self.discovered_groups),
            'mapped_signals_count': len(self.group_mapping),
            'groups': sorted(self.discovered_groups, key=self._sort_key)
        }
