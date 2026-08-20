# asc_to_csv/ui/export_tab.py
"""
数据导出标签页模块

提供CSV文件列选择、数据预览和导出功能。
支持左右双列表格选择机制，实时预览和灵活导出。
"""

import os
import csv
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, List
from datetime import datetime

from .base import BaseTab, LogMixin
from core.csv_loader import CSVDataLoader


class ExportTab(BaseTab, LogMixin):
    """
    数据导出标签页

    提供CSV文件的列选择、数据预览和导出功能。
    采用左右双列表格列选择机制，支持实时预览。
    """

    def __init__(self, parent: tk.Widget, app_context: dict):
        """
        初始化导出标签页

        Args:
            parent: 父容器
            app_context: 应用上下文
        """
        # 创建CSV数据加载器实例，用于加载和解析CSV文件
        self.data_loader = CSVDataLoader()
        # 当前加载文件对应的时间列名（被归一化为 epoch 的列，导出时需要还原为字符串）
        self._time_column: Optional[str] = None
        # 当前加载的CSV文件路径
        self.current_file: Optional[str] = None
        # 可用的数据列名列表（从CSV文件中读取）
        self.available_columns: List[str] = []
        # 用户选择要导出的数据列名列表
        self.selected_columns: List[str] = []
        # 经过搜索过滤后的数据列名列表
        self.filtered_columns: List[str] = []
        # 搜索关键词，用于过滤数据列
        self.search_keyword: str = ""

        # 文件路径输入框，用于显示和选择要导出的CSV文件
        self.file_entry: Optional[ttk.Entry] = None
        # 左侧列表框，显示可用数据列（待选择）
        self.left_listbox: Optional[tk.Listbox] = None
        # 右侧列表框，显示已选择的数据列（待导出）
        self.right_listbox: Optional[tk.Listbox] = None
        # 预览树形视图，用于显示数据预览表格
        self.preview_tree: Optional[ttk.Treeview] = None
        # 导出文件名输入框
        self.filename_entry: Optional[ttk.Entry] = None
        # 导出路径输入框
        self.path_entry: Optional[ttk.Entry] = None
        # CSV编码方式变量，存储用户选择的编码格式
        self.encoding_var: Optional[tk.StringVar] = None
        # 导出按钮，触发导出操作
        self.export_btn: Optional[ttk.Button] = None
        # 清除按钮，清除所有选择
        self.clear_btn: Optional[ttk.Button] = None
        # 预览按钮，显示数据预览
        self.preview_btn: Optional[ttk.Button] = None
        # 日志文本框，显示操作日志和错误信息
        self.log_text: Optional[tk.Text] = None
        # 状态标签，显示当前操作状态
        self.status_label: Optional[ttk.Label] = None
        # 搜索输入框，用于搜索数据列
        self.search_entry: Optional[ttk.Entry] = None
        # 左侧列表框的选中项索引列表
        self.left_selections: List[int] = []
        # 右侧列表框的选中项索引列表
        self.right_selections: List[int] = []

        # 异步加载相关字段（方案六优化）
        self._load_thread: Optional[threading.Thread] = None
        self._load_cancel_event: threading.Event = threading.Event()
        self._loading_file: Optional[str] = None

        # 调用父类初始化方法，完成基类的初始化
        super().__init__(parent, app_context)

    def _create_widgets(self):
        """创建界面组件
        
        构建导出标签页的完整界面布局，采用多层分割窗口结构实现灵活的界面布局和可调整大小的区域。
        
        界面布局结构：
        ┌─────────────────────────────────────────────────────┐
        │  主框架 (main_frame)                                  │
        │  ┌───────────────────────────────────────────────┐  │
        │  │  顶部框架 (top_frame) - 固定高度                │  │
        │  │  ├─ 文件选择区域 (file_section)                │  │
        │  │  ├─ 列选择区域 (column_selection_section)      │  │
        │  │  └─ 导出配置区域 (export_config_section)       │  │
        │  └───────────────────────────────────────────────┘  │
        │  ┌───────────────────────────────────────────────┐  │
        │  │  预览日志框架 (preview_log_frame)             │  │
        │  │  ├─ 操作按钮区域 (action_frame)               │  │
        │  │  ├─ 数据预览区域 (preview_inner_frame)        │  │
        │  │  └─ 日志显示区域 (log_inner_frame)             │  │
        │  └───────────────────────────────────────────────┘  │
        └─────────────────────────────────────────────────────┘
        
        使用说明：
            - 该方法在初始化时自动调用
            - 创建所有必需的界面控件
            - 设置分割窗口的拖拽约束
            - 绑定窗口大小调整事件
        """
        # 创建主框架（最外层容器），设置5像素的内边距
        # fill=tk.BOTH 表示框架在水平和垂直方向都填充父容器
        # expand=True 允许框架在父容器增大时扩展
        main_frame = ttk.Frame(self, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建垂直分割窗口（paned_window），用于分割顶部控制区和底部预览日志区
        # orient=tk.VERTICAL 表示分割线是水平方向，可以上下拖动调整高度
        self.paned_window = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # 创建顶部框架（top_frame），包含文件选择、列选择和导出配置区域
        # weight=0 表示该区域使用0权重，在调整大小时保持固定高度
        # 用户调整窗口大小时，只有weight>0的区域会发生变化
        top_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(top_frame, weight=0)

        # 创建预览日志框架（preview_log_frame），包含操作按钮、数据预览和日志区域
        # weight=1 表示该区域使用1权重，会随窗口大小变化而自动调整
        # 这确保了预览和日志区域能够充分利用可用空间
        preview_log_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(preview_log_frame, weight=1)

        # 创建操作按钮框架（action_frame），放置导出、清除、预览等按钮
        # fill=tk.X 表示只在水平方向填充
        # pady=(0, 5) 设置垂直内边距：上方0像素，下方5像素
        self.action_frame = ttk.Frame(preview_log_frame)
        self.action_frame.pack(fill=tk.X, pady=(0, 5))

        # 创建预览区域的垂直分割窗口（preview_paned）
        # 用于在数据预览和日志区域之间提供可调整的分隔
        self.preview_paned = ttk.PanedWindow(preview_log_frame, orient=tk.VERTICAL)
        self.preview_paned.pack(fill=tk.BOTH, expand=True)

        # 创建预览内部框架（preview_inner_frame），用于显示数据预览表格
        # weight=1 表示预览区域会随分割窗口调整大小而变化
        self.preview_inner_frame = ttk.Frame(self.preview_paned)
        self.preview_paned.add(self.preview_inner_frame, weight=1)

        # 创建日志内部框架（log_inner_frame），用于显示操作日志
        # weight=0 表示日志区域保持固定最小高度
        self.log_inner_frame = ttk.Frame(self.preview_paned)
        self.preview_paned.add(self.log_inner_frame, weight=0)

        # 创建各个功能区域的界面控件
        # 每个区域都有独立的创建方法，便于维护和扩展
        self._create_file_section(top_frame)               # 文件选择区域：输入框、浏览按钮
        self._create_column_selection_section(top_frame)  # 列选择区域：左右列表框、移动按钮
        self._create_export_config_section(top_frame)     # 导出配置：文件名、路径、编码选项
        self._create_action_section(self.action_frame)     # 操作按钮：导出、清除、预览、重置
        self._create_preview_section(self.preview_inner_frame)  # 数据预览：树形视图显示表格
        self._create_log_section(self.log_inner_frame)    # 日志显示：文本框显示操作记录

        # 绑定窗口大小调整事件，实现响应式布局
        # 当用户调整窗口大小时，自动重新计算各区域的尺寸
        self._bind_resize_event(main_frame)
        
        # 设置分割线拖拽约束（sash constraint）
        # 防止用户在拖拽分割线时将某个区域调整得过小
        # 确保预览和日志区域始终保持可用的最小尺寸
        self._setup_sash_constraint()

    def _setup_sash_constraint(self):
        """设置分割线拖拽约束"""
        self.preview_min_lines = 6
        self.log_min_lines = 3
        self.line_height_approx = 20

        self.preview_paned.bind("<B1-Motion>", self._on_sash_drag)
        self.preview_paned.bind("<ButtonRelease-1>", self._on_sash_release)

    def _on_sash_drag(self, event):
        """分割线拖拽时的约束处理"""
        self._constrain_sash_position()

    def _on_sash_release(self, event):
        """分割线释放时的约束处理"""
        self._constrain_sash_position()
        self._save_sash_position()

    def _constrain_sash_position(self):
        """约束分割线位置确保最小高度"""
        if not hasattr(self, 'preview_paned') or not self.preview_paned:
            return

        try:
            sash_pos = self.preview_paned.sashpos(0)
            preview_min = self.preview_min_lines * self.line_height_approx
            log_min = self.log_min_lines * self.line_height_approx + 80

            total_height = self.preview_paned.winfo_height()
            if total_height <= 1:
                total_height = 300

            max_sash_pos = total_height - log_min
            min_sash_pos = preview_min

            if sash_pos < min_sash_pos:
                self.preview_paned.sashpos(0, min_sash_pos)
            elif sash_pos > max_sash_pos:
                self.preview_paned.sashpos(0, max_sash_pos)
        except Exception:
            pass

    def _save_sash_position(self):
        """保存分割线位置"""
        if not hasattr(self, 'preview_paned'):
            return
        try:
            sash_pos = self.preview_paned.sashpos(0)
            total_height = self.preview_paned.winfo_height()
            if total_height > 1:
                self._saved_sash_ratio = sash_pos / total_height
        except Exception:
            pass

    def _restore_sash_position(self):
        """恢复保存的分割线位置"""
        if not hasattr(self, 'preview_paned') or not hasattr(self, '_saved_sash_ratio'):
            return
        try:
            total_height = self.preview_paned.winfo_height()
            if total_height > 1:
                sash_pos = int(total_height * self._saved_sash_ratio)
                preview_min = self.preview_min_lines * self.line_height_approx
                log_min = self.log_min_lines * self.line_height_approx + 80
                sash_pos = max(preview_min, min(sash_pos, total_height - log_min))
                self.preview_paned.sashpos(0, sash_pos)
        except Exception:
            pass

    def _bind_resize_event(self, main_frame: tk.Frame):
        """绑定窗口大小变化事件用于响应式调整"""
        self.bind("<Configure>", lambda e: self._adjust_layout(main_frame))

    def _adjust_layout(self, main_frame: tk.Frame):
        """根据窗口大小动态调整布局"""
        window_height = self.winfo_height()
        screen_height = self.winfo_screenheight()
        screen_width = self.winfo_screenwidth()

        line_height_px = 18
        target_height_px = screen_height * 0.25
        calculated_lines = max(4, min(12, int(target_height_px / line_height_px)))

        if window_height < 500:
            self._set_compact_mode(True)
            self._adjust_column_list_height(4)
        else:
            self._set_compact_mode(False)
            self._adjust_column_list_height(calculated_lines)

        if hasattr(self, 'preview_paned'):
            self._restore_sash_position()
            self._constrain_sash_position()

    def _adjust_column_list_height(self, height: int):
        """动态调整列选择列表的高度"""
        if not hasattr(self, 'left_listbox') or not self.left_listbox:
            return
        min_height = 11
        height = max(height, min_height)
        if self.left_listbox.cget('height') == height:
            return

        self.left_listbox.configure(height=height)
        self.right_listbox.configure(height=height)

    def _set_compact_mode(self, compact: bool):
        """设置紧凑模式以适应小屏幕"""
        if not hasattr(self, 'log_text') or not self.log_text:
            return

        if compact:
            if hasattr(self, '_original_log_height'):
                return
            self._original_log_height = self.log_text.cget("height")
            self.log_text.configure(height=3)
        else:
            if hasattr(self, '_original_log_height'):
                self.log_text.configure(height=self._original_log_height)

    def _create_file_section(self, parent: ttk.Frame):
        """创建文件选择区域"""
        file_frame = ttk.LabelFrame(parent, text="文件选择", padding="5")
        file_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(file_frame, text="CSV文件:").pack(side=tk.LEFT)
        self.file_entry = ttk.Entry(file_frame, width=60)
        self.file_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="浏览...", command=self._browse_file,
                   width=8).pack(side=tk.RIGHT, padx=(0, 5))
        ttk.Button(file_frame, text="加载文件",
                   command=self._load_selected_file).pack(side=tk.RIGHT)

    def _create_column_selection_section(self, parent: ttk.Frame):
        """创建左右双列表格列选择区域"""
        column_frame = ttk.LabelFrame(parent, text="列选择", padding="5")
        column_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        search_frame = ttk.Frame(column_frame)
        search_frame.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(search_frame, text="搜索列:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)
        ttk.Button(search_frame, text="清除", command=self._clear_search,
                  width=8).pack(side=tk.LEFT, padx=(5, 0))

        list_container = ttk.Frame(column_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(list_container)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        ttk.Label(left_frame, text="可用列").pack()

        left_scroll = ttk.Scrollbar(left_frame)
        left_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.left_listbox = tk.Listbox(left_frame, selectmode=tk.EXTENDED,
                                       yscrollcommand=left_scroll.set,
                                       height=11, exportselection=False)
        self.left_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.left_listbox.bind("<Double-Button-1>", lambda e: self._add_selected_column())
        self.left_listbox.bind("<<ListboxSelect>>", self._on_left_select)
        left_scroll.config(command=self.left_listbox.yview)

        btn_frame = ttk.Frame(list_container)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(btn_frame, text="选中 →",
                   command=self._add_selected_columns, width=10).pack(pady=3)
        ttk.Button(btn_frame, text="← 移除",
                   command=self._remove_selected_columns, width=10).pack(pady=3)
        ttk.Button(btn_frame, text="全选 →",
                   command=self._add_all_columns, width=10).pack(pady=3)
        ttk.Button(btn_frame, text="← 清空",
                   command=self._clear_selected_columns, width=10).pack(pady=3)

        right_frame = ttk.Frame(list_container)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        ttk.Label(right_frame, text="已选列").pack()

        right_scroll = ttk.Scrollbar(right_frame)
        right_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_listbox = tk.Listbox(right_frame, selectmode=tk.EXTENDED,
                                         yscrollcommand=right_scroll.set,
                                         height=11, exportselection=False)
        self.right_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.right_listbox.bind("<Double-Button-1>", lambda e: self._remove_selected_column())
        self.right_listbox.bind("<<ListboxSelect>>", self._on_right_select)
        right_scroll.config(command=self.right_listbox.yview)

        self.status_label = ttk.Label(list_container, text="请先加载CSV文件",
                                       foreground="blue")
        self.status_label.pack(pady=5, side=tk.BOTTOM)

        separator = ttk.Separator(column_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=(5, 0))

    def _create_export_config_section(self, parent: ttk.Frame):
        """创建导出配置区域"""
        config_frame = ttk.LabelFrame(parent, text="导出设置", padding="5")
        config_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(config_frame, text="文件名:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.filename_entry = ttk.Entry(config_frame, width=40)
        self.filename_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        ttk.Label(config_frame, text="（自动添加.csv扩展名）",
                 font=('', 8)).grid(row=0, column=2, sticky=tk.W, padx=5)

        ttk.Label(config_frame, text="保存路径:").grid(row=1, column=0, sticky=tk.W, pady=2)
        path_frame = ttk.Frame(config_frame)
        path_frame.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        self.path_entry = ttk.Entry(path_frame, width=35)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="浏览...", command=self._browse_path,
                   width=8).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Label(config_frame, text="编码:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.encoding_var = tk.StringVar(value="utf-8-sig")
        encoding_combo = ttk.Combobox(config_frame, textvariable=self.encoding_var,
                                       width=15, state="readonly")
        encoding_combo["values"] = ("utf-8-sig", "utf-8", "gbk", "gb2312")
        encoding_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        config_frame.columnconfigure(1, weight=1)

    def _create_preview_section(self, parent: ttk.Frame):
        """创建数据预览区域"""
        preview_frame = ttk.LabelFrame(parent, text="数据预览（前10行）", padding="5")
        preview_frame.pack(fill=tk.BOTH, expand=True)

        tree_frame = ttk.Frame(preview_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.preview_tree = ttk.Treeview(tree_frame,
                                          yscrollcommand=scroll_y.set,
                                          xscrollcommand=scroll_x.set,
                                          show="headings", height=6)
        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.config(command=self._preview_tree_yview)
        scroll_x.config(command=self._preview_tree_xview)

    def _preview_tree_yview(self, *args):
        """预览树垂直滚动"""
        self.preview_tree.yview(*args)

    def _preview_tree_xview(self, *args):
        """预览树水平滚动"""
        self.preview_tree.xview(*args)

    def _on_mousewheel(self, event):
        """鼠标滚轮事件处理"""
        if self.preview_tree and self.preview_tree.winfo_exists():
            self.preview_tree.yview("scroll", -1*(event.delta//120), "units")

    def _bound_to_mousewheel(self, widget):
        """绑定鼠标滚轮事件"""
        widget.bind("<MouseWheel>", self._on_mousewheel)

    def _create_action_section(self, parent: ttk.Frame):
        """创建操作按钮区域"""
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=(0, 5))

        self.preview_btn = ttk.Button(action_frame, text="数据预览",
                                      command=self._show_preview, width=15)
        self.preview_btn.pack(side=tk.LEFT, padx=5)

        self.export_btn = ttk.Button(action_frame, text="导出数据",
                                     command=self._start_export, width=15)
        self.export_btn.pack(side=tk.LEFT, padx=5)

        self.clear_btn = ttk.Button(action_frame, text="清空选项",
                                     command=self._clear_all, width=15)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

    def _create_log_section(self, parent: ttk.Frame):
        """创建日志区域"""
        log_frame = ttk.LabelFrame(parent, text="操作日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.log_text = tk.Text(log_frame, height=3, state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _format_cell_value(self, col: str, value) -> str:
        """
        格式化单元格值用于预览或导出。

        若该列为被归一化过的时间列（值为 epoch 秒浮点），则还原为
        用户可阅读的 `yyyy/mm/dd h:mm:ss.f` 字符串格式，防止导出后
        显示为 1786959657 这种大整数。
        """
        if value is None:
            return ""
        if (
            self._time_column
            and col == self._time_column
            and isinstance(value, (int, float))
            and value > 1e9  # epoch 2001 年之后，确认为真实时间戳
        ):
            try:
                whole = int(value)
                frac = round((value - whole) * 10)
                if frac == 10:
                    whole += 1
                    frac = 0
                frac %= 10
                dt = datetime.fromtimestamp(whole)
                date_part = f"{dt.year:04d}/{dt.month:02d}/{dt.day:02d}"
                time_part = f"{dt.hour}:{dt.minute:02d}:{dt.second:02d}"
                return f"{date_part} {time_part}.{frac}"
            except (OSError, OverflowError, ValueError):
                return str(value)
        return str(value)

    def _browse_file(self):
        """浏览并选择CSV文件"""
        filename = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if filename:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, filename)
            self._load_selected_file()

    def _load_selected_file(self):
        """加载选中的CSV文件 - 异步版本（后台线程执行，不阻塞UI）

        方案六优化：将耗时的CSV解析放到后台线程，主线程保持响应。
        后台线程只做纯数据IO和计算，所有Tk控件更新通过主线程回调执行。
        """
        file_path = self.file_entry.get().strip()
        if not file_path:
            messagebox.showwarning("提示", "请输入或选择CSV文件路径")
            return

        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"文件不存在: {file_path}")
            return

        # 取消上一次正在进行的加载任务
        if self._load_thread and self._load_thread.is_alive():
            self._load_cancel_event.set()
            self._load_thread.join(timeout=0.5)
        self._load_cancel_event.clear()
        self._loading_file = file_path

        self._log(f"正在加载: {os.path.basename(file_path)}")

        def load_worker():
            """后台线程：只做纯数据加载，不触碰任何Tk控件"""
            try:
                loader = CSVDataLoader()
                success = loader.load(file_path)
                if not self._load_cancel_event.is_set():
                    self.app_context['root'].after(
                        0, lambda: self._on_load_complete(success, loader, file_path)
                    )
            except Exception as e:
                if not self._load_cancel_event.is_set():
                    err_msg = str(e)
                    self.app_context['root'].after(
                        0, lambda: self._on_load_error(err_msg, file_path)
                    )

        self._load_thread = threading.Thread(target=load_worker, daemon=True)
        self._load_thread.start()

    def _on_load_complete(self, success: bool, loader: CSVDataLoader, file_path: str):
        """CSV加载完成回调（主线程执行）

        所有UI控件操作都在这里执行，确保线程安全。
        """
        # 如果当前加载的文件已经不是用户最后选择的文件，忽略旧结果
        if file_path != self._loading_file:
            return

        if not success:
            self._log("加载失败，请检查文件格式和编码")
            messagebox.showerror("错误", "文件加载失败")
            return

        # 释放旧 data_loader 内存
        if self.data_loader:
            self.data_loader.clear()
        self.data_loader = loader

        # 缓存时间列名（导出/预览时按名格式化）
        self._time_column = self.data_loader.get_time_column()
        self.current_file = file_path
        self.available_columns = self.data_loader.columns
        self.selected_columns = []
        self.filtered_columns = self.available_columns[:]
        self.search_keyword = ""

        if self.search_entry:
            self.search_entry.delete(0, tk.END)

        self._update_left_listbox()

        self.right_listbox.delete(0, tk.END)

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        self.filename_entry.delete(0, tk.END)
        self.filename_entry.insert(0, base_name)

        default_path = self.app_context.get('output_dir', os.path.dirname(file_path))
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, default_path)

        self._update_status()
        self._log(f"已加载 {len(self.available_columns)} 列，共 {self.data_loader.row_count} 行数据")

    def _on_load_error(self, error_msg: str, file_path: str):
        """CSV加载错误回调（主线程执行）"""
        if file_path != self._loading_file:
            return
        self._log(f"加载失败: {error_msg[:100]}")
        messagebox.showerror("错误", f"文件加载失败:\n{error_msg[:200]}")

    def _on_search_changed(self, event=None):
        """搜索框内容变化时的处理"""
        keyword = self.search_entry.get().strip().lower()
        self.search_keyword = keyword

        self.filtered_columns = []
        for col in self.available_columns:
            if keyword == "" or keyword in col.lower():
                self.filtered_columns.append(col)

        self._update_left_listbox()

    def _clear_search(self):
        """清除搜索"""
        if self.search_entry:
            self.search_entry.delete(0, tk.END)
        self.search_keyword = ""
        self.filtered_columns = self.available_columns[:]
        self._update_left_listbox()

    def _update_left_listbox(self):
        """更新左侧列表框显示"""
        self.left_listbox.delete(0, tk.END)
        for col in self.filtered_columns:
            self.left_listbox.insert(tk.END, col)

    def _on_left_select(self, event=None):
        """左侧列表选择事件"""
        self.left_selections = list(self.left_listbox.curselection())

    def _on_right_select(self, event=None):
        """右侧列表选择事件"""
        self.right_selections = list(self.right_listbox.curselection())

    def _add_selected_columns(self):
        """将左侧列表选中的多列添加到右侧"""
        if not self.left_selections:
            return

        for idx in self.left_selections:
            if idx < len(self.filtered_columns):
                col_name = self.filtered_columns[idx]
                if col_name not in self.selected_columns:
                    self.selected_columns.append(col_name)

        self._reorder_and_update_right_list()
        self._update_status()

    def _add_selected_column(self):
        """将左侧列表选中的列添加到右侧"""
        selection = self.left_listbox.curselection()
        if not selection:
            return

        col_index = selection[0]
        if col_index < len(self.filtered_columns):
            col_name = self.filtered_columns[col_index]

            if col_name not in self.selected_columns:
                self.selected_columns.append(col_name)
                self._reorder_and_update_right_list()

        self._update_status()

    def _remove_selected_columns(self):
        """从右侧列表移除选中的多列"""
        if not self.right_selections:
            return

        cols_to_remove = []
        for idx in self.right_selections:
            if idx < len(self.selected_columns):
                cols_to_remove.append(self.selected_columns[idx])

        for col in cols_to_remove:
            if col in self.selected_columns:
                self.selected_columns.remove(col)

        self._reorder_and_update_right_list()
        self._update_status()

    def _remove_selected_column(self):
        """从右侧列表移除选中的列"""
        selection = self.right_listbox.curselection()
        if not selection:
            return

        col_index = selection[0]
        col_name = self.selected_columns[col_index]

        self.selected_columns.pop(col_index)
        self.right_listbox.delete(col_index)
        self._update_status()

    def _add_all_columns(self):
        """将所有可用列添加到右侧"""
        if self.search_keyword:
            self.selected_columns = self.filtered_columns[:]
        else:
            self.selected_columns = self.available_columns[:]
        self._reorder_and_update_right_list()
        self._update_status()

    def _clear_selected_columns(self):
        """清空右侧列表"""
        self.selected_columns = []
        self.right_listbox.delete(0, tk.END)
        self._update_status()

    def _reorder_and_update_right_list(self):
        """重新排序并更新右侧列表（time列优先）"""
        time_cols = [c for c in self.selected_columns if 'time' in c.lower()]
        other_cols = [c for c in self.selected_columns if 'time' not in c.lower()]
        self.selected_columns = time_cols + other_cols

        self.right_listbox.delete(0, tk.END)
        for col in self.selected_columns:
            self.right_listbox.insert(tk.END, col)

    def _update_status(self):
        """更新状态标签"""
        total = len(self.available_columns)
        selected = len(self.selected_columns)
        if total > 0:
            self.status_label.config(
                text=f"已选择: {selected}/{total} 列",
                foreground="blue"
            )
        else:
            self.status_label.config(
                text="请先加载CSV文件",
                foreground="gray"
            )

    def _show_preview(self):
        """点击数据预览按钮时的处理"""
        if not self.selected_columns:
            messagebox.showwarning("提示", "请先选择要预览的列")
            return

        if not self.current_file:
            messagebox.showwarning("提示", "请先加载CSV文件")
            return

        self._bound_to_mousewheel(self.preview_tree)
        self._update_preview()

    def _update_preview(self):
        """更新数据预览"""
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

        self.preview_tree["columns"] = []
        self.preview_tree.tag_configure("time_col", background="#E6F3FF")

        if not self.selected_columns or not self.current_file:
            return

        preview_cols = self.selected_columns[:20]

        self.preview_tree["columns"] = preview_cols
        self.preview_tree.column("#0", width=0, stretch=False)

        for col in preview_cols:
            self.preview_tree.heading(col, text=col)
            col_len = len(col)
            width = max(80, min(150, col_len * 10))
            self.preview_tree.column(col, width=width, anchor=tk.W, stretch=False)

        preview_count = min(10, self.data_loader.row_count)
        for row_idx in range(preview_count):
            row_data = []
            for col in preview_cols:
                value = self.data_loader.data[col][row_idx]
                row_data.append(self._format_cell_value(col, value))
            self.preview_tree.insert("", tk.END, values=row_data)

    def _browse_path(self):
        """浏览保存路径"""
        initial_dir = self.path_entry.get() or os.path.dirname(self.current_file) if self.current_file else ""
        dirname = filedialog.askdirectory(title="选择保存路径", initialdir=initial_dir)
        if dirname:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, dirname)

    def _start_export(self):
        """开始导出数据"""
        if not self.selected_columns:
            messagebox.showwarning("提示", "请选择要导出的列")
            return

        if not self.current_file:
            messagebox.showwarning("提示", "请先加载CSV文件")
            return

        filename = self.filename_entry.get().strip()
        if not filename:
            messagebox.showerror("错误", "请输入导出文件名")
            return

        if not filename.endswith('.csv'):
            filename += '.csv'

        save_path = self.path_entry.get().strip()
        if not save_path:
            save_path = os.path.dirname(self.current_file)

        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建目录: {e}")
                return

        output_file = os.path.join(save_path, filename)

        self._log(f"正在导出到: {output_file}")
        self.export_btn.configure(state=tk.DISABLED)

        try:
            self._export_columns_to_csv(output_file, self.encoding_var.get())
            self._log(f"导出成功！")
            messagebox.showinfo("成功", f"数据已成功导出到:\n{output_file}")
        except Exception as e:
            self._log(f"导出失败: {str(e)}")
            messagebox.showerror("错误", f"导出失败:\n{str(e)}")
        finally:
            self.export_btn.configure(state=tk.NORMAL)

    def _export_columns_to_csv(self, output_file: str, encoding: str):
        """
        将选定的列导出到CSV文件

        Args:
            output_file: 输出文件路径
            encoding: 文件编码
        """
        try:
            with open(output_file, 'w', newline='', encoding=encoding) as f:
                writer = csv.writer(f)

                writer.writerow(self.selected_columns)

                for row_idx in range(self.data_loader.row_count):
                    row_data = []
                    for col in self.selected_columns:
                        value = self.data_loader.data[col][row_idx]
                        # 空值保持空串（兼容 Excel），非空值用格式化方法：
                        # 若是时间列将 epoch 浮点数还原为 yyyy/mm/dd h:mm:ss.f 字符串
                        if value is None or value == "":
                            row_data.append("")
                        else:
                            row_data.append(self._format_cell_value(col, value))
                    writer.writerow(row_data)
        except Exception as e:
            raise RuntimeError(f"写入文件失败: {e}")

    def _clear_all(self):
        """清空所有选项，重置到初始状态"""
        self.data_loader.clear()
        self._time_column = None
        self.current_file = None
        self.available_columns = []
        self.selected_columns = []
        self.filtered_columns = []
        self.search_keyword = ""

        self.file_entry.delete(0, tk.END)
        if self.search_entry:
            self.search_entry.delete(0, tk.END)
        self.left_listbox.delete(0, tk.END)
        self.right_listbox.delete(0, tk.END)

        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        self.preview_tree["columns"] = []

        self.filename_entry.delete(0, tk.END)
        self.filename_entry.insert(0, "export_data")
        self.path_entry.delete(0, tk.END)

        self._update_status()
        self._log("已清空所有选项")

    def refresh_files(self):
        """刷新文件列表（供外部调用）"""
        pass

    def cleanup(self):
        """清理资源，防止内存泄漏（方案六新增）"""
        # 先取消后台加载线程
        self._load_cancel_event.set()
        if self._load_thread and self._load_thread.is_alive():
            self._load_thread.join(timeout=1.0)
        self._load_thread = None

        if self.data_loader:
            self.data_loader.clear()

        self.current_file = None
        self.available_columns = []
        self.selected_columns = []
        self.filtered_columns = []

    def _log(self, message: str):
        """输出日志"""
        if not self.log_text:
            return
        try:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
            if self.root:
                self.root.update_idletasks()
        except tk.TclError:
            pass

    @property
    def root(self):
        """获取根窗口"""
        return self.app_context.get('root')