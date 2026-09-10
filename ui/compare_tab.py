# asc_to_csv/ui/compare_tab.py
"""
数据对比标签页模块

提供多文件数据对比功能界面，支持异步加载和进度显示。
"""

import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, List, Dict, Tuple
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import BaseTab
from core.csv_loader import CSVDataLoader, MULTI_SELECT_COLUMNS, read_csv_column_sample
from core.chart_manager import ChartManager
from core.compare_export import (
    is_time_column,
    read_csv_header,
    resolve_matching_column,
    strip_column_prefix,
    write_export_csv,
)


BATCH_SIZE = 10000
MAX_CONCURRENT_LOADS = 3
PROGRESS_UPDATE_INTERVAL = 100


def _extract_file_id(file_name: str) -> str:
    """
    从文件名提取编号，用于括号标注

    规则：BATP5.csv -> '5'，BATPQ.csv -> 'Q'，BATP10.csv -> '10'；
    非BATP*文件（如Others.csv）统一返回 '0'。

    Args:
        file_name: CSV文件名

    Returns:
        str: 文件编号
    """
    base = file_name[:-4] if file_name.lower().endswith('.csv') else file_name
    if base.upper().startswith('BATP') and len(base) > 4:
        return base[4:]
    return '0'


def _file_id_sort_key(file_id: str):
    """
    括号内文件编号的排序键：0在前，数字升序，字母顺序

    Args:
        file_id: 文件编号

    Returns:
        tuple: 排序键
    """
    if file_id == '0':
        return (0, 0, '')
    if file_id.isdigit():
        return (1, int(file_id), '')
    return (2, 0, file_id)


