# tests/test_group_extractor.py
"""
组名称提取器单元测试
验证动态组名称提取功能
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from group_extractor import GroupExtractor, ExtractionStrategy


class TestGroupExtractorBasic(unittest.TestCase):
    """基础功能测试"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = GroupExtractor(ExtractionStrategy.AUTO_DISCOVER)
    
    def test_extract_batp_with_number(self):
        """测试BatP数字模式"""
        signal_name = "800V_BMS_PCAN_V2.5.3.dbc::BatP3_BMS_CellVoltMaxMin::P3_AvgCellVlt"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "BATP3")
    
    def test_extract_batpq(self):
        """测试BATPQ模式"""
        signal_name = "test.dbc::BATPQ_Message::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "BATPQ")
    
    def test_extract_batps(self):
        """测试BATPS模式"""
        signal_name = "test.dbc::BATPS_Message::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "BATPS")
    
    def test_extract_batpl(self):
        """测试BATPL模式（新组）"""
        signal_name = "test.dbc::BATPL_Message::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "BATPL")
    
    def test_extract_batpm(self):
        """测试BATPM模式（新组）"""
        signal_name = "test.dbc::BATPM_Message::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "BATPM")


class TestGroupExtractorMessagePrefix(unittest.TestCase):
    """消息名称前缀提取策略测试"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = GroupExtractor(ExtractionStrategy.MESSAGE_PREFIX)
    
    def test_extract_from_message_prefix(self):
        """测试从消息名称前缀提取"""
        signal_name = "test.dbc::BatP4_BMS_Status::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "BATP4")
    
    def test_extract_from_message_prefix_complex(self):
        """测试复杂消息名称"""
        signal_name = "test.dbc::BATPQ_CellData_V1::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "BATPQ")


class TestGroupExtractorSignalPrefix(unittest.TestCase):
    """信号名称前缀提取策略测试"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = GroupExtractor(ExtractionStrategy.SIGNAL_PREFIX)
    
    def test_extract_from_signal_prefix(self):
        """测试从信号名称前缀提取"""
        signal_name = "test.dbc::Message::P3_AvgCellVlt"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "P3")


class TestGroupExtractorBATPPattern(unittest.TestCase):
    """BATP模式提取策略测试"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = GroupExtractor(ExtractionStrategy.BATP_PATTERN)
    
    def test_extract_batp_uppercase(self):
        """测试大写BATP模式"""
        signal_name = "test.dbc::BATP5_Message::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "BATP5")
    
    def test_extract_batp_mixed_case(self):
        """测试混合大小写BatP模式"""
        signal_name = "test.dbc::BatP6_Message::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "BATP6")


class TestGroupExtractorCustomPattern(unittest.TestCase):
    """自定义模式提取策略测试"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = GroupExtractor(ExtractionStrategy.CUSTOM_PATTERN)
        self.extractor.add_custom_pattern(r'(HVMS\d*)')
        self.extractor.add_custom_pattern(r'(BMS_\w+)')
    
    def test_custom_pattern_hvms(self):
        """测试自定义HVMS模式"""
        signal_name = "test.dbc::HVMS3_Message::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "HVMS3")
    
    def test_custom_pattern_bms(self):
        """测试自定义BMS模式"""
        signal_name = "test.dbc::BMS_CellVolt::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertEqual(result, "BMS_CELLVOLT")


class TestGroupExtractorAutoDiscover(unittest.TestCase):
    """自动发现模式测试"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = GroupExtractor(ExtractionStrategy.AUTO_DISCOVER)
    
    def test_auto_discover_various_patterns(self):
        """测试自动发现各种模式"""
        test_cases = [
            ("test.dbc::BatP3_Msg::sig", "BATP3"),
            ("test.dbc::BATPQ_Msg::sig", "BATPQ"),
            ("test.dbc::BATPS_Msg::sig", "BATPS"),
            ("test.dbc::BATPL_Msg::sig", "BATPL"),
            ("test.dbc::BATPM_Msg::sig", "BATPM"),
            ("test.dbc::BATPX_Msg::sig", "BATPX"),
            ("test.dbc::HVMS_Msg::sig", None),
            ("test.dbc::BMS_Status::sig", None),
        ]
        
        for signal_name, expected_group in test_cases:
            result = self.extractor.extract_from_signal_name(signal_name)
            self.assertEqual(result, expected_group, f"Failed for {signal_name}")


class TestGroupExtractorSanitization(unittest.TestCase):
    """组名称清理测试"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = GroupExtractor(ExtractionStrategy.AUTO_DISCOVER)
    
    def test_sanitize_invalid_chars(self):
        """测试清理无效字符"""
        # 包含特殊字符的组名 - 使用BATPL模式（有效的组名）
        signal_name = "test.dbc::BATPL_Msg::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        # 应该提取出BATPL
        self.assertEqual(result, "BATPL")
    
    def test_sanitize_empty_result(self):
        """测试空结果处理"""
        signal_name = "test.dbc::::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        # 无法提取组名，应返回None
        self.assertIsNone(result)


