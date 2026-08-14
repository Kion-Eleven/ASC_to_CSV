# asc_to_csv/core/chart_manager.py
"""
图表管理器模块
负责图表的创建、更新和管理

性能优化版本：
- 支持数据降采样，避免大数据量导致的卡顿
- 限制最大渲染数据点数量
- 优化内存使用
"""

import tkinter as tk
from typing import List, Optional, Tuple, Any
import numpy as np

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from datetime import datetime

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['lines.antialiased'] = True
plt.rcParams['patch.antialiased'] = True

MAX_RENDER_POINTS = 100000
DEFAULT_MAX_POINTS = 5000


class ChartManager:
    """
    图表管理器

    负责图表的创建、更新和交互管理

    Attributes:
        figure: matplotlib Figure对象
        ax: matplotlib Axes对象
        canvas: Tkinter画布
        zoom_level: 缩放级别
        scroll_position: 滚动位置
        max_render_points: 最大渲染数据点数
        _downsample_enabled: 是否启用降采样
        _last_render_time: 上次渲染时间
    """

    def __init__(self, master: tk.Widget, figsize: Tuple[float, float] = (12, 6),
                 max_render_points: int = DEFAULT_MAX_POINTS):
        """
        初始化图表管理器

        Args:
            master: 父容器
            figsize: 图表尺寸
            max_render_points: 最大渲染数据点数
        """
        self.figure = Figure(figsize=figsize, dpi=100)
        self.ax = self.figure.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.figure, master=master)
        self.canvas.draw()

        self.zoom_level: float = 1.0
        self.scroll_position: float = 0.0
        self.max_render_points: int = max_render_points

        self._crosshair_enabled: bool = False
        self._crosshair_vline: Optional[Any] = None
        self._crosshair_hline: Optional[Any] = None
        self._coord_annotation: Optional[Any] = None

        self._downsample_enabled: bool = True
        self._last_render_time: float = 0
        self._min_render_interval: float = 0.033
    
    def get_widget(self) -> tk.Widget:
        """获取画布控件"""
        return self.canvas.get_tk_widget()
    
    def add_toolbar(self, master: tk.Widget) -> NavigationToolbar2Tk:
        """
        添加工具栏
        
        Args:
            master: 父容器
            
        Returns:
            NavigationToolbar2Tk: 工具栏对象
        """
        toolbar_frame = tk.Frame(master)
        toolbar_frame.pack(fill=tk.X)
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.update()
        return toolbar
    
    def clear(self):
        """清除图表"""
        self.ax.clear()
    
    def plot_data(self, x_data: List, y_data: List, label: str = "", 
                  linewidth: float = 1.5, color: Any = None, **kwargs):
        """
        绘制数据曲线
        
        Args:
            x_data: X轴数据
            y_data: Y轴数据
            label: 曲线标签
            linewidth: 线宽
            color: 颜色
            **kwargs: 其他参数
        """
        self.ax.plot(x_data, y_data, label=label, linewidth=linewidth, 
                    color=color, antialiased=True, **kwargs)
    
    def plot_segments(self, x_data: List, y_data: List, label: str = "",
                      max_gap: int = 2, **kwargs):
        """
        分段绘制数据（跳过数据缺失区间）
        包含降采样优化

        Args:
            x_data: X轴数据
            y_data: Y轴数据
            label: 曲线标签
            max_gap: 最大允许间隔
            **kwargs: 其他参数
        """
        if not x_data or not y_data:
            return

        if len(x_data) != len(y_data):
            return

        x_data, y_data = self._downsample_data(x_data, y_data)

        valid_indices = [i for i, v in enumerate(y_data) if v is not None]

        if not valid_indices:
            return

        segments = []
        current_segment = [valid_indices[0]]

        for i in range(1, len(valid_indices)):
            idx = valid_indices[i]
            prev_idx = valid_indices[i-1]

            if idx - prev_idx <= max_gap:
                current_segment.append(idx)
            else:
                segments.append(current_segment)
                current_segment = [idx]

        if current_segment:
            segments.append(current_segment)

        first_segment = True
        for segment in segments:
            if len(segment) > 0:
                x_segment = [x_data[i] for i in segment]
                y_segment = [y_data[i] for i in segment]
                seg_label = label if first_segment else None
                first_segment = False
                self.ax.plot(x_segment, y_segment, label=seg_label, **kwargs)

    def _downsample_data(self, x_data: List, y_data: List) -> Tuple[List, List]:
        """
        降采样数据以优化渲染性能

        Args:
            x_data: X轴数据
            y_data: Y轴数据

        Returns:
            Tuple[List, List]: 降采样后的数据
        """
        total_points = len(x_data)

        if total_points <= self.max_render_points:
            return x_data, y_data

        step = total_points / self.max_render_points
        indices = [int(i * step) for i in range(self.max_render_points)]

        return ([x_data[i] for i in indices], [y_data[i] for i in indices])

    def set_max_render_points(self, max_points: int):
        """
        设置最大渲染数据点数

        Args:
            max_points: 最大数据点数
        """
        self.max_render_points = max(100, min(max_points, MAX_RENDER_POINTS))

    def enable_downsample(self, enabled: bool):
        """
        启用/禁用降采样

        Args:
            enabled: 是否启用
        """
        self._downsample_enabled = enabled

    def should_render(self) -> bool:
        """
        检查是否可以进行渲染（频率限制）

        Returns:
            bool: 是否可以渲染
        """
        import time
        current_time = time.time()

        if current_time - self._last_render_time < self._min_render_interval:
            return False

        self._last_render_time = current_time
        return True
    
    def set_labels(self, xlabel: str, ylabel: str, title: str = ""):
        """
        设置坐标轴标签和标题
        
        Args:
            xlabel: X轴标签
            ylabel: Y轴标签
            title: 图表标题
        """
        self.ax.set_xlabel(xlabel, fontsize=10)
        self.ax.set_ylabel(ylabel, fontsize=10)
        if title:
            self.ax.set_title(title, fontsize=12)
    
    def add_grid(self, linestyle: str = '--', alpha: float = 0.7):
        """
        添加网格
        
        Args:
            linestyle: 线型
            alpha: 透明度
        """
        self.ax.grid(True, linestyle=linestyle, alpha=alpha)
    
    def add_legend(self, loc: str = 'upper right', fontsize: int = 8):
        """
        添加图例
        
        Args:
            loc: 位置
            fontsize: 字体大小
        """
        self.ax.legend(loc=loc, fontsize=fontsize)
    
    def update(self):
        """更新图表显示"""
        self._apply_xaxis_datetime_format()
        self.figure.tight_layout()
        self.canvas.draw()
    
    def draw_idle(self):
        """空闲时重绘"""
        self._apply_xaxis_datetime_format()
        self.canvas.draw_idle()
    
    def _apply_xaxis_datetime_format(self):
        """
        若 X 轴数据为 epoch 秒（2001 年以后的大数值），
        自动将 X 轴格式化为日期时间字符串显示，便于用户阅读。
        """
        try:
            xlim = self.ax.get_xlim()
            if xlim is None:
                return
            x_min, x_max = xlim
            # epoch 秒起始 1e9 ≈ 2001-09-09，小于 1e9 视为相对秒数不格式化
            if x_min is None or x_max is None or x_min < 1e9:
                return

            # 使用 matplotlib 日期格式化器（将 epoch 秒视为 Unix 时间 -> 转换为 matplotlib 日期数）
            # 这里设置 FuncFormatter：显示时用 datetime.fromtimestamp
            def _epoch_formatter(x, pos):
                try:
                    whole = int(x)
                    frac = x - whole
                    # 保留 0.1s 精度
                    frac_digit = int(round(frac * 10)) % 10
                    dt = datetime.fromtimestamp(whole)
                    return dt.strftime('%Y-%m-%d %H:%M:%S') + f'.{frac_digit}'
                except (OSError, OverflowError, ValueError):
                    return f"{x:.1f}"

            from matplotlib.ticker import FuncFormatter
            self.ax.xaxis.set_major_formatter(FuncFormatter(_epoch_formatter))

            # 根据时间跨度选择合理的刻度
            span_sec = x_max - x_min
            if span_sec <= 60:
                # 1分钟以内：按 5-10 个刻度
                step = max(1, int(span_sec / 6))
                if step < 1:
                    step = 1
                self.ax.xaxis.set_major_locator(
                    mdates.SecondLocator(bysecond=range(0, 60, max(1, step)))
                )
                # 手动设置更简单的刻度，避免 DateLocator 对 epoch 不兼容
                from matplotlib.ticker import FixedLocator, MaxNLocator
                self.ax.xaxis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 5, 10]))
            elif span_sec <= 3600:
                from matplotlib.ticker import MaxNLocator
                self.ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
            else:
                from matplotlib.ticker import MaxNLocator
                self.ax.xaxis.set_major_locator(MaxNLocator(nbins=6))

            # X 轴标签旋转避免重叠
            for label in self.ax.get_xticklabels():
                label.set_rotation(15)
                label.set_ha('right')
        except Exception:
            # 格式化失败不影响图表显示
            pass
    
    def bind_scroll(self, callback):
        """
        绑定鼠标滚轮事件
        
        Args:
            callback: 回调函数
        """
        self.canvas.mpl_connect('scroll_event', callback)
    
    def bind_motion(self, callback):
        """
        绑定鼠标移动事件
        
        Args:
            callback: 回调函数
        """
        self.canvas.mpl_connect('motion_notify_event', callback)
    
    def clear_crosshair(self):
        """清除十字参考线"""
        if self._crosshair_vline:
            self._crosshair_vline.remove()
            self._crosshair_vline = None
        if self._crosshair_hline:
            self._crosshair_hline.remove()
            self._crosshair_hline = None
        if self._coord_annotation:
            self._coord_annotation.remove()
            self._coord_annotation = None
    
    def update_crosshair(self, x: float, y: float):
        """
        更新十字参考线位置
        
        Args:
            x: X坐标
            y: Y坐标
        """
        if self._crosshair_vline:
            self._crosshair_vline.set_xdata([x, x])
        else:
            self._crosshair_vline = self.ax.axvline(x=x, color='gray', 
                                                     linestyle='--', linewidth=1, alpha=0.7)
        
        if self._crosshair_hline:
            self._crosshair_hline.set_ydata([y, y])
        else:
            self._crosshair_hline = self.ax.axhline(y=y, color='gray',
                                                     linestyle='--', linewidth=1, alpha=0.7)

    def destroy(self):
        """
        释放图表管理器占用的所有资源

        用于清理matplotlib图表，释放内存，防止内存泄漏。
        应在销毁图表或关闭窗口时调用。
        """
        self.clear_crosshair()

        if hasattr(self, 'ax') and self.ax:
            self.ax.clear()

        if hasattr(self, 'figure') and self.figure:
            self.figure.clear()

        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.get_tk_widget().destroy()
            self.canvas._master = None

        plt.close(self.figure)

    def __del__(self):
        """析构函数，确保资源释放"""
        try:
            if hasattr(self, 'figure') and self.figure:
                plt.close(self.figure)
        except Exception:
            pass
