# asc_to_csv/data_visualizer.py
"""
数据可视化模块
提供CSV数据折线图可视化功能
"""

import os
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib
matplotlib.use('TkAgg')


class CSVDataLoader:
    """
    CSV数据加载器
    
    负责加载CSV文件并解析数据
    """
    
    def __init__(self):
        self.data: Dict[str, List] = {}
        self.columns: List[str] = []
        self.row_count: int = 0
    
    def load(self, file_path: str, encoding: str = 'utf-8-sig') -> bool:
        """
        加载CSV文件
        
        Args:
            file_path: CSV文件路径
            encoding: 文件编码
            
        Returns:
            bool: 是否成功加载
        """
        self.data = {}
        self.columns = []
        self.row_count = 0
        
        try:
            with open(file_path, 'r', newline='', encoding=encoding) as f:
                reader = csv.reader(f)
                self.columns = next(reader)
                
                for col in self.columns:
                    self.data[col] = []
                
                for row in reader:
                    if len(row) == 0:
                        continue
                    
                    self.row_count += 1
                    for i, col in enumerate(self.columns):
                        if i < len(row):
                            value = row[i].strip()
                            try:
                                if value == '':
                                    self.data[col].append(None)
                                else:
                                    self.data[col].append(float(value))
                            except ValueError:
                                self.data[col].append(value)
                        else:
                            self.data[col].append(None)
            
            return True
            
        except FileNotFoundError:
            print(f"文件不存在: {file_path}")
            return False
        except Exception as e:
            print(f"加载文件失败: {e}")
            return False
    
    def get_time_column(self) -> Optional[str]:
        """
        获取时间列名称
        
        Returns:
            Optional[str]: 时间列名称
        """
        for col in self.columns:
            if 'time' in col.lower():
                return col
        if self.columns:
            return self.columns[0]
        return None
    
    def get_numeric_columns(self) -> List[str]:
        """
        获取数值型列名称列表
        
        Returns:
            List[str]: 数值型列名称列表
        """
        numeric_cols = []
        for col in self.columns:
            if col == self.get_time_column():
                continue
            values = [v for v in self.data[col] if v is not None]
            if values and all(isinstance(v, (int, float)) for v in values):
                numeric_cols.append(col)
        return numeric_cols


