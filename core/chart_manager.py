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
from matplotlib.transforms import ScaledTranslation
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

        # 数据点提示元素：垂直虚线、加粗标记点、坐标标注
        self._crosshair_vline: Optional[Any] = None
        self._datatip_marker: Optional[Any] = None
        self._coord_annotation: Optional[Any] = None

        # 方案3优化：增量绘制缓存
        # key: 曲线label, value: 该label对应的Line2D对象列表（分段时多个）
        self._line_cache: dict = {}
    
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
        """清除图表（方案3优化：同步清空曲线缓存，避免持有失效的Line2D引用）"""
        # ax.clear() 会移除所有 artist（含数据点提示元素），这里仅重置引用
        self._crosshair_vline = None
        self._datatip_marker = None
        self._coord_annotation = None
        self._line_cache.clear()
        self.ax.clear()

    def clear_all_lines(self):
        """
        仅清除缓存的曲线，保留坐标轴标签/网格/图例等设置（方案3新增）

        用于切换文件/切换列的场景，配合 plot_data_cached 使用：
        相比 clear() 不会重置 axes 状态，避免重复设置 labels/legend/grid。
        """
        for lines in self._line_cache.values():
            for line in lines:
                try:
                    line.remove()
                except Exception:
                    pass
        self._line_cache.clear()
    
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

        segments = self._build_segments(y_data, max_gap)

        first_segment = True
        for segment in segments:
            if len(segment) > 0:
                x_segment = [x_data[i] for i in segment]
                y_segment = [y_data[i] for i in segment]
                seg_label = label if first_segment else None
                first_segment = False
                self.ax.plot(x_segment, y_segment, label=seg_label, **kwargs)

    def plot_data_cached(self, x_data: List, y_data: List, label: str = "",
                         max_gap: int = 2, **kwargs):
        """
        增量绘制数据曲线（方案3新增）

        与 plot_segments 行为一致（分段+降采样），但增加增量复用：
        当该label已缓存的曲线分段数与新数据一致时，直接复用已有
        Line2D对象调用 set_data 更新数据，避免销毁/重建曲线对象。

        适用于 zoom/scroll 等高频更新场景（数据形状基本不变）。

        Args:
            x_data: X轴数据
            y_data: Y轴数据
            label: 曲线标签
            max_gap: 最大允许间隔
            **kwargs: 其他参数（仅重建时使用）
        """
        if not x_data or not y_data:
            return

        if len(x_data) != len(y_data):
            return

        # 数据即将变化，清除吸附在旧数据上的十字光标，
        # 避免其旧坐标参与 relim 污染坐标范围
        self.clear_crosshair()

        x_data, y_data = self._downsample_data(x_data, y_data)

        segments = self._build_segments(y_data, max_gap)
        if not segments:
            return

        cached_lines = self._line_cache.get(label)

        # 增量复用：分段数一致时仅更新数据
        if cached_lines is not None and len(cached_lines) == len(segments):
            for seg, line in zip(segments, cached_lines):
                line.set_data([x_data[i] for i in seg],
                              [y_data[i] for i in seg])
        else:
            # 分段数变化：移除旧线并重建该label的曲线
            if cached_lines:
                for old_line in cached_lines:
                    try:
                        old_line.remove()
                    except Exception:
                        pass

            new_lines = []
            first_segment = True
            for segment in segments:
                if len(segment) > 0:
                    x_segment = [x_data[i] for i in segment]
                    y_segment = [y_data[i] for i in segment]
                    seg_label = label if first_segment else None
                    first_segment = False
                    line, = self.ax.plot(x_segment, y_segment,
                                         label=seg_label, **kwargs)
                    new_lines.append(line)

            self._line_cache[label] = new_lines

        # 坐标范围必须随数据窗口刷新，原因有二：
        # 1) set_data 增量更新不会触发坐标轴自动缩放，若不重算范围，
        #    放大后曲线只占画面左侧、右侧空白；
        # 2) 工具栏"zoom to rectangle"/平移会关闭坐标轴自动缩放，
        #    重新启用后"重置"按钮才能恢复标准视图。
        self.ax.set_autoscale_on(True)
        self.ax.relim()
        self.ax.autoscale_view()

    def _build_segments(self, y_data: List, max_gap: int = 2) -> List[List[int]]:
        """
        构建有效数据段的索引列表（跳过None缺口，方案3从plot_segments提取）

        Args:
            y_data: Y轴数据（可含None）
            max_gap: 相邻有效索引最大允许间隔

        Returns:
            List[List[int]]: 分段索引列表，无有效数据时为空列表
        """
        valid_indices = [i for i, v in enumerate(y_data) if v is not None]

        if not valid_indices:
            return []

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

        return segments

    def _downsample_data(self, x_data: List, y_data: List) -> Tuple[List, List]:
        """
        min-max 降采样：将数据分成若干桶，每桶仅保留最小值和最大值两个点

        相比等间隔抽样：
        - 完整保留波形包络，尖峰/毛刺不会被跳过
        - 消除高密度绘制时的混叠锯齿（点数远超像素数导致的视觉失真）
        - 渲染点数可控（约每像素2个点），保证缩放/滚动流畅

        Args:
            x_data: X轴数据
            y_data: Y轴数据（可含None表示缺失）

        Returns:
            Tuple[List, List]: 降采样后的数据
        """
        total_points = len(x_data)

        if total_points <= self.max_render_points:
            return x_data, y_data

        bucket_count = max(1, self.max_render_points // 2)
        bucket_size = total_points / bucket_count

        out_x: List = []
        out_y: List = []
        for b in range(bucket_count):
            start = int(b * bucket_size)
            end = max(start + 1, int((b + 1) * bucket_size))

            min_v = None
            max_v = None
            min_i = -1
            max_i = -1
            for i in range(start, end):
                v = y_data[i]
                if v is None:
                    continue
                if min_v is None or v < min_v:
                    min_v = v
                    min_i = i
                if max_v is None or v > max_v:
                    max_v = v
                    max_i = i

            if min_i < 0:
                continue  # 整桶均为缺失值，跳过以保留断点

            # 按原始索引顺序输出，保证线形不失真
            if min_i <= max_i:
                out_x.append(x_data[min_i])
                out_y.append(y_data[min_i])
                if max_i != min_i:
                    out_x.append(x_data[max_i])
                    out_y.append(y_data[max_i])
            else:
                out_x.append(x_data[max_i])
                out_y.append(y_data[max_i])
                out_x.append(x_data[min_i])
                out_y.append(y_data[min_i])

        return out_x, out_y

    def set_max_render_points(self, max_points: int):
        """
        设置最大渲染数据点数

        Args:
            max_points: 最大数据点数
        """
        self.max_render_points = max(100, min(max_points, MAX_RENDER_POINTS))

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
        """更新图表显示（方案3优化：draw_idle异步重绘）
        
        相比 canvas.draw() 的同步全量重绘，draw_idle 将绘制排入
        事件循环空闲时机，高频调用（zoom/scroll防抖后）会自动合并，
        避免阻塞Tk主线程造成卡顿。
        """
        self._apply_xaxis_datetime_format()
        self.figure.tight_layout()
        self.canvas.draw_idle()
    
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
        """清除数据点提示（垂直虚线、加粗标记点和坐标标注）"""
        for attr in ('_crosshair_vline', '_datatip_marker', '_coord_annotation'):
            artist = getattr(self, attr, None)
            if artist is not None:
                try:
                    artist.remove()
                except Exception:
                    pass
                setattr(self, attr, None)

    def update_datatip(self, x_mouse: float, y_mouse: float) -> Optional[Tuple[float, float]]:
        """
        更新数据点提示

        从鼠标指针向曲线引一条垂直虚线（X 吸附到曲线上最近的真实采样点），
        虚线与曲线的交点加粗标记，并在旁边标注该点坐标（时间 + 数值）。
        多条曲线时只标记在吸附X处Y值与鼠标最接近的一条曲线。

        Args:
            x_mouse: 鼠标X坐标（数据坐标）
            y_mouse: 鼠标Y坐标（数据坐标）

        Returns:
            Optional[Tuple[float, float]]: 吸附到的数据点 (x, y)，无有效曲线时为 None
        """
        best = None  # (Y距离, x, y, 曲线颜色)
        for line in self.ax.lines:
            if line is self._crosshair_vline or line is self._datatip_marker:
                continue
            try:
                xs = np.asarray(line.get_xdata(), dtype=float)
                ys = np.asarray(line.get_ydata(), dtype=float)
            except (TypeError, ValueError):
                continue
            if len(xs) == 0:
                continue
            mask = np.isfinite(xs) & np.isfinite(ys)
            if not mask.any():
                continue
            xs, ys = xs[mask], ys[mask]
            idx = int(np.argmin(np.abs(xs - x_mouse)))
            dist_y = abs(float(ys[idx]) - y_mouse)
            if best is None or dist_y < best[0]:
                best = (dist_y, float(xs[idx]), float(ys[idx]), line.get_color())

        if best is None:
            self.clear_crosshair()
            return None

        _, x_pt, y_pt, color = best

        # 垂直虚线：从鼠标指针指向数据点
        if self._crosshair_vline is not None:
            self._crosshair_vline.set_data([x_pt, x_pt], [y_mouse, y_pt])
        else:
            self._crosshair_vline, = self.ax.plot(
                [x_pt, x_pt], [y_mouse, y_pt],
                color='gray', linestyle='--', linewidth=1, alpha=0.8, zorder=5)

        # 加粗标记数据点
        if self._datatip_marker is not None:
            self._datatip_marker.set_data([x_pt], [y_pt])
            self._datatip_marker.set_color(color)
        else:
            self._datatip_marker, = self.ax.plot(
                [x_pt], [y_pt], linestyle='None', marker='o', markersize=7,
                color=color, markeredgecolor='white', markeredgewidth=1.2, zorder=6)

        # 坐标标注（靠近右边缘时翻转到左侧，避免被裁剪）
        if self._coord_annotation is None:
            self._coord_annotation = self.ax.text(x_pt, y_pt, '', fontsize=9)
        self._coord_annotation.set_text(self._format_datatip_text(x_pt, y_pt))
        self._coord_annotation.set_position((x_pt, y_pt))
        self._coord_annotation.set_color(color)
        x_min, x_max = self.ax.get_xlim()
        near_right = x_max > x_min and (x_max - x_pt) < (x_pt - x_min)
        dx = -8 if near_right else 8
        offset_tr = ScaledTranslation(dx / 72, 8 / 72, self.figure.dpi_scale_trans)
        self._coord_annotation.set_transform(self.ax.transData + offset_tr)
        self._coord_annotation.set_ha('right' if near_right else 'left')

        return (x_pt, y_pt)

    @staticmethod
    def _format_datatip_text(x: float, y: float) -> str:
        """格式化数据点提示文本：时间为 MM-DD HH:MM:SS（epoch秒）或数值"""
        x_text = f"{x:.2f}"
        if x >= 1e9:  # 与 _apply_xaxis_datetime_format 一致：epoch 秒视为时间
            try:
                dt = datetime.fromtimestamp(x)
                x_text = dt.strftime('%m-%d %H:%M:%S')
            except (OSError, OverflowError, ValueError):
                pass
        return f"{x_text}, {y:.6g}"

    def destroy(self):
        """
        释放图表管理器占用的所有资源

        用于清理matplotlib图表，释放内存，防止内存泄漏。
        应在销毁图表或关闭窗口时调用。
        """
        self.clear_crosshair()
        self._line_cache.clear()

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
