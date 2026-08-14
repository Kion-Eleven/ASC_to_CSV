#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ASC to CSV 转换与可视化工具 - 模块化版本

主入口模块，负责创建和管理整个GUI应用程序。

模块结构:
    - core/: 核心功能模块（数据加载、图表管理）
    - ui/: 用户界面模块（各功能标签页）
    - 其他模块: 数据处理相关功能

使用方法:
    python main_app.py

版本: 见 version.py
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

from config import Config, get_config
from version import __version__

from ui import ConvertTab, VisualizeTab, CompareTab, ExportTab

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['lines.antialiased'] = True
plt.rcParams['patch.antialiased'] = True


class MainApplication:
    """
    主应用程序类
    
    负责创建和管理整个GUI应用程序，协调各功能模块之间的交互。
    
    Attributes:
        root: Tkinter根窗口对象
        config: 应用配置对象
        notebook: 标签页容器
        convert_tab: 数据转换标签页
        visualize_tab: 数据可视化标签页
        compare_tab: 数据对比标签页
        app_context: 应用上下文字典，用于模块间通信
    
    Example:
        >>> root = tk.Tk()
        >>> app = MainApplication(root)
        >>> root.mainloop()
    """
    
    VERSION = f"v{__version__}"
    TITLE = "系统集成测试数据解析"
    MIN_SIZE = (1000, 700)
    DEFAULT_SIZE = (1400, 900)
    
    def __init__(self, root: tk.Tk):
        """
        初始化主应用程序
        
        Args:
            root: Tkinter根窗口对象
        """
        self.root = root
        self._setup_window()
        
        self.config: Config = None
        self.output_dir: str = None
        
        self._setup_styles()
        self._create_widgets()
        self._load_config()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _setup_window(self):
        """配置窗口属性"""
        self.root.title(f"{self.TITLE} {self.VERSION}")
        self.root.geometry(f"{self.DEFAULT_SIZE[0]}x{self.DEFAULT_SIZE[1]}")
        self.root.minsize(*self.MIN_SIZE)
    
    def _setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Microsoft YaHei", 12, "bold"))
    
    def _create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.app_context = self._create_app_context()
        
        self.convert_tab = ConvertTab(self.notebook, self.app_context)
        self.notebook.add(self.convert_tab, text="数据转换")
        
        self.visualize_tab = VisualizeTab(self.notebook, self.app_context)
        self.notebook.add(self.visualize_tab, text="数据可视化")
        
        self.compare_tab = CompareTab(self.notebook, self.app_context)
        self.notebook.add(self.compare_tab, text="数据对比")

        self.export_tab = ExportTab(self.notebook, self.app_context)
        self.notebook.add(self.export_tab, text="数据导出")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._tabs = [self.convert_tab, self.visualize_tab, self.compare_tab, self.export_tab]
        self._current_tab_index = 0
    
    def _create_app_context(self) -> dict:
        """
        创建应用上下文
        
        Returns:
            dict: 应用上下文字典
        """
        return {
            'root': self.root,
            'output_dir': None,
            'is_converting': False,
            'refresh_callback': self._on_convert_complete
        }
    
    def _load_config(self):
        """加载配置文件"""
        try:
            self.config = get_config()
            if self.config:
                self.convert_tab.load_config(self.config)
                if self.config.output_dir:
                    self.output_dir = self.config.output_dir
                    self.app_context['output_dir'] = self.output_dir
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"加载配置失败: {e}")
    
    def _on_convert_complete(self):
        """转换完成回调函数"""
        output_dir = self.app_context.get('output_dir')
        if output_dir:
            self.output_dir = output_dir
            self.visualize_tab.refresh_files()
            self.compare_tab.refresh_files()
            self.export_tab.refresh_files()
    
    def _on_tab_changed(self, event):
        """Tab切换时触发的事件"""
        new_index = self.notebook.index(self.notebook.select())

        if 0 <= self._current_tab_index < len(self._tabs):
            old_tab = self._tabs[self._current_tab_index]
            old_tab.on_deactivate()

        self._current_tab_index = new_index

        if 0 <= new_index < len(self._tabs):
            new_tab = self._tabs[new_index]
            new_tab.on_activate()

    def _on_closing(self):
        """窗口关闭事件处理"""
        if self.app_context.get('is_converting', False):
            if messagebox.askyesno("确认", "转换正在进行中，确定要退出吗？"):
                self._cleanup_all_tabs()
                self.root.quit()
        else:
            self._cleanup_all_tabs()
            self.root.quit()

    def _cleanup_all_tabs(self):
        """清理所有Tab的资源"""
        for tab in self._tabs:
            try:
                tab.cleanup()
            except Exception as e:
                print(f"清理Tab资源时出错: {e}")


def main():
    """
    程序入口函数
    
    创建Tkinter根窗口和主应用程序实例，启动主事件循环。
    """
    root = tk.Tk()
    app = MainApplication(root)
    root.mainloop()


if __name__ == "__main__":
    main()
