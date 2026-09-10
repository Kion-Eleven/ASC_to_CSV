# asc_to_csv/ui/visualize_tab.py
"""
数据可视化标签页模块
提供CSV数据的可视化功能界面
"""

import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, List, Dict, Any

from .base import BaseTab
from core.csv_loader import CSVDataLoader
from core.chart_manager import ChartManager


class VisualizeTab(BaseTab):
    """
    数据可视化标签页
    
    提供CSV数据的图表可视化功能
    
    Attributes:
        data_loader: CSV数据加载器
        chart_manager: 图表管理器
        current_file: 当前加载的文件路径
        current_column: 当前选择的数据列
    """
    
    def __init__(self, parent: tk.Widget, app_context: dict):
        """
        初始化可视化标签页

        Args:
            parent: 父容器
            app_context: 应用上下文
        """
        self.data_loader = CSVDataLoader()
        self.chart_manager: Optional[ChartManager] = None
        self.current_file: Optional[str] = None
        self.current_column: Optional[str] = None

        self.zoom_level: float = 1.0
        self.scroll_position: float = 0.0
        self.crosshair_enabled: bool = False

        self._all_columns: List[str] = []
        self._search_placeholder: str = "搜索列名..."

        self._chart_update_pending: bool = False
        self._last_chart_update: float = 0
        self._debounce_delay: int = 50

        self._last_mouse_move_time: float = 0
        self._mouse_move_throttle: int = 30

        self._max_data_points: int = 100000
        self._data_warning_shown: bool = False

        # 异步加载相关字段（方案六优化）
        self._load_thread: Optional[threading.Thread] = None
        self._load_cancel_event: threading.Event = threading.Event()
        self._loading_file: Optional[str] = None

        # 方案4优化：跟踪当前图表上下文（文件+列），
        # 仅在上下文变化时才重建 labels/legend/grid，zoom/scroll 只更新数据
        self._last_chart_context: Optional[tuple] = None

        self.file_combo: Optional[ttk.Combobox] = None
        self.column_combo: Optional[ttk.Combobox] = None
        self.column_search_var: Optional[tk.StringVar] = None
        self.column_search_entry: Optional[ttk.Entry] = None
        self.column_search_status: Optional[ttk.Label] = None
        self.zoom_scale: Optional[ttk.Scale] = None
        self.zoom_label: Optional[ttk.Label] = None
        self.scroll_scale: Optional[ttk.Scale] = None
        self.crosshair_var: Optional[tk.BooleanVar] = None
        self.status_label: Optional[ttk.Label] = None
        self.coord_label: Optional[ttk.Label] = None

        super().__init__(parent, app_context)
    
    def on_activate(self):
        """标签页激活：确保图表可见并重绘"""
        super().on_activate()
        if self.chart_manager is not None:
            try:
                self.chart_manager.draw_idle()
            except Exception:
                pass
    
    def _create_widgets(self):
        """创建界面组件"""
        control_frame = ttk.LabelFrame(self, text="控制面板", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 5))
        
        self._create_file_section(control_frame)
        self._create_column_section(control_frame)
        self._create_zoom_section(control_frame)
        
        chart_frame = ttk.LabelFrame(self, text="数据图表", padding="5")
        chart_frame.pack(fill=tk.BOTH, expand=True)
        
        self.chart_manager = ChartManager(chart_frame)
        self.chart_manager.get_widget().pack(fill=tk.BOTH, expand=True)
        self.chart_manager.add_toolbar(chart_frame)
        
        self.chart_manager.bind_scroll(self._on_mouse_scroll)
        self.chart_manager.bind_motion(self._on_mouse_move)
        
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        self.status_label = ttk.Label(status_frame, text="请选择CSV文件")
        self.status_label.pack(side=tk.LEFT)
        self.coord_label = ttk.Label(status_frame, text="")
        self.coord_label.pack(side=tk.RIGHT)
    
    def _create_file_section(self, parent: ttk.Frame):
        """创建文件选择区域"""
        file_frame = ttk.Frame(parent)
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="CSV文件:").pack(side=tk.LEFT)
        self.file_combo = ttk.Combobox(file_frame, width=50, state="readonly")
        self.file_combo.pack(side=tk.LEFT, padx=5)
        self.file_combo.bind("<<ComboboxSelected>>", self._on_file_selected)
        
        ttk.Button(file_frame, text="刷新目录", command=self._refresh_csv_files).pack(side=tk.LEFT, padx=5)
    
    def _create_column_section(self, parent: ttk.Frame):
        """创建数据列选择区域"""
        column_frame = ttk.Frame(parent)
        column_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(column_frame, text="数据列:").pack(side=tk.LEFT)
        
        self.column_search_var = tk.StringVar()
        self.column_search_var.trace_add("write", self._on_column_search_changed)
        self.column_search_entry = ttk.Entry(column_frame, textvariable=self.column_search_var, width=20)
        self.column_search_entry.pack(side=tk.LEFT, padx=5)
        self.column_search_entry.insert(0, self._search_placeholder)
        self.column_search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.column_search_entry.bind("<FocusOut>", self._on_search_focus_out)
        
        self.column_combo = ttk.Combobox(column_frame, width=50, state="readonly")
        self.column_combo.pack(side=tk.LEFT, padx=5)
        self.column_combo.bind("<<ComboboxSelected>>", self._on_column_selected)
        
        self.column_search_status = ttk.Label(column_frame, text="", width=20)
        self.column_search_status.pack(side=tk.LEFT, padx=5)
    
    def _create_zoom_section(self, parent: ttk.Frame):
        """创建缩放控制区域"""
        zoom_frame = ttk.Frame(parent)
        zoom_frame.pack(fill=tk.X, pady=5)

        ttk.Label(zoom_frame, text="缩放:").pack(side=tk.LEFT)
        self.zoom_scale = ttk.Scale(zoom_frame, from_=0.1, to=5.0, value=1.0,
                                     orient=tk.HORIZONTAL, length=150,
                                     command=self._on_zoom_changed)
        self.zoom_scale.pack(side=tk.LEFT, padx=5)
        self.zoom_label = ttk.Label(zoom_frame, text="100%", width=6)
        self.zoom_label.pack(side=tk.LEFT)

        ttk.Button(zoom_frame, text="重置", command=self._reset_zoom).pack(side=tk.LEFT, padx=10)

        ttk.Label(zoom_frame, text="水平滚动:").pack(side=tk.LEFT, padx=(20, 0))
        self.scroll_scale = ttk.Scale(zoom_frame, from_=0, to=100, value=0,
                                       orient=tk.HORIZONTAL, length=150,
                                       command=self._on_scroll_changed)
        self.scroll_scale.pack(side=tk.LEFT, padx=5)

        self.crosshair_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(zoom_frame, text="显示数据提示", variable=self.crosshair_var,
                        command=self._toggle_crosshair).pack(side=tk.LEFT, padx=20)

        self.perf_mode_label = ttk.Label(zoom_frame, text="", foreground="orange", width=15)
        self.perf_mode_label.pack(side=tk.LEFT, padx=5)
    
    def _on_file_selected(self, event):
        """文件选择事件处理"""
        file_name = self.file_combo.get()
        if not file_name:
            return
        
        output_dir = self.app_context.get('output_dir', '')
        if not output_dir:
            return
        
        file_path = os.path.join(output_dir, file_name)
        self._load_csv_file(file_path)
    
    def _load_csv_file(self, file_path: str):
        """加载CSV文件 - 异步版本（后台线程执行，不阻塞UI）

        方案六优化：将耗时的CSV解析放到后台线程，主线程保持响应。
        注意：所有 Tk/matplotlib GUI 操作必须在主线程执行，
        后台线程只做纯数据IO和计算（CSVDataLoader.load()）。
        """
        # 取消上一次正在进行的加载任务
        if self._load_thread and self._load_thread.is_alive():
            self._load_cancel_event.set()
            self._load_thread.join(timeout=0.5)
        self._load_cancel_event.clear()
        self._loading_file = file_path

        # 立即在主线程更新状态提示（非阻塞）
        self.status_label.config(text=f"正在加载: {os.path.basename(file_path)}...")
        # 注意：不再调用 root.update()，它会强制重入事件循环导致卡顿

        def load_worker():
            """后台线程：只做纯数据加载，不触碰任何Tk/matplotlib控件"""
            try:
                loader = CSVDataLoader()
                success = loader.load(file_path)
                # 加载完成后通过 root.after 回到主线程更新UI
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

        所有UI控件操作、图表更新都在这里执行，确保线程安全。
        """
        # 如果当前加载的文件已经不是用户最后选择的文件，忽略旧结果
        if file_path != self._loading_file:
            return

        if not success:
            self.status_label.config(text="加载失败")
            return

        # === 主线程安全操作：清理旧图表资源 ===
        # 注意：切文件前先清空旧图，避免内存累积
        try:
            self.chart_manager.clear()
            self.chart_manager.clear_crosshair()
        except Exception:
            pass
        # 重置图表上下文跟踪（clear 已清掉 axes 全部状态，
        # 需重新设置 labels/legend/grid）
        self._last_chart_context = None

        # 释放旧 data_loader 内存
        if self.data_loader:
            self.data_loader.clear()
        self.data_loader = loader

        self.current_file = file_path

        # 更新列选择控件
        numeric_cols = self.data_loader.get_numeric_columns()
        self._all_columns = numeric_cols

        self.column_combo['values'] = numeric_cols
        if numeric_cols:
            self.column_combo.set(numeric_cols[0])
            self.current_column = numeric_cols[0]

        self.column_search_status.config(text=f"共 {len(numeric_cols)} 列")
        self.column_search_var.set(self._search_placeholder)

        # 更新状态标签和图表
        time_col = self.data_loader.get_time_column()
        if time_col:
            total_points = len(self.data_loader.data.get(time_col, []))
            if total_points > self._max_data_points:
                if not self._data_warning_shown:
                    self.status_label.config(
                        text=f"警告: 数据量过大({total_points}点)，已启用性能模式"
                    )
                    self._data_warning_shown = True
                    self.app_context['root'].after(3000, lambda: self.status_label.config(
                        text=f"已加载: {os.path.basename(file_path)}"
                    ))
                # 即使有警告也更新图表
                self._update_chart()
                return
        self.status_label.config(text=f"已加载: {os.path.basename(file_path)}")
        self._update_chart()

    def _on_load_error(self, error_msg: str, file_path: str):
        """CSV加载错误回调（主线程执行）"""
        if file_path != self._loading_file:
            return
        self.status_label.config(text=f"加载失败: {error_msg[:50]}")
    
    def _on_column_search_changed(self, *args):
        """列搜索内容变化事件处理"""
        search_text = self.column_search_var.get().lower()
        
        if search_text == self._search_placeholder.lower():
            return
        
        if not search_text:
            self.column_combo['values'] = self._all_columns
            self.column_search_status.config(text=f"共 {len(self._all_columns)} 列")
            return
        
        filtered_columns = [col for col in self._all_columns if search_text in col.lower()]
        
        self.column_combo['values'] = filtered_columns
        
        if filtered_columns:
            self.column_search_status.config(text=f"找到 {len(filtered_columns)} 列")
            if len(filtered_columns) == 1:
                self.column_combo.set(filtered_columns[0])
                self.current_column = filtered_columns[0]
                self._update_chart()
        else:
            self.column_search_status.config(text="无匹配结果")
    
    def _on_search_focus_in(self, event):
        """搜索框获得焦点"""
        if self.column_search_var.get() == self._search_placeholder:
            self.column_search_var.set("")
    
    def _on_search_focus_out(self, event):
        """搜索框失去焦点"""
        if not self.column_search_var.get():
            self.column_search_var.set(self._search_placeholder)
    
    def _on_column_selected(self, event):
        """列选择事件处理"""
        self.current_column = self.column_combo.get()
        self._update_chart()
    
    def _on_zoom_changed(self, value):
        """缩放变化事件处理"""
        self.zoom_level = float(value)
        self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
        self._debounce_chart_update()
    
    def _on_scroll_changed(self, value):
        """滚动位置变化事件处理"""
        self.scroll_position = float(value) / 100.0
        self._debounce_chart_update()
    
    def _debounce_chart_update(self):
        """防抖更新图表"""
        current_time = time.time() * 1000
        
        if current_time - self._last_chart_update < self._debounce_delay:
            if not self._chart_update_pending:
                self._chart_update_pending = True
                self.app_context['root'].after(self._debounce_delay, self._do_chart_update)
        else:
            self._do_chart_update()
    
    def _do_chart_update(self):
        """执行图表更新"""
        self._chart_update_pending = False
        self._last_chart_update = time.time() * 1000
        self._update_chart()
    
    def _update_chart(self):
        """更新图表（方案4优化：增量更新）

        原实现每次都 clear() 全图重建（曲线/labels/legend/grid 全部重来），
        zoom/scroll 高频触发时开销大。现改为：
        - 文件/列变化时：clear_all_lines + 重建曲线 + 重设 labels/legend/grid
        - 仅 zoom/scroll 变化时：plot_data_cached 增量更新曲线数据
        """
        if not self.current_column or not self.data_loader.data:
            return

        time_col = self.data_loader.get_time_column()
        if not time_col:
            return

        time_data = self.data_loader.data[time_col]

        total_points = len(time_data)

        if total_points > self._max_data_points:
            self.perf_mode_label.config(text=f"性能模式: {total_points}点")
        else:
            self.perf_mode_label.config(text="")

        # 渲染点数预算 ≈ 每像素2点，超出部分走min-max降采样：
        # 保留波形包络、避免混叠锯齿，同时大幅减少实际渲染点数
        fig = self.chart_manager.figure
        render_budget = int(fig.get_size_inches()[0] * fig.dpi * 2)
        self.chart_manager.set_max_render_points(render_budget)

        visible_points = max(1, int(total_points / self.zoom_level))
        visible_points = min(visible_points, self._max_data_points)

        start_idx = int(self.scroll_position * (total_points - visible_points))
        start_idx = max(0, min(start_idx, total_points - visible_points))
        end_idx = min(start_idx + visible_points, total_points)

        # 判断上下文（文件+列）是否变化
        chart_context = (self.current_file, self.current_column)
        context_changed = chart_context != self._last_chart_context
        if context_changed:
            # 清除旧曲线（保留坐标轴状态），并记录新上下文
            self.chart_manager.clear_all_lines()
            self._last_chart_context = chart_context

        if self.current_column in self.data_loader.data:
            y_data = self.data_loader.data[self.current_column][start_idx:end_idx]
            x_data = time_data[start_idx:end_idx]

            # 短路判断是否存在有效数据（避免构建整个索引列表）
            if any(v is not None for v in y_data):
                label = self.current_column.split('[')[0] if '[' in self.current_column else self.current_column
                label = label.split('::')[-1] if '::' in label else label

                self.chart_manager.plot_data_cached(
                    x_data, y_data, label=label,
                    linewidth=1.5, antialiased=True
                )

        # labels/legend/grid 仅在上下文变化时设置（zoom/scroll时跳过）
        if context_changed:
            self.chart_manager.set_labels(time_col, "数值",
                                           os.path.basename(self.current_file) if self.current_file else "")
            self.chart_manager.add_legend()
            self.chart_manager.add_grid()

        self.chart_manager.clear_crosshair()
        self.chart_manager.update()
    
    def _on_mouse_scroll(self, event):
        """鼠标滚轮事件处理"""
        if event.inaxes:
            x_mouse = event.xdata
            old_zoom = self.zoom_level
            
            if event.button == 'up':
                new_zoom = min(5.0, self.zoom_level * 1.1)
            else:
                new_zoom = max(0.1, self.zoom_level / 1.1)
            
            if abs(new_zoom - old_zoom) < 0.001:
                return
            
            self.zoom_level = new_zoom
            
            if x_mouse is not None and self.data_loader.data:
                time_col = self.data_loader.get_time_column()
                if time_col:
                    time_data = self.data_loader.data[time_col]
                    total_points = len(time_data)
                    
                    if total_points > 0:
                        mouse_idx = 0
                        for i, t in enumerate(time_data):
                            if t is not None and t >= x_mouse:
                                mouse_idx = i
                                break
                        
                        visible_points = max(1, int(total_points / self.zoom_level))
                        new_start = max(0, min(mouse_idx - visible_points // 2, total_points - visible_points))
                        self.scroll_position = new_start / max(1, total_points - visible_points)
                        self.scroll_scale.set(self.scroll_position * 100)
            
            self.zoom_scale.set(self.zoom_level)
            self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
            self._update_chart()
    
    def _on_mouse_move(self, event):
        """鼠标移动事件处理（带节流优化）"""
        current_time = time.time() * 1000
        
        # 节流：限制更新频率
        if current_time - self._last_mouse_move_time < self._mouse_move_throttle:
            return
        
        self._last_mouse_move_time = current_time
        
        if not event.inaxes:
            self.chart_manager.clear_crosshair()
            self.coord_label.config(text="")
            self.chart_manager.draw_idle()
            return
        
        x_mouse, y_mouse = event.xdata, event.ydata
        if x_mouse is None or y_mouse is None:
            return
        
        if self.crosshair_enabled:
            self.chart_manager.update_datatip(x_mouse, y_mouse)
        else:
            self.chart_manager.clear_crosshair()
        self.coord_label.config(text=f"坐标: X={x_mouse:.4f}, Y={y_mouse:.4f}")
        
        self.chart_manager.draw_idle()
    
    def _reset_zoom(self):
        """重置缩放和滚动位置"""
        self.zoom_level = 1.0
        self.scroll_position = 0.0
        self.zoom_scale.set(1.0)
        self.scroll_scale.set(0)
        self.zoom_label.config(text="100%")
        self._update_chart()
    
    def _toggle_crosshair(self):
        """切换十字参考线显示状态"""
        self.crosshair_enabled = self.crosshair_var.get()
        if not self.crosshair_enabled:
            self.chart_manager.clear_crosshair()
            self.coord_label.config(text="")
            self.chart_manager.draw_idle()
    
    def refresh_files(self):
        """刷新文件列表（公共接口）"""
        self._refresh_csv_files()

    def cleanup(self):
        """清理资源，防止内存泄漏"""
        # 先取消后台加载线程
        self._load_cancel_event.set()
        if self._load_thread and self._load_thread.is_alive():
            self._load_thread.join(timeout=1.0)
        self._load_thread = None

        if self.chart_manager:
            self.chart_manager.destroy()
            self.chart_manager = None

        if self.data_loader:
            self.data_loader.clear()
            self.data_loader = None

        self.current_file = None
        self.current_column = None
        self._all_columns = []

    def _refresh_csv_files(self):
        """刷新CSV文件列表"""
        output_dir = self.app_context.get('output_dir', '')
        if not output_dir or not os.path.exists(output_dir):
            return

        csv_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
        self.file_combo['values'] = csv_files

        if csv_files:
            self.file_combo.set(csv_files[0])
            self._on_file_selected(None)