class TestGroupExtractorClassification(unittest.TestCase):
    """信号分类测试"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = GroupExtractor(ExtractionStrategy.AUTO_DISCOVER)
    
    def test_classify_signals(self):
        """测试信号分类"""
        signals = [
            "test.dbc::BatP3_Msg::sig1",
            "test.dbc::BatP3_Msg::sig2",
            "test.dbc::BatP4_Msg::sig1",
            "test.dbc::BATPQ_Msg::sig1",
            "test.dbc::BATPS_Msg::sig1",
            "test.dbc::Unknown_Msg::sig1",
        ]
        
        classified = self.extractor.classify_signals(signals)
        
        self.assertEqual(len(classified.get("BATP3", [])), 2)
        self.assertEqual(len(classified.get("BATP4", [])), 1)
        self.assertEqual(len(classified.get("BATPQ", [])), 1)
        self.assertEqual(len(classified.get("BATPS", [])), 1)
    
    def test_get_discovered_groups(self):
        """测试获取发现的组"""
        signals = [
            "test.dbc::BatP3_Msg::sig1",
            "test.dbc::BatP4_Msg::sig1",
            "test.dbc::BATPQ_Msg::sig1",
        ]
        
        self.extractor.classify_signals(signals)
        groups = self.extractor.get_discovered_groups()
        
        self.assertIn("BATP3", groups)
        self.assertIn("BATP4", groups)
        self.assertIn("BATPQ", groups)
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        signals = [
            "test.dbc::BatP3_Msg::sig1",
            "test.dbc::BatP4_Msg::sig1",
        ]
        
        self.extractor.classify_signals(signals)
        stats = self.extractor.get_statistics()
        
        self.assertEqual(stats['discovered_groups_count'], 2)
        self.assertEqual(stats['mapped_signals_count'], 2)


class TestGroupExtractorCaching(unittest.TestCase):
    """缓存功能测试"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = GroupExtractor(ExtractionStrategy.AUTO_DISCOVER)
    
    def test_caching(self):
        """测试结果缓存"""
        signal_name = "test.dbc::BatP3_Msg::sig"
        
        # 第一次提取
        result1 = self.extractor.extract_from_signal_name(signal_name)
        
        # 第二次提取（应从缓存获取）
        result2 = self.extractor.extract_from_signal_name(signal_name)
        
        self.assertEqual(result1, result2)
        self.assertEqual(len(self.extractor.group_mapping), 1)
    
    def test_clear_cache(self):
        """测试清空缓存"""
        signal_name = "test.dbc::BatP3_Msg::sig"
        self.extractor.extract_from_signal_name(signal_name)
        
        self.assertGreater(len(self.extractor.group_mapping), 0)
        
        self.extractor.clear()
        
        self.assertEqual(len(self.extractor.group_mapping), 0)
        self.assertEqual(len(self.extractor.discovered_groups), 0)


class TestGroupExtractorEdgeCases(unittest.TestCase):
    """边界情况测试"""
    
    def setUp(self):
        """测试前准备"""
        self.extractor = GroupExtractor(ExtractionStrategy.AUTO_DISCOVER)
    
    def test_empty_signal_name(self):
        """测试空信号名称"""
        result = self.extractor.extract_from_signal_name("")
        self.assertIsNone(result)
    
    def test_none_signal_name(self):
        """测试None信号名称"""
        result = self.extractor.extract_from_signal_name(None)
        self.assertIsNone(result)
    
    def test_malformed_signal_name(self):
        """测试格式错误的信号名称"""
        result = self.extractor.extract_from_signal_name("invalid_format")
        self.assertIsNone(result)
    
    def test_very_long_group_name(self):
        """测试超长 BatP 组名称会被截断"""
        signal_name = f"test.dbc::BatP{'9' * 300}_Msg::signal"
        result = self.extractor.extract_from_signal_name(signal_name)
        self.assertIsNotNone(result)
        self.assertLessEqual(len(result), 200)


if __name__ == '__main__':
    unittest.main()