class CompareTab(BaseTab):
    """
    数据对比标签页

    提供多文件数据对比功能，支持异步加载和进度显示。
    支持固定复选框列与搜索添加的公有数据列（跨文件统一列名）两种选择方式。

    Attributes:
        compare_file_listbox: 文件列表框
        compare_column_vars: 数据列选择变量字典
        compare_selected_listbox: 已选择数据列列表框
        compare_search_entry: 数据列搜索输入框
        compare_search_listbox: 数据列搜索结果列表框
        chart_manager: 图表管理器
    """

    def __init__(self, parent: tk.Widget, app_context: dict):
        """
        初始化对比标签页

        Args:
            parent: 父容器
            app_context: 应用上下文
        """
        self.compare_file_listbox: Optional[tk.Listbox] = None
        self.compare_column_vars: Dict[str, tk.BooleanVar] = {}
        self.chart_manager: Optional[ChartManager] = None

        self.compare_selected_listbox: Optional[tk.Listbox] = None
        self.compare_search_entry: Optional[ttk.Entry] = None
        self.compare_search_listbox: Optional[tk.Listbox] = None
        self._search_var: Optional[tk.StringVar] = None

        self._column_pool: Dict[str, List[str]] = {}
        self._pool_file_count: int = 0
        self._search_results: List[str] = []
        self._selected_unified_columns: List[str] = []

        self.compare_zoom_level: float = 1.0
        self.compare_scroll_position: float = 0.0

        self._compare_time_data: List = []
        self._loaded_files: OrderedDict = OrderedDict()

        self._compare_update_pending: bool = False
        self._last_compare_update: float = 0
        self._debounce_delay: int = 50
        self._listbox_hover: bool = False

        self._max_data_points: int = 100000

        self.compare_zoom_scale: Optional[ttk.Scale] = None
        self.compare_zoom_label: Optional[ttk.Label] = None
        self.compare_scroll_scale: Optional[ttk.Scale] = None
        self.compare_status_label: Optional[ttk.Label] = None
        self._datatip_var: Optional[tk.BooleanVar] = None

        self._compare_thread: Optional[threading.Thread] = None
        self._cancel_event: threading.Event = threading.Event()
        self._is_comparing: bool = False

        self._progress_bar: Optional[ttk.Progressbar] = None
        self._cancel_btn: Optional[ttk.Button] = None
        self._export_btn: Optional[ttk.Button] = None
        self._export_thread: Optional[threading.Thread] = None
        self._is_exporting: bool = False

        super().__init__(parent, app_context)

    def on_activate(self):
        """标签页激活：确保对比图表可见并重绘"""
        super().on_activate()
        if self.chart_manager is not None:
            try:
                self.chart_manager.draw_idle()
            except Exception:
                pass

    def _create_widgets(self):
        """创建界面组件"""
        control_frame = ttk.LabelFrame(self, text="对比设置", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 5))

        self._create_file_section(control_frame)
        self._create_column_section(control_frame)
        self._create_control_section(control_frame)
        self._create_progress_section(control_frame)

        chart_frame = ttk.LabelFrame(self, text="对比图表", padding="5")
        chart_frame.pack(fill=tk.BOTH, expand=True)

        self.chart_manager = ChartManager(chart_frame)
        self.chart_manager.get_widget().pack(fill=tk.BOTH, expand=True)
        self.chart_manager.add_toolbar(chart_frame)

        self.chart_manager.bind_scroll(self._on_mouse_scroll)
        self.chart_manager.bind_motion(self._on_mouse_move)

        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        self.compare_status_label = ttk.Label(status_frame, text="请选择文件和数据列进行对比")
        self.compare_status_label.pack(side=tk.LEFT)

    def _create_file_section(self, parent: ttk.Frame):
        """创建文件选择区域（含已选择数据列、搜索和添加/删除/清空按钮）"""
        file_frame = ttk.Frame(parent)
        file_frame.pack(fill=tk.X, pady=5)

        ttk.Label(file_frame, text="选择文件:").pack(side=tk.LEFT)

        listbox_frame = ttk.Frame(file_frame)
        listbox_frame.pack(side=tk.LEFT, padx=5)

        self.compare_file_listbox = tk.Listbox(
            listbox_frame, height=4, selectmode=tk.MULTIPLE,
            width=40, exportselection=False)
        self.compare_file_listbox.pack(side=tk.LEFT)

        self.compare_file_listbox.bind('<MouseWheel>', self._on_file_list_scroll)
        self.compare_file_listbox.bind('<Button-4>', self._on_file_list_scroll_linux)
        self.compare_file_listbox.bind('<Button-5>', self._on_file_list_scroll_linux)

        self.compare_file_listbox.bind('<Enter>', self._on_listbox_enter)
        self.compare_file_listbox.bind('<Leave>', self._on_listbox_leave)

        # 文件选择变化时重建数据列搜索池
        self.compare_file_listbox.bind('<<ListboxSelect>>', self._on_file_selection_changed)

        ttk.Button(file_frame, text="刷新文件", command=self._refresh_files).pack(side=tk.LEFT, padx=5)

        # 已选择数据列框
        selected_frame = ttk.Frame(file_frame)
        selected_frame.pack(side=tk.LEFT, padx=(15, 5))

        ttk.Label(selected_frame, text="已选择数据列:").pack(anchor=tk.W)

        self.compare_selected_listbox = tk.Listbox(
            selected_frame, height=4, selectmode=tk.MULTIPLE,
            width=28, exportselection=False)
        self.compare_selected_listbox.pack()
        self._setup_listbox_scrolling(self.compare_selected_listbox)

        # 搜索框 + 搜索结果列表
        search_frame = ttk.Frame(file_frame)
        search_frame.pack(side=tk.LEFT, padx=5)

        ttk.Label(search_frame, text="搜索数据列:").pack(anchor=tk.W)

        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', lambda *_: self._refresh_search_results())
        self.compare_search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        self.compare_search_entry.pack(fill=tk.X)

        self.compare_search_listbox = tk.Listbox(
            search_frame, height=3, selectmode=tk.MULTIPLE,
            width=30, exportselection=False)
        self.compare_search_listbox.pack()
        self._setup_listbox_scrolling(self.compare_search_listbox)

        # 添加 / 删除 / 清空按钮
        column_btn_frame = ttk.Frame(file_frame)
        column_btn_frame.pack(side=tk.LEFT, padx=5)

        ttk.Button(column_btn_frame, text="添加", command=self._add_selected_columns).pack(pady=1)
        ttk.Button(column_btn_frame, text="删除", command=self._remove_selected_columns).pack(pady=1)
        ttk.Button(column_btn_frame, text="清空", command=self._clear_selected_columns).pack(pady=1)

    def _setup_listbox_scrolling(self, listbox: tk.Listbox):
        """为列表框绑定鼠标滚轮滚动和悬停聚焦"""
        listbox.bind('<Enter>', lambda e: listbox.focus_set())

        def on_wheel(event):
            listbox.yview_scroll(-1 if event.delta > 0 else 1, 'units')
            return "break"

        def on_button4(event):
            listbox.yview_scroll(-1, 'units')
            return "break"

        def on_button5(event):
            listbox.yview_scroll(1, 'units')
            return "break"

        listbox.bind('<MouseWheel>', on_wheel)
        listbox.bind('<Button-4>', on_button4)
        listbox.bind('<Button-5>', on_button5)

    def _create_column_section(self, parent: ttk.Frame):
        """创建数据列选择区域"""
        column_frame = ttk.Frame(parent)
        column_frame.pack(fill=tk.X, pady=5)

        ttk.Label(column_frame, text="选择数据列:").pack(side=tk.LEFT)

        self.compare_column_frame = ttk.Frame(column_frame)
        self.compare_column_frame.pack(side=tk.LEFT, padx=5)

        for i, col_name in enumerate(MULTI_SELECT_COLUMNS):
            var = tk.BooleanVar(value=False)
            self.compare_column_vars[col_name] = var
            cb = ttk.Checkbutton(self.compare_column_frame, text=col_name, variable=var)
            cb.grid(row=0, column=i, padx=5)

    def _create_control_section(self, parent: ttk.Frame):
        """创建控制按钮区域"""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=5)

        self._compare_btn = ttk.Button(btn_frame, text="生成对比图", command=self._start_compare)
        self._compare_btn.pack(side=tk.LEFT, padx=5)

        self._cancel_btn = ttk.Button(btn_frame, text="取消", command=self._cancel_compare, state=tk.DISABLED)
        self._cancel_btn.pack(side=tk.LEFT, padx=5)

        self._export_btn = ttk.Button(btn_frame, text="导出选中列", command=self._export_selected_columns)
        self._export_btn.pack(side=tk.LEFT, padx=5)

        ttk.Label(btn_frame, text="缩放:").pack(side=tk.LEFT, padx=(20, 0))
        self.compare_zoom_scale = ttk.Scale(btn_frame, from_=0.1, to=5.0, value=1.0,
                                             orient=tk.HORIZONTAL, length=100,
                                             command=self._on_zoom_changed)
        self.compare_zoom_scale.pack(side=tk.LEFT, padx=5)
        self.compare_zoom_label = ttk.Label(btn_frame, text="100%", width=6)
        self.compare_zoom_label.pack(side=tk.LEFT)

        ttk.Button(btn_frame, text="重置缩放", command=self._reset_zoom).pack(side=tk.LEFT, padx=10)

        ttk.Label(btn_frame, text="水平滚动:").pack(side=tk.LEFT, padx=(20, 0))
        self.compare_scroll_scale = ttk.Scale(btn_frame, from_=0, to=100, value=0,
                                               orient=tk.HORIZONTAL, length=150,
                                               command=self._on_scroll_changed)
        self.compare_scroll_scale.pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="重置滚动", command=self._reset_scroll).pack(side=tk.LEFT, padx=10)

        self._datatip_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(btn_frame, text="显示数据提示", variable=self._datatip_var,
                        command=self._toggle_datatip).pack(side=tk.LEFT, padx=(15, 0))

    def _create_progress_section(self, parent: ttk.Frame):
        """创建进度显示区域"""
        progress_frame = ttk.Frame(parent)
        progress_frame.pack(fill=tk.X, pady=5)

        self._progress_label = ttk.Label(progress_frame, text="")
        self._progress_label.pack(side=tk.LEFT)

        self._progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=200)
        self._progress_bar.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

    def _on_listbox_enter(self, event):
        """鼠标进入列表框时获取焦点"""
        self._listbox_hover = True
        self.compare_file_listbox.focus_set()

    def _on_listbox_leave(self, event):
        """鼠标离开列表框"""
        self._listbox_hover = False

    def _on_file_list_scroll(self, event):
        """
        文件列表滚动事件处理 (Windows/macOS)

        Args:
            event: 鼠标滚轮事件对象

        Returns:
            str: "break" 阻止事件继续传播
        """
        if not self.compare_file_listbox:
            return "break"

        size = self.compare_file_listbox.size()
        if size == 0:
            return "break"

        first_visible = self.compare_file_listbox.nearest(0)
        scroll_amount = 1

        if event.delta > 0:
            self.compare_file_listbox.yview_scroll(-scroll_amount, "units")
        else:
            self.compare_file_listbox.yview_scroll(scroll_amount, "units")

        return "break"

    def _on_file_list_scroll_linux(self, event):
        """
        文件列表滚动事件处理 (Linux)

        Args:
            event: 鼠标按钮事件对象

        Returns:
            str: "break" 阻止事件继续传播
        """
        if not self.compare_file_listbox:
            return "break"

        size = self.compare_file_listbox.size()
        if size == 0:
            return "break"

        scroll_amount = 1

        if event.num == 4:
            self.compare_file_listbox.yview_scroll(-scroll_amount, "units")
        elif event.num == 5:
            self.compare_file_listbox.yview_scroll(scroll_amount, "units")

        return "break"

    def _refresh_files(self):
        """刷新文件列表（排除Summary.csv汇总表）"""
        output_dir = self.app_context.get('output_dir', '')
        if not output_dir or not os.path.exists(output_dir):
            messagebox.showwarning("提示", "请先进行数据转换或设置输出目录")
            return

        csv_files = [f for f in os.listdir(output_dir)
                     if f.endswith('.csv') and f.lower() != 'summary.csv']

        self.compare_file_listbox.delete(0, tk.END)
        for f in csv_files:
            self.compare_file_listbox.insert(tk.END, f)

        # 列表重建后选择被清空，同步清空数据列搜索池
        self._rebuild_column_pool()

        self.compare_status_label.config(text=f"已加载 {len(csv_files)} 个文件")

    def _on_file_selection_changed(self, event=None):
        """文件选择变化时重建数据列搜索池"""
        self._rebuild_column_pool()

    def _rebuild_column_pool(self):
        """
        根据当前选中的文件重建公有数据列搜索池

        读取各选中文件的表头和采样数据，将数值列按公有名称
        （去掉首个下划线前缀）聚合，记录拥有该列的文件。
        """
        self._column_pool = {}
        self._pool_file_count = 0
        if self.compare_file_listbox is None:
            return

        selected = self.compare_file_listbox.curselection()
        if not selected:
            self._refresh_search_results()
            return

        self._pool_file_count = len(selected)
        output_dir = self.app_context.get('output_dir', '')

        for i in selected:
            file_name = self.compare_file_listbox.get(i)
            numeric_cols = read_csv_column_sample(os.path.join(output_dir, file_name))
            if not numeric_cols:
                continue

            unified_names = {strip_column_prefix(col) for col in numeric_cols}
            for unified in unified_names:
                self._column_pool.setdefault(unified, []).append(file_name)

        self._refresh_search_results()

    def _format_column_display(self, unified: str) -> str:
        """
        生成公有列的显示文本

        所有选中文件都有该列时不带括号；仅部分文件有时，
        括号中标注拥有该列的文件编号（排序：0、数字升序、字母）。

        Args:
            unified: 公有列名

        Returns:
            str: 显示文本，如 'AvgCellTemp[C]' 或 'AvgCellTemp[C](3,5)'
        """
        file_names = self._column_pool.get(unified, [])
        if not file_names:
            return unified
        if self._pool_file_count > 0 and len(file_names) >= self._pool_file_count:
            return unified
        ids = sorted({_extract_file_id(f) for f in file_names}, key=_file_id_sort_key)
        return f"{unified}({','.join(ids)})"

    def _refresh_search_results(self):
        """根据搜索框内容刷新搜索结果列表"""
        if self.compare_search_listbox is None:
            return

        keyword = ''
        if self._search_var is not None:
            keyword = self._search_var.get().strip().lower()

        self.compare_search_listbox.delete(0, tk.END)
        self._search_results = []

        for unified in sorted(self._column_pool.keys(), key=lambda s: s.lower()):
            display = self._format_column_display(unified)
            if keyword and keyword not in display.lower():
                continue
            self.compare_search_listbox.insert(tk.END, display)
            self._search_results.append(unified)

    def _add_selected_columns(self):
        """将搜索结果中选中的公有列添加到已选择数据列框"""
        if self.compare_search_listbox is None:
            return

        indices = self.compare_search_listbox.curselection()
        if not indices:
            messagebox.showinfo("提示", "请先在搜索结果中选择要添加的数据列")
            return

        for idx in indices:
            if idx >= len(self._search_results):
                continue
            unified = self._search_results[idx]
            if unified in self._selected_unified_columns:
                continue
            self._selected_unified_columns.append(unified)
            self.compare_selected_listbox.insert(tk.END, self._format_column_display(unified))

        self.compare_status_label.config(
            text=f"已选择 {len(self._selected_unified_columns)} 个数据列")

    def _remove_selected_columns(self):
        """删除已选择数据列框中选中的条目"""
        if self.compare_selected_listbox is None:
            return

        indices = self.compare_selected_listbox.curselection()
        if not indices:
            messagebox.showinfo("提示", "请先在已选择数据列框中选择要删除的条目")
            return

        for idx in sorted(indices, reverse=True):
            del self._selected_unified_columns[idx]
            self.compare_selected_listbox.delete(idx)

        self.compare_status_label.config(
            text=f"已选择 {len(self._selected_unified_columns)} 个数据列")

    def _clear_selected_columns(self):
        """清空已选择数据列"""
        self._selected_unified_columns.clear()
        if self.compare_selected_listbox is not None:
            self.compare_selected_listbox.delete(0, tk.END)
        self.compare_status_label.config(text="已清空已选择数据列")

    def _get_column_requests(self) -> List[Tuple[str, str]]:
        """
        构建绘图列请求列表

        固定复选框列在前（子串匹配），搜索添加的公有列在后（剥离规则精确匹配）。
        去重时先解析的生效，保证重复内容在图中只显示一次。

        Returns:
            List[Tuple[str, str]]: (类型, 列名) 列表，类型为 'fixed' 或 'unified'
        """
        fixed = [('fixed', col) for col, var in self.compare_column_vars.items() if var.get()]
        unified = [('unified', col) for col in self._selected_unified_columns]
        return fixed + unified

    def _start_compare(self):
        """开始异步对比操作"""
        if self._is_exporting:
            return

        selected_files = self.compare_file_listbox.curselection()
        if not selected_files:
            messagebox.showwarning("提示", "请至少选择一个文件")
            return

        selected_columns = self._get_column_requests()
        if not selected_columns:
            messagebox.showwarning("提示", "请至少选择一个数据列")
            return

        self._is_comparing = True
        self._cancel_event.clear()
        self._compare_btn.config(state=tk.DISABLED)
        self._cancel_btn.config(state=tk.NORMAL)
        if self._export_btn is not None:
            self._export_btn.config(state=tk.DISABLED)
        self._progress_bar.config(value=0)
        self._progress_label.config(text="准备中...")

        file_names = [self.compare_file_listbox.get(i) for i in selected_files]

        self._compare_thread = threading.Thread(
            target=self._async_generate_chart,
            args=(file_names, selected_columns),
            daemon=True
        )
        self._compare_thread.start()

    def _cancel_compare(self):
        """取消对比操作"""
        self._cancel_event.set()
        self._progress_label.config(text="正在取消...")

    def _async_generate_chart(self, file_names: List[str], selected_columns: List[Tuple[str, str]]):
        """异步生成对比图表（在线程中执行）"""
        def on_render_complete(success: bool, cancelled: bool):
            if cancelled or not success:
                self._on_compare_complete(cancelled=True)
            else:
                self._on_compare_complete(cancelled=False)

        try:
            self._update_progress(0, len(file_names), "正在加载文件...")

            loaded_data = self._load_files_async(file_names, selected_columns)

            if self._cancel_event.is_set():
                self._on_compare_complete(cancelled=True)
                return

            self._update_progress(len(file_names), len(file_names), "正在处理数据...")

            processed_data = self._process_compare_data(loaded_data, selected_columns)

            if self._cancel_event.is_set():
                self._on_compare_complete(cancelled=True)
                return

            self._update_progress(len(file_names), len(file_names), "正在渲染图表...")

            self._render_chart(processed_data, file_names, selected_columns, on_render_complete)

        except Exception as e:
            self._on_compare_error(str(e))

    def _load_files_async(self, file_names: List[str], selected_columns: List[Tuple[str, str]]) -> Dict:
        """
        异步加载多个文件

        Args:
            file_names: 文件名列表
            selected_columns: 选中的列请求列表，元素为 (类型, 列名)

        Returns:
            Dict: 文件路径到加载数据的映射
        """
        loaded_data = {}
        output_dir = self.app_context.get('output_dir', '')

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_LOADS) as executor:
            future_to_file = {}
            for i, file_name in enumerate(file_names):
                file_path = os.path.join(output_dir, file_name)
                future = executor.submit(self._load_single_file, file_path, file_name, selected_columns)
                future_to_file[future] = (file_name, i)

            completed = 0
            for future in as_completed(future_to_file):
                if self._cancel_event.is_set():
                    executor.shutdown(wait=False)
                    return loaded_data

                file_name, idx = future_to_file[future]
                try:
                    data = future.result()
                    if data:
                        loaded_data[file_name] = data
                except Exception as e:
                    print(f"加载文件失败 {file_name}: {e}")

                completed += 1
                self._update_progress(completed, len(file_names), f"已加载 {completed}/{len(file_names)} 个文件")

        return loaded_data

    def _load_single_file(self, file_path: str, file_name: str, selected_columns: List[Tuple[str, str]]) -> Optional[Dict]:
        """
        加载单个CSV文件并进行预处理

        Args:
            file_path: 文件路径
            file_name: 文件名
            selected_columns: 选中的列请求列表，元素为 (类型, 列名)，
                类型 'fixed' 为固定复选框列（子串匹配），
                类型 'unified' 为搜索添加的公有列（剥离规则精确匹配）

        Returns:
            Dict: 包含时间列和选中列的数据
        """
        if file_path in self._loaded_files:
            loader = self._loaded_files[file_path]
            self._loaded_files.move_to_end(file_path)
        else:
            loader = CSVDataLoader()
            if not loader.load(file_path):
                return None
            self._add_to_cache(file_path, loader)

        time_col = loader.get_time_column()
        if not time_col:
            return None

        time_data = self._downsample_data(loader.data[time_col], BATCH_SIZE)

        col_data = {}
        used_columns = set()
        for req_type, target_col in selected_columns:
            matching_col = resolve_matching_column(loader, req_type, target_col, time_col)

            # 同一文件中解析到相同实际列名时只保留先解析的（重复内容只显示一次）
            if matching_col and matching_col not in used_columns:
                used_columns.add(matching_col)
                col_data[(req_type, target_col)] = self._downsample_data(
                    loader.data[matching_col], BATCH_SIZE)

        return {
            'time_data': time_data,
            'columns': col_data,
            'total_points': len(loader.data[time_col])
        }

    def _downsample_data(self, data: List, max_points: int) -> List:
        """
        数据降采样

        Args:
            data: 原始数据列表
            max_points: 最大采样点数

        Returns:
            List: 降采样后的数据
        """
        if len(data) <= max_points:
            return data

        step = len(data) / max_points
        indices = [int(i * step) for i in range(max_points)]
        return [data[i] if i < len(data) else None for i in indices]

    def _process_compare_data(self, loaded_data: Dict, selected_columns: List[Tuple[str, str]]) -> Dict:
        """
        处理对比数据

        Args:
            loaded_data: 加载的文件数据
            selected_columns: 选中的列请求列表，元素为 (类型, 列名)

        Returns:
            Dict: 处理后的数据
        """
        processed = {}
        max_points = 0

        for file_name, data in loaded_data.items():
            total = data['total_points']
            if total > max_points:
                max_points = total

            time_data = data['time_data']
            col_data = data['columns']

            for col_name, col_values in col_data.items():
                key = (file_name, col_name)
                processed[key] = {
                    'x': time_data,
                    'y': col_values
                }

        return {
            'data': processed,
            'max_points': max_points,
            'file_count': len(loaded_data)
        }

    def _render_chart(self, processed_data: Dict, file_names: List[str], selected_columns: List[Tuple[str, str]],
                      render_complete_callback: callable):
        """
        在主线程中渲染图表（线程安全版本）

        Args:
            processed_data: 处理后的数据
            file_names: 文件名列表
            selected_columns: 选中的列请求列表，元素为 (类型, 列名)
            render_complete_callback: 渲染完成后的回调，接收 (success: bool, cancelled: bool) 参数
        """
        def do_render():
            try:
                self.chart_manager.clear()

                import matplotlib.pyplot as plt
                colors = plt.cm.tab10.colors
                color_idx = 0

                data = processed_data['data']
                max_points = processed_data['max_points']

                visible_points = max(1, int(max_points / self.compare_zoom_level))
                visible_points = min(visible_points, self._max_data_points)

                start_idx = int(self.compare_scroll_position * (max_points - visible_points))
                start_idx = max(0, min(start_idx, max_points - visible_points))
                end_idx = min(start_idx + visible_points, max_points)

                for file_name in file_names:
                    for col_name in selected_columns:
                        if self._cancel_event.is_set():
                            render_complete_callback(success=False, cancelled=True)
                            return

                        key = (file_name, col_name)
                        if key not in data:
                            continue

                        point_data = data[key]
                        x_data = point_data['x'][start_idx:end_idx]
                        y_data = point_data['y'][start_idx:end_idx]

                        valid_indices = [i for i, v in enumerate(y_data) if v is not None]

                        if valid_indices:
                            _, req_name = col_name
                            label = f"{file_name.replace('.csv', '')} - {req_name}"
                            x_valid = [x_data[i] for i in valid_indices]
                            y_valid = [y_data[i] for i in valid_indices]

                            self.chart_manager.plot_segments(
                                x_valid, y_valid, label=label,
                                linewidth=1.5, color=colors[color_idx % len(colors)],
                                antialiased=True
                            )
                            color_idx += 1

                if self._cancel_event.is_set():
                    render_complete_callback(success=False, cancelled=True)
                    return

                # 渲染点数预算 ≈ 每像素2点，超出部分走min-max降采样：
                # 保留波形包络、避免混叠锯齿，同时大幅减少实际渲染点数
                fig = self.chart_manager.figure
                render_budget = int(fig.get_size_inches()[0] * fig.dpi * 2)
                self.chart_manager.set_max_render_points(render_budget)

                self.chart_manager.set_labels("时间 [s]", "数值", "多文件数据对比")
                self.chart_manager.add_legend()
                self.chart_manager.add_grid()
                self.chart_manager.update()

                render_complete_callback(success=True, cancelled=False)

            except Exception as e:
                error_msg = str(e)
                self.app_context['root'].after(0, lambda: self._on_compare_error(error_msg))

        self.app_context['root'].after(0, do_render)

    def _update_progress(self, current: int, total: int, message: str):
        """更新进度显示"""
        def do_update():
            if total > 0:
                self._progress_bar.config(value=(current / total) * 100)
            self._progress_label.config(text=message)

        self.app_context['root'].after(0, do_update)

    def _on_compare_complete(self, cancelled: bool):
        """对比完成回调"""
        def do_complete():
            self._is_comparing = False
            self._compare_btn.config(state=tk.NORMAL)
            self._cancel_btn.config(state=tk.DISABLED)
            if self._export_btn is not None:
                self._export_btn.config(state=tk.NORMAL)
            self._progress_bar.config(value=0 if cancelled else 100)
            self._progress_label.config(text="已取消" if cancelled else "完成")
            self.compare_status_label.config(
                text="对比已取消" if cancelled else "对比完成"
            )

        self.app_context['root'].after(0, do_complete)

    def _on_compare_error(self, error_msg: str):
        """对比错误回调"""
        def do_error():
            self._is_comparing = False
            self._compare_btn.config(state=tk.NORMAL)
            self._cancel_btn.config(state=tk.DISABLED)
            if self._export_btn is not None:
                self._export_btn.config(state=tk.NORMAL)
            self._progress_label.config(text="错误")
            self.compare_status_label.config(text=f"对比出错: {error_msg}")
            messagebox.showerror("错误", f"对比操作出错:\n{error_msg}")

        self.app_context['root'].after(0, do_error)

    def _export_selected_columns(self):
        """将当前选中的文件和数据列导出为新的CSV文件（宽表并排，完整原始数据）"""
        if self._is_exporting or self._is_comparing:
            return

        selected_files = self.compare_file_listbox.curselection()
        if not selected_files:
            messagebox.showwarning("提示", "请至少选择一个文件")
            return

        selected_columns = self._get_column_requests()
        if not selected_columns:
            messagebox.showwarning("提示", "请至少选择一个数据列")
            return

        file_names = [self.compare_file_listbox.get(i) for i in selected_files]
        output_dir = self.app_context.get('output_dir', '')

        # 导出前检查时间列类型是否一致（轻量读取表头）
        time_col_names = set()
        for file_name in file_names:
            for col in read_csv_header(os.path.join(output_dir, file_name)):
                if is_time_column(col):
                    time_col_names.add(col)
                    break
        if len(time_col_names) > 1:
            names = '、'.join(sorted(time_col_names))
            proceed = messagebox.askokcancel(
                "警告",
                f"选中文件的时间列类型不一致（{names}）。\n"
                "导出将以第一个文件的时间列为准，各文件数据按行号对齐，"
                "时间可能不匹配。\n\n是否继续导出？")
            if not proceed:
                return

        output_path = filedialog.asksaveasfilename(
            title="导出选中数据列",
            defaultextension=".csv",
            initialfile="selected_export.csv",
            initialdir=output_dir or None,
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not output_path:
            return

        self._is_exporting = True
        self._compare_btn.config(state=tk.DISABLED)
        self._export_btn.config(state=tk.DISABLED)
        self._progress_bar.config(value=0)
        self._progress_label.config(text="准备导出...")

        self._export_thread = threading.Thread(
            target=self._async_export,
            args=(file_names, selected_columns, output_path),
            daemon=True
        )
        self._export_thread.start()

    def _async_export(self, file_names: List[str],
                      selected_columns: List[Tuple[str, str]], output_path: str):
        """后台线程：加载选中文件并将选中数据列导出为宽表CSV"""
        try:
            output_dir = self.app_context.get('output_dir', '')
            total_files = len(file_names)

            # 收集各文件数据：仅持有列数据列表引用，
            # 缓存淘汰时loader.data字典被清空也不影响已提取的列表
            file_data = OrderedDict()
            skipped_files = []
            for i, file_name in enumerate(file_names):
                file_path = os.path.join(output_dir, file_name)
                loader = self._get_file_loader(file_path)
                if loader is None:
                    skipped_files.append(file_name)
                    continue

                time_col = loader.get_time_column()
                req_cols = {}
                used_columns = set()
                for req_type, target_col in selected_columns:
                    matching = resolve_matching_column(loader, req_type, target_col, time_col)
                    if matching and matching not in used_columns:
                        used_columns.add(matching)
                        req_cols[(req_type, target_col)] = matching

                file_data[file_name] = {
                    'time_col': time_col,
                    'time_values': loader.data[time_col] if time_col else [],
                    'req_cols': req_cols,
                    'col_values': {req: loader.data[raw]
                                   for req, raw in req_cols.items()},
                }
                self._update_progress(i + 1, total_files,
                                      f"已加载 {i + 1}/{total_files} 个文件")

            # 共用时间列取第一个包含时间列的文件；导出列按文件顺序 × 列请求顺序
            time_source = next((fd for fd in file_data.values() if fd['time_col']), None)
            time_header = time_source['time_col'] if time_source else None
            time_values = time_source['time_values'] if time_source else []

            export_columns = []
            for file_name, fd in file_data.items():
                stem = file_name[:-4] if file_name.lower().endswith('.csv') else file_name
                for req, raw_col in fd['req_cols'].items():
                    export_columns.append((stem, raw_col, fd['col_values'][req]))

            if not export_columns:
                raise RuntimeError("选中的数据列在所有文件中均未匹配到")

            max_rows, col_count = write_export_csv(
                output_path, time_header, time_values, export_columns,
                progress_callback=lambda cur, total: self._update_progress(
                    cur, total, f"正在写入数据 {cur}/{total} 行"))

            summary = (f"数据已成功导出到:\n{output_path}\n\n"
                       f"共 {max_rows} 行 × {col_count} 列")
            if skipped_files:
                summary += f"\n\n以下文件加载失败已跳过: {', '.join(skipped_files)}"
            self._on_export_complete(True, summary)
        except Exception as e:
            self._on_export_complete(False, str(e))

    def _on_export_complete(self, success: bool, message: str):
        """导出完成回调（主线程执行UI更新）"""
        def do_complete():
            self._is_exporting = False
            self._compare_btn.config(state=tk.NORMAL)
            self._export_btn.config(state=tk.NORMAL)
            if success:
                self._progress_bar.config(value=100)
                self._progress_label.config(text="导出完成")
                self.compare_status_label.config(text="导出完成")
                messagebox.showinfo("成功", message)
            else:
                self._progress_bar.config(value=0)
                self._progress_label.config(text="导出失败")
                self.compare_status_label.config(text=f"导出失败: {message}")
                messagebox.showerror("错误", f"导出失败:\n{message}")

        self.app_context['root'].after(0, do_complete)

    def _add_to_cache(self, file_path: str, loader: CSVDataLoader):
        """添加文件到缓存"""
        max_cache_size = 10
        while len(self._loaded_files) >= max_cache_size:
            oldest_key = next(iter(self._loaded_files))
            old_loader = self._loaded_files.pop(oldest_key)
            old_loader.clear()

        self._loaded_files[file_path] = loader

    def _generate_chart(self):
        """生成对比图表（保留兼容性）"""
        selected_files = self.compare_file_listbox.curselection()
        if not selected_files:
            return

        selected_columns = self._get_column_requests()
        if not selected_columns:
            return

        file_names = [self.compare_file_listbox.get(i) for i in selected_files]
        self._start_compare()

    def _on_zoom_changed(self, value):
        """缩放变化事件处理"""
        self.compare_zoom_level = float(value)
        self.compare_zoom_label.config(text=f"{int(self.compare_zoom_level * 100)}%")
        self._debounce_compare_update()

    def _on_scroll_changed(self, value):
        """滚动位置变化事件处理"""
        self.compare_scroll_position = float(value) / 100.0
        self._debounce_compare_update()

    def _debounce_compare_update(self):
        """防抖更新对比图表"""
        if self._is_comparing:
            return

        current_time = time.time() * 1000

        if current_time - self._last_compare_update < self._debounce_delay:
            if not self._compare_update_pending:
                self._compare_update_pending = True
                self.app_context['root'].after(self._debounce_delay, self._do_compare_update)
        else:
            self._do_compare_update()

    def _do_compare_update(self):
        """执行对比图表更新"""
        self._compare_update_pending = False
        self._last_compare_update = time.time() * 1000
        self._generate_chart()

    def _on_mouse_scroll(self, event):
        """鼠标滚轮事件处理"""
        if self._is_comparing:
            return

        if event.inaxes:
            x_mouse = event.xdata
            old_zoom = self.compare_zoom_level

            if event.button == 'up':
                new_zoom = min(5.0, self.compare_zoom_level * 1.1)
            else:
                new_zoom = max(0.1, self.compare_zoom_level / 1.1)

            if abs(new_zoom - old_zoom) < 0.001:
                return

            self.compare_zoom_level = new_zoom

            if x_mouse is not None and len(self._compare_time_data) > 0:
                total_points = len(self._compare_time_data)

                mouse_idx = 0
                for i, t in enumerate(self._compare_time_data):
                    if t is not None and t >= x_mouse:
                        mouse_idx = i
                        break

                visible_points = max(1, int(total_points / self.compare_zoom_level))
                new_start = max(0, min(mouse_idx - visible_points // 2, total_points - visible_points))
                self.compare_scroll_position = new_start / max(1, total_points - visible_points)
                self.compare_scroll_scale.set(self.compare_scroll_position * 100)

            self.compare_zoom_scale.set(self.compare_zoom_level)
            self.compare_zoom_label.config(text=f"{int(self.compare_zoom_level * 100)}%")
            self._generate_chart()

    def _on_mouse_move(self, event):
        """鼠标移动事件处理：更新数据点提示"""
        if self._datatip_var is None or not self._datatip_var.get():
            return
        if not event.inaxes or event.xdata is None or event.ydata is None:
            self.chart_manager.clear_crosshair()
            self.chart_manager.draw_idle()
            return
        self.chart_manager.update_datatip(event.xdata, event.ydata)
        self.chart_manager.draw_idle()

    def _toggle_datatip(self):
        """切换数据点提示显示状态"""
        if self._datatip_var is not None and not self._datatip_var.get():
            self.chart_manager.clear_crosshair()
            self.chart_manager.draw_idle()

    def _reset_zoom(self):
        """重置缩放"""
        self.compare_zoom_level = 1.0
        self.compare_zoom_scale.set(1.0)
        self.compare_zoom_label.config(text="100%")
        self._generate_chart()

    def _reset_scroll(self):
        """重置滚动位置"""
        self.compare_scroll_position = 0.0
        self.compare_scroll_scale.set(0)
        self._generate_chart()

    def cleanup(self):
        """清理资源，防止内存泄漏"""
        self._cancel_event.set()

        if self._compare_thread and self._compare_thread.is_alive():
            self._compare_thread.join(timeout=1.0)

        if self._export_thread and self._export_thread.is_alive():
            self._export_thread.join(timeout=1.0)

        if self.chart_manager:
            self.chart_manager.destroy()
            self.chart_manager = None

        for loader in self._loaded_files.values():
            loader.clear()
        self._loaded_files.clear()
        self._compare_time_data = []

        self._column_pool = {}
        self._pool_file_count = 0
        self._search_results = []
        self._selected_unified_columns = []

    def refresh_files(self):
        """刷新文件列表（公共接口）"""
        self._refresh_files()

    def _get_file_loader(self, file_path: str) -> Optional[CSVDataLoader]:
        """
        获取或创建文件加载器（带缓存）

        Args:
            file_path: CSV文件路径

        Returns:
            CSVDataLoader或None
        """
        if file_path in self._loaded_files:
            self._loaded_files.move_to_end(file_path)
            return self._loaded_files[file_path]

        loader = CSVDataLoader()
        if loader.load(file_path):
            self._add_to_cache(file_path, loader)
            return loader

        return None