class DataVisualizerApp:
    """
    数据可视化应用
    
    提供CSV数据折线图可视化功能
    """
    
    def __init__(self, root: tk.Tk):
        """
        初始化可视化应用
        
        Args:
            root: Tkinter根窗口
        """
        self.root = root
        self.root.title("CSV数据可视化工具 v1.0.0")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        self.data_loader = CSVDataLoader()
        self.current_file: Optional[str] = None
        self.current_column: Optional[str] = None
        self.zoom_level: float = 1.0
        self.scroll_position: float = 0.0
        
        self._setup_styles()
        self._create_widgets()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Microsoft YaHei", 12, "bold"))
        style.configure("Status.TLabel", font=("Microsoft YaHei", 9))
    
    def _create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._create_control_panel(main_frame)
        self._create_chart_area(main_frame)
        self._create_status_bar(main_frame)
    
    def _create_control_panel(self, parent):
        """创建控制面板"""
        control_frame = ttk.LabelFrame(parent, text="控制面板", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 5))
        
        file_frame = ttk.Frame(control_frame)
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="CSV文件:").pack(side=tk.LEFT)
        
        self.file_combo = ttk.Combobox(file_frame, width=50, state="readonly")
        self.file_combo.pack(side=tk.LEFT, padx=5)
        self.file_combo.bind("<<ComboboxSelected>>", self._on_file_selected)
        
        ttk.Button(file_frame, text="选择目录", command=self._select_directory).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="选择文件", command=self._select_file).pack(side=tk.LEFT, padx=5)
        
        column_frame = ttk.Frame(control_frame)
        column_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(column_frame, text="数据列:").pack(side=tk.LEFT)
        
        self.column_combo = ttk.Combobox(column_frame, width=50, state="readonly")
        self.column_combo.pack(side=tk.LEFT, padx=5)
        self.column_combo.bind("<<ComboboxSelected>>", self._on_column_selected)
        
        self.multi_select_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(column_frame, text="多列显示", variable=self.multi_select_var, 
                        command=self._on_multi_select_changed).pack(side=tk.LEFT, padx=5)
        
        zoom_frame = ttk.Frame(control_frame)
        zoom_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(zoom_frame, text="缩放:").pack(side=tk.LEFT)
        
        self.zoom_scale = ttk.Scale(zoom_frame, from_=0.1, to=5.0, value=1.0, 
                                    orient=tk.HORIZONTAL, length=200,
                                    command=self._on_zoom_changed)
        self.zoom_scale.pack(side=tk.LEFT, padx=5)
        
        self.zoom_label = ttk.Label(zoom_frame, text="100%", width=6)
        self.zoom_label.pack(side=tk.LEFT)
        
        ttk.Button(zoom_frame, text="重置", command=self._reset_zoom).pack(side=tk.LEFT, padx=10)
        
        ttk.Label(zoom_frame, text="水平滚动:").pack(side=tk.LEFT, padx=(20, 0))
        
        self.scroll_scale = ttk.Scale(zoom_frame, from_=0, to=100, value=0,
                                      orient=tk.HORIZONTAL, length=200,
                                      command=self._on_scroll_changed)
        self.scroll_scale.pack(side=tk.LEFT, padx=5)
    
    def _create_chart_area(self, parent):
        """创建图表区域"""
        chart_frame = ttk.LabelFrame(parent, text="数据图表", padding="5")
        chart_frame.pack(fill=tk.BOTH, expand=True)
        
        self.figure = Figure(figsize=(12, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.draw()
        
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)
        
        toolbar_frame = ttk.Frame(chart_frame)
        toolbar_frame.pack(fill=tk.X)
        
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()
        
        self.canvas.mpl_connect('scroll_event', self._on_mouse_scroll)
    
    def _create_status_bar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.status_label = ttk.Label(status_frame, text="就绪", style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT)
        
        self.info_label = ttk.Label(status_frame, text="", style="Status.TLabel")
        self.info_label.pack(side=tk.RIGHT)
    
    def _select_directory(self):
        """选择包含CSV文件的目录"""
        directory = filedialog.askdirectory(title="选择CSV文件目录")
        if directory:
            csv_files = [f for f in os.listdir(directory) if f.endswith('.csv')]
            if csv_files:
                self.csv_directory = directory
                self.file_combo['values'] = csv_files
                self.file_combo.set(csv_files[0])
                self._on_file_selected(None)
            else:
                messagebox.showwarning("提示", "所选目录中没有CSV文件")
    
    def _select_file(self):
        """选择单个CSV文件"""
        file_path = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if file_path:
            self.current_file = file_path
            self.file_combo['values'] = [os.path.basename(file_path)]
            self.file_combo.set(os.path.basename(file_path))
            self._load_file(file_path)
    
    def _on_file_selected(self, event):
        """文件选择事件处理"""
        selected = self.file_combo.get()
        if hasattr(self, 'csv_directory'):
            file_path = os.path.join(self.csv_directory, selected)
        else:
            file_path = self.current_file
        
        if file_path and os.path.exists(file_path):
            self._load_file(file_path)
    
    def _load_file(self, file_path: str):
        """
        加载CSV文件
        
        Args:
            file_path: 文件路径
        """
        self.status_label.config(text=f"正在加载: {os.path.basename(file_path)}...")
        self.root.update()
        
        if self.data_loader.load(file_path):
            self.current_file = file_path
            
            numeric_cols = self.data_loader.get_numeric_columns()
            self.column_combo['values'] = numeric_cols
            
            if numeric_cols:
                self.column_combo.set(numeric_cols[0])
                self.current_column = numeric_cols[0]
            
            self._update_chart()
            
            self.status_label.config(text=f"已加载: {os.path.basename(file_path)}")
            self.info_label.config(text=f"数据行数: {self.data_loader.row_count}, 数值列数: {len(numeric_cols)}")
        else:
            self.status_label.config(text="加载失败")
            messagebox.showerror("错误", f"无法加载文件: {file_path}")
    
    def _on_column_selected(self, event):
        """列选择事件处理"""
        self.current_column = self.column_combo.get()
        self._update_chart()
    
    def _on_multi_select_changed(self):
        """多列显示选项变更"""
        self._update_chart()
    
    def _on_zoom_changed(self, value):
        """缩放滑块变更"""
        self.zoom_level = float(value)
        self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
        self._update_chart()
    
    def _on_scroll_changed(self, value):
        """滚动滑块变更"""
        self.scroll_position = float(value) / 100.0
        self._update_chart()
    
    def _on_mouse_scroll(self, event):
        """鼠标滚轮事件"""
        if event.inaxes:
            if event.button == 'up':
                self.zoom_level = min(5.0, self.zoom_level * 1.1)
            else:
                self.zoom_level = max(0.1, self.zoom_level / 1.1)
            
            self.zoom_scale.set(self.zoom_level)
            self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
            self._update_chart()
    
    def _reset_zoom(self):
        """重置缩放"""
        self.zoom_level = 1.0
        self.scroll_position = 0.0
        self.zoom_scale.set(1.0)
        self.scroll_scale.set(0)
        self.zoom_label.config(text="100%")
        self._update_chart()
    
    def _update_chart(self):
        """更新图表"""
        if not self.current_column or not self.data_loader.data:
            return
        
        self.ax.clear()
        
        time_col = self.data_loader.get_time_column()
        if not time_col:
            return
        
        time_data = self.data_loader.data[time_col]
        
        if self.multi_select_var.get():
            selected_columns = list(self.column_combo['values'])[:10]
        else:
            selected_columns = [self.current_column]
        
        total_points = len(time_data)
        visible_points = int(total_points / self.zoom_level)
        
        start_idx = int(self.scroll_position * (total_points - visible_points))
        start_idx = max(0, min(start_idx, total_points - visible_points))
        end_idx = min(start_idx + visible_points, total_points)
        
        for col in selected_columns:
            if col in self.data_loader.data:
                y_data = self.data_loader.data[col][start_idx:end_idx]
                x_data = time_data[start_idx:end_idx]
                
                valid_indices = [i for i, v in enumerate(y_data) if v is not None]
                if valid_indices:
                    x_valid = [x_data[i] for i in valid_indices]
                    y_valid = [y_data[i] for i in valid_indices]
                    
                    label = col.split('[')[0] if '[' in col else col
                    self.ax.plot(x_valid, y_valid, label=label, linewidth=1)
        
        self.ax.set_xlabel(time_col, fontsize=10)
        self.ax.set_ylabel("数值", fontsize=10)
        self.ax.set_title(f"数据可视化 - {os.path.basename(self.current_file) if self.current_file else ''}", fontsize=12)
        
        if len(selected_columns) > 1:
            self.ax.legend(loc='upper right', fontsize=8)
        
        self.ax.grid(True, linestyle='--', alpha=0.7)
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def _on_closing(self):
        """窗口关闭处理"""
        self.root.quit()


def main():
    """主函数"""
    root = tk.Tk()
    app = DataVisualizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
