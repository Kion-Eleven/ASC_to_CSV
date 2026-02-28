# asc_to_csv/main_app.py
"""
ASC to CSV 转换与可视化主程序
整合了数据转换和数据可视化功能
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Optional, Any, Tuple
import csv
import gc
import traceback

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np

try:
    from scipy.interpolate import make_interp_spline
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from config import Config, get_config
from dbc_loader import DBCLoader
from asc_parser import ASCParser
from data_processor import DataProcessor
from csv_writer import CSVWriter


plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['lines.antialiased'] = True
plt.rcParams['patch.antialiased'] = True


MULTI_SELECT_COLUMNS = [
    'MaxCellTemp', 'MinCellTemp', 'PackSOC', 'HvBusVlt', 
    'BranchCrnt', 'PackFltLvl', 'MaxCellVlt', 'MinCellVlt'
]


class CSVDataLoader:
    """CSV数据加载器"""
    
    def __init__(self):
        self.data: Dict[str, List] = {}
        self.columns: List[str] = []
        self.row_count: int = 0
    
    def load(self, file_path: str, encoding: str = 'utf-8-sig') -> bool:
        """加载CSV文件"""
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
            
        except Exception as e:
            print(f"加载文件失败: {e}")
            return False
    
    def get_time_column(self) -> Optional[str]:
        """获取时间列名称"""
        for col in self.columns:
            if 'time' in col.lower():
                return col
        if self.columns:
            return self.columns[0]
        return None
    
    def get_numeric_columns(self) -> List[str]:
        """获取数值型列名称列表"""
        numeric_cols = []
        for col in self.columns:
            if col == self.get_time_column():
                continue
            values = [v for v in self.data[col] if v is not None]
            if values and all(isinstance(v, (int, float)) for v in values):
                numeric_cols.append(col)
        return numeric_cols
    
    def get_multi_select_columns(self) -> List[str]:
        """获取多列显示时可选择的列（仅包含指定的8个列）"""
        numeric_cols = self.get_numeric_columns()
        result = []
        for target in MULTI_SELECT_COLUMNS:
            for col in numeric_cols:
                if target in col:
                    result.append(col)
                    break
        return result


class MainApplication:
    """主应用程序"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ASC to CSV 转换与可视化工具 v2.1.0")
        self.root.geometry("1400x900")
        self.root.minsize(1000, 700)
        
        self.config: Optional[Config] = None
        self._convert_lock = threading.Lock()
        self._is_converting = False
        
        self.data_loader = CSVDataLoader()
        self.current_file: Optional[str] = None
        self.current_column: Optional[str] = None
        self.zoom_level: float = 1.0
        self.scroll_position: float = 0.0
        self.crosshair_enabled: bool = False
        self.output_dir: Optional[str] = None
        self.smooth_curve: bool = True
        
        self.compare_data_loaders: Dict[str, CSVDataLoader] = {}
        self.compare_files: List[str] = []
        self.compare_columns: List[str] = []
        
        self._setup_styles()
        self._create_widgets()
        self._load_config()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    @property
    def is_converting(self) -> bool:
        with self._convert_lock:
            return self._is_converting
    
    @is_converting.setter
    def is_converting(self, value: bool):
        with self._convert_lock:
            self._is_converting = value
    
    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Microsoft YaHei", 12, "bold"))
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self._create_convert_tab()
        self._create_visualize_tab()
        self._create_compare_tab()
    
    def _create_convert_tab(self):
        convert_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(convert_frame, text="数据转换")
        
        title_label = ttk.Label(convert_frame, text="ASC to CSV 转换工具", style="Title.TLabel")
        title_label.pack(pady=(0, 10))
        
        file_frame = ttk.LabelFrame(convert_frame, text="文件设置", padding="10")
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="ASC文件:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.asc_entry = ttk.Entry(file_frame, width=60)
        self.asc_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        ttk.Button(file_frame, text="浏览...", command=self._browse_asc).grid(row=0, column=2, pady=2)
        
        ttk.Label(file_frame, text="DBC文件:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.dbc_frame = ttk.Frame(file_frame)
        self.dbc_frame.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=2)
        
        self.dbc_listbox = tk.Listbox(self.dbc_frame, height=3, selectmode=tk.EXTENDED)
        self.dbc_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        dbc_btn_frame = ttk.Frame(self.dbc_frame)
        dbc_btn_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Button(dbc_btn_frame, text="添加", command=self._add_dbc, width=6).pack(pady=1)
        ttk.Button(dbc_btn_frame, text="删除", command=self._remove_dbc, width=6).pack(pady=1)
        
        ttk.Label(file_frame, text="输出目录:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.output_entry = ttk.Entry(file_frame, width=60)
        self.output_entry.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)
        ttk.Button(file_frame, text="浏览...", command=self._browse_output).grid(row=2, column=2, pady=2)
        
        file_frame.columnconfigure(1, weight=1)
        
        param_frame = ttk.LabelFrame(convert_frame, text="转换参数", padding="10")
        param_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(param_frame, text="采样间隔(秒):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.sample_interval_var = tk.StringVar(value="0.1")
        ttk.Entry(param_frame, textvariable=self.sample_interval_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(param_frame, text="CSV编码:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.encoding_var = tk.StringVar(value="utf-8-sig")
        encoding_combo = ttk.Combobox(param_frame, textvariable=self.encoding_var, width=12, state="readonly")
        encoding_combo["values"] = ("utf-8-sig", "utf-8", "gbk", "gb2312")
        encoding_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(param_frame, text="调试模式", variable=self.debug_var).grid(row=1, column=2, sticky=tk.W, padx=(20, 0), pady=2)
        
        action_frame = ttk.Frame(convert_frame)
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(action_frame, text="保存配置", command=self._save_config, width=12).pack(side=tk.LEFT, padx=5)
        self.convert_btn = ttk.Button(action_frame, text="开始转换", command=self._start_convert, width=15)
        self.convert_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="退出", command=self._on_closing, width=12).pack(side=tk.RIGHT, padx=5)
        
        log_frame = ttk.LabelFrame(convert_frame, text="运行日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _create_visualize_tab(self):
        viz_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(viz_frame, text="数据可视化")
        
        control_frame = ttk.LabelFrame(viz_frame, text="控制面板", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 5))
        
        file_frame = ttk.Frame(control_frame)
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="CSV文件:").pack(side=tk.LEFT)
        self.file_combo = ttk.Combobox(file_frame, width=50, state="readonly")
        self.file_combo.pack(side=tk.LEFT, padx=5)
        self.file_combo.bind("<<ComboboxSelected>>", self._on_file_selected)
        
        ttk.Button(file_frame, text="刷新目录", command=self._refresh_csv_files).pack(side=tk.LEFT, padx=5)
        
        column_frame = ttk.Frame(control_frame)
        column_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(column_frame, text="数据列:").pack(side=tk.LEFT)
        self.column_combo = ttk.Combobox(column_frame, width=50, state="readonly")
        self.column_combo.pack(side=tk.LEFT, padx=5)
        self.column_combo.bind("<<ComboboxSelected>>", self._on_column_selected)
        
        self.multi_select_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(column_frame, text="多列显示", variable=self.multi_select_var, 
                        command=self._on_multi_select_changed).pack(side=tk.LEFT, padx=5)
        
        self.multi_column_frame = ttk.Frame(column_frame)
        
        self.smooth_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(column_frame, text="平滑曲线", variable=self.smooth_var,
                        command=self._update_chart).pack(side=tk.LEFT, padx=5)
        
        zoom_frame = ttk.Frame(control_frame)
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
        ttk.Checkbutton(zoom_frame, text="显示十字参考线", variable=self.crosshair_var,
                        command=self._toggle_crosshair).pack(side=tk.LEFT, padx=20)
        
        chart_frame = ttk.LabelFrame(viz_frame, text="数据图表", padding="5")
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
        self.canvas.mpl_connect('motion_notify_event', self._on_mouse_move)
        
        self.crosshair_vline = None
        self.crosshair_hline = None
        self.coord_annotation = None
        
        status_frame = ttk.Frame(viz_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        self.status_label = ttk.Label(status_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT)
        self.coord_label = ttk.Label(status_frame, text="")
        self.coord_label.pack(side=tk.RIGHT)
    
    def _create_compare_tab(self):
        compare_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(compare_frame, text="数据对比")
        
        control_frame = ttk.LabelFrame(compare_frame, text="对比设置", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 5))
        
        file_frame = ttk.Frame(control_frame)
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="选择文件:").pack(side=tk.LEFT)
        
        self.compare_file_listbox = tk.Listbox(file_frame, height=3, selectmode=tk.MULTIPLE, width=40)
        self.compare_file_listbox.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(file_frame, text="刷新文件", command=self._refresh_compare_files).pack(side=tk.LEFT, padx=5)
        
        column_frame = ttk.Frame(control_frame)
        column_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(column_frame, text="选择数据列:").pack(side=tk.LEFT)
        
        self.compare_column_vars: Dict[str, tk.BooleanVar] = {}
        self.compare_column_frame = ttk.Frame(column_frame)
        self.compare_column_frame.pack(side=tk.LEFT, padx=5)
        
        for i, col_name in enumerate(MULTI_SELECT_COLUMNS):
            var = tk.BooleanVar(value=False)
            self.compare_column_vars[col_name] = var
            cb = ttk.Checkbutton(self.compare_column_frame, text=col_name, variable=var)
            cb.grid(row=0, column=i, padx=5)
        
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="生成对比图", command=self._generate_compare_chart).pack(side=tk.LEFT, padx=5)
        
        self.smooth_compare_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(btn_frame, text="平滑曲线", variable=self.smooth_compare_var).pack(side=tk.LEFT, padx=5)
        
        chart_frame = ttk.LabelFrame(compare_frame, text="对比图表", padding="5")
        chart_frame.pack(fill=tk.BOTH, expand=True)
        
        self.compare_figure = Figure(figsize=(12, 6), dpi=100)
        self.compare_ax = self.compare_figure.add_subplot(111)
        
        self.compare_canvas = FigureCanvasTkAgg(self.compare_figure, master=chart_frame)
        self.compare_canvas.draw()
        
        compare_canvas_widget = self.compare_canvas.get_tk_widget()
        compare_canvas_widget.pack(fill=tk.BOTH, expand=True)
        
        compare_toolbar_frame = ttk.Frame(chart_frame)
        compare_toolbar_frame.pack(fill=tk.X)
        self.compare_toolbar = NavigationToolbar2Tk(self.compare_canvas, compare_toolbar_frame)
        self.compare_toolbar.update()
        
        compare_status_frame = ttk.Frame(compare_frame)
        compare_status_frame.pack(fill=tk.X, pady=(5, 0))
        self.compare_status_label = ttk.Label(compare_status_frame, text="请选择文件和数据列进行对比")
        self.compare_status_label.pack(side=tk.LEFT)
    
    def _log(self, message: str):
        try:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
            self.root.update_idletasks()
        except tk.TclError:
            pass
    
    def _clear_log(self):
        try:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass
    
    def _browse_asc(self):
        filename = filedialog.askopenfilename(title="选择ASC文件", filetypes=[("ASC文件", "*.asc"), ("所有文件", "*.*")])
        if filename:
            self.asc_entry.delete(0, tk.END)
            self.asc_entry.insert(0, filename)
    
    def _add_dbc(self):
        filenames = filedialog.askopenfilenames(title="选择DBC文件", filetypes=[("DBC文件", "*.dbc"), ("所有文件", "*.*")])
        for filename in filenames:
            if filename not in self.dbc_listbox.get(0, tk.END):
                self.dbc_listbox.insert(tk.END, filename)
    
    def _remove_dbc(self):
        selection = self.dbc_listbox.curselection()
        for index in reversed(selection):
            self.dbc_listbox.delete(index)
    
    def _browse_output(self):
        dirname = filedialog.askdirectory(title="选择输出目录")
        if dirname:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, dirname)
    
    def _load_config(self):
        try:
            self.config = get_config()
            if self.config and self.config.asc_file:
                self.asc_entry.insert(0, self.config.asc_file)
                for dbc in self.config.dbc_files:
                    self.dbc_listbox.insert(tk.END, dbc)
                self.output_entry.insert(0, self.config.output_dir)
                self.sample_interval_var.set(str(self.config.sample_interval))
                self.encoding_var.set(self.config.csv_encoding)
                self.debug_var.set(self.config.debug)
                self._log("已加载配置文件")
        except FileNotFoundError:
            self._log("未找到配置文件，将使用默认设置")
        except Exception as e:
            self._log(f"加载配置失败: {type(e).__name__}: {e}")
    
    def _save_config(self):
        import json
        config_data = {
            "asc_file": self.asc_entry.get(),
            "dbc_files": list(self.dbc_listbox.get(0, tk.END)),
            "output_dir": self.output_entry.get(),
            "sample_interval": float(self.sample_interval_var.get()),
            "csv_encoding": self.encoding_var.get(),
            "debug": self.debug_var.get()
        }
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            self._log(f"配置已保存到: {config_path}")
            messagebox.showinfo("成功", "配置保存成功！")
        except Exception as e:
            self._log(f"保存配置失败: {type(e).__name__}: {e}")
            messagebox.showerror("错误", f"保存配置失败: {e}")
    
    def _validate_inputs(self) -> bool:
        asc_file = self.asc_entry.get().strip()
        if not asc_file:
            messagebox.showerror("错误", "请选择ASC文件")
            return False
        if not os.path.exists(asc_file):
            messagebox.showerror("错误", f"ASC文件不存在: {asc_file}")
            return False
        if self.dbc_listbox.size() == 0:
            messagebox.showerror("错误", "请至少添加一个DBC文件")
            return False
        for dbc in self.dbc_listbox.get(0, tk.END):
            if not os.path.exists(dbc):
                messagebox.showerror("错误", f"DBC文件不存在: {dbc}")
                return False
        output_dir = self.output_entry.get().strip()
        if not output_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return False
        try:
            sample_interval = float(self.sample_interval_var.get())
            if sample_interval <= 0:
                messagebox.showerror("错误", "采样间隔必须大于0")
                return False
        except ValueError:
            messagebox.showerror("错误", "采样间隔必须是有效的数字")
            return False
        return True
    
    def _start_convert(self):
        if not self._validate_inputs():
            return
        if self.is_converting:
            messagebox.showwarning("提示", "转换正在进行中，请稍候...")
            return
        
        self.is_converting = True
        self.convert_btn.configure(state=tk.DISABLED)
        self._clear_log()
        
        thread = threading.Thread(target=self._do_convert, daemon=True)
        thread.start()
    
    def _do_convert(self):
        dbc_loader = None
        asc_parser = None
        data_processor = None
        
        try:
            config = Config(
                asc_file=self.asc_entry.get(),
                dbc_files=list(self.dbc_listbox.get(0, tk.END)),
                output_dir=self.output_entry.get(),
                sample_interval=float(self.sample_interval_var.get()),
                csv_encoding=self.encoding_var.get(),
                debug=self.debug_var.get()
            )
            
            self._log("开始转换...")
            self._log(f"采样间隔: {config.sample_interval}秒")
            self._log("")
            
            self._log("正在加载DBC文件...")
            dbc_loader = DBCLoader()
            if not dbc_loader.load(config.dbc_files):
                self._log("DBC文件加载失败")
                return
            
            self._log(f"总消息定义数: {dbc_loader.get_message_count()}")
            self._log(f"总信号定义数: {dbc_loader.get_signal_count()}")
            self._log("")
            
            self._log("正在解析ASC文件...")
            asc_parser = ASCParser(sample_interval=config.sample_interval, debug=config.debug)
            if not asc_parser.parse(config.asc_file, dbc_loader.message_map):
                self._log("ASC文件解析失败")
                return
            
            original_count, sampled_count, signal_count = asc_parser.get_statistics()
            self._log(f"解析完成：原始数据点数: {original_count}, 采样后时间点数: {sampled_count}, 实际信号数: {signal_count}")
            self._log("")
            
            self._log("正在处理数据...")
            data_processor = DataProcessor()
            data_processor.aggregate(asc_parser.sampled_data)
            data_processor.classify_signals(asc_parser.found_signals)
            self._log("")
            
            self._log("正在创建CSV文件...")
            config.create_output_dir()
            csv_writer = CSVWriter(output_dir=config.output_dir, encoding=config.csv_encoding)
            
            created_files = csv_writer.write_all(
                sorted_groups=data_processor.sorted_groups,
                classified_signals=data_processor.classified_signals,
                sorted_timestamps=data_processor.get_sorted_timestamps(),
                aggregated_data=data_processor.aggregated_data,
                signal_info=dbc_loader.signal_info,
                statistics={'original_count': original_count, 'sampled_count': sampled_count, 'signal_count': signal_count}
            )
            
            self._log("")
            self._log("=" * 60)
            self._log("转换完成！")
            self._log(f"输出目录: {config.output_dir}")
            self._log("")
            self._log("生成的文件列表：")
            self._log("-" * 60)
            
            for file_path in created_files:
                file_name = os.path.basename(file_path)
                signal_count = 0
                try:
                    with open(file_path, 'r', encoding=config.csv_encoding) as f:
                        reader = csv.reader(f)
                        header = next(reader)
                        signal_count = len(header) - 1
                except:
                    pass
                self._log(f"  {file_name}: {signal_count} 个信号")
            
            self._log("-" * 60)
            self._log(f"总计生成 {len(created_files)} 个文件")
            self._log("=" * 60)
            
            self.output_dir = config.output_dir
            self.root.after(0, lambda: self._refresh_csv_files())
            self.root.after(0, lambda: self._refresh_compare_files())
            self.root.after(0, lambda: messagebox.showinfo("成功", f"转换完成！\n输出目录: {config.output_dir}"))
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            self._log(f"转换失败: {error_msg}")
            if self.debug_var.get():
                self._log(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("错误", f"转换失败: {error_msg}"))
        
        finally:
            if asc_parser:
                asc_parser.clear()
            if data_processor:
                data_processor.clear()
            gc.collect()
            
            self.is_converting = False
            self.root.after(0, lambda: self.convert_btn.configure(state=tk.NORMAL))
    
    def _refresh_csv_files(self):
        if self.output_dir and os.path.exists(self.output_dir):
            csv_files = [f for f in os.listdir(self.output_dir) if f.endswith('.csv')]
            self.file_combo['values'] = csv_files
            if csv_files:
                self.file_combo.set(csv_files[0])
                self._on_file_selected(None)
    
    def _refresh_compare_files(self):
        if self.output_dir and os.path.exists(self.output_dir):
            csv_files = [f for f in os.listdir(self.output_dir) if f.endswith('.csv')]
            self.compare_file_listbox.delete(0, tk.END)
            for f in csv_files:
                self.compare_file_listbox.insert(tk.END, f)
    
    def _on_file_selected(self, event):
        selected = self.file_combo.get()
        if self.output_dir and selected:
            file_path = os.path.join(self.output_dir, selected)
            if os.path.exists(file_path):
                self._load_csv_file(file_path)
    
    def _load_csv_file(self, file_path: str):
        self.status_label.config(text=f"正在加载: {os.path.basename(file_path)}...")
        self.root.update()
        
        if self.data_loader.load(file_path):
            self.current_file = file_path
            
            if self.multi_select_var.get():
                numeric_cols = self.data_loader.get_multi_select_columns()
            else:
                numeric_cols = self.data_loader.get_numeric_columns()
            
            self.column_combo['values'] = numeric_cols
            if numeric_cols:
                self.column_combo.set(numeric_cols[0])
                self.current_column = numeric_cols[0]
            self._update_chart()
            self.status_label.config(text=f"已加载: {os.path.basename(file_path)}")
        else:
            self.status_label.config(text="加载失败")
    
    def _on_column_selected(self, event):
        self.current_column = self.column_combo.get()
        self._update_chart()
    
    def _on_multi_select_changed(self):
        if self.current_file:
            self._load_csv_file(self.current_file)
    
    def _on_zoom_changed(self, value):
        self.zoom_level = float(value)
        self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
        self._update_chart()
    
    def _on_scroll_changed(self, value):
        self.scroll_position = float(value) / 100.0
        self._update_chart()
    
    def _on_mouse_scroll(self, event):
        if event.inaxes:
            if event.button == 'up':
                self.zoom_level = min(5.0, self.zoom_level * 1.1)
            else:
                self.zoom_level = max(0.1, self.zoom_level / 1.1)
            self.zoom_scale.set(self.zoom_level)
            self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
            self._update_chart()
    
    def _reset_zoom(self):
        self.zoom_level = 1.0
        self.scroll_position = 0.0
        self.zoom_scale.set(1.0)
        self.scroll_scale.set(0)
        self.zoom_label.config(text="100%")
        self._update_chart()
    
    def _toggle_crosshair(self):
        self.crosshair_enabled = self.crosshair_var.get()
        if not self.crosshair_enabled:
            if self.crosshair_vline:
                self.crosshair_vline.remove()
                self.crosshair_vline = None
            if self.crosshair_hline:
                self.crosshair_hline.remove()
                self.crosshair_hline = None
            if self.coord_annotation:
                self.coord_annotation.remove()
                self.coord_annotation = None
            self.coord_label.config(text="")
            self.canvas.draw()
    
    def _on_mouse_move(self, event):
        if not self.crosshair_enabled or not event.inaxes:
            if self.crosshair_vline:
                self.crosshair_vline.remove()
                self.crosshair_vline = None
            if self.crosshair_hline:
                self.crosshair_hline.remove()
                self.crosshair_hline = None
            if self.coord_annotation:
                self.coord_annotation.remove()
                self.coord_annotation = None
            self.coord_label.config(text="")
            self.canvas.draw()
            return
        
        x_mouse, y_mouse = event.xdata, event.ydata
        if x_mouse is None or y_mouse is None:
            return
        
        if self.crosshair_vline:
            self.crosshair_vline.set_xdata([x_mouse, x_mouse])
        else:
            self.crosshair_vline = self.ax.axvline(x=x_mouse, color='gray', linestyle='--', linewidth=1, alpha=0.7)
        
        y_curve = self._get_curve_y_at_x(x_mouse)
        if y_curve is not None:
            y_display = y_curve
            if self.crosshair_hline:
                self.crosshair_hline.set_ydata([y_curve, y_curve])
            else:
                self.crosshair_hline = self.ax.axhline(y=y_curve, color='gray', linestyle='--', linewidth=1, alpha=0.7)
        else:
            y_display = y_mouse
            if self.crosshair_hline:
                self.crosshair_hline.set_ydata([y_mouse, y_mouse])
            else:
                self.crosshair_hline = self.ax.axhline(y=y_mouse, color='gray', linestyle='--', linewidth=1, alpha=0.7)
        
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        x_range = xlim[1] - xlim[0]
        y_range = ylim[1] - ylim[0]
        
        offset_x = x_range * 0.02
        offset_y = y_range * 0.02
        
        annot_x = x_mouse + offset_x
        annot_y = y_display - offset_y
        
        if annot_x > xlim[1] - x_range * 0.15:
            annot_x = x_mouse - x_range * 0.15
        if annot_y < ylim[0] + y_range * 0.1:
            annot_y = y_display + y_range * 0.1
        
        if self.coord_annotation:
            self.coord_annotation.xy = (x_mouse, y_display)
            self.coord_annotation.set_position((annot_x, annot_y))
            self.coord_annotation.set_text(f"X: {x_mouse:.3f}\nY: {y_display:.3f}")
        else:
            self.coord_annotation = self.ax.annotate(
                f"X: {x_mouse:.3f}\nY: {y_display:.3f}",
                xy=(x_mouse, y_display),
                xytext=(annot_x, annot_y),
                fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', edgecolor='gray', alpha=0.9),
                horizontalalignment='left',
                verticalalignment='top'
            )
        
        self.coord_label.config(text=f"坐标: X={x_mouse:.4f}, Y={y_display:.4f}")
        self.canvas.draw_idle()
    
    def _get_curve_y_at_x(self, x_target: float) -> Optional[float]:
        """获取当前图表中曲线在指定x坐标处的y值"""
        if not self.current_column or not self.data_loader.data:
            return None
        
        time_col = self.data_loader.get_time_column()
        if not time_col:
            return None
        
        time_data = self.data_loader.data[time_col]
        
        if self.multi_select_var.get():
            selected_columns = self.data_loader.get_multi_select_columns()
        else:
            selected_columns = [self.current_column]
        
        for col in selected_columns:
            if col in self.data_loader.data:
                y_data = self.data_loader.data[col]
                
                for i, t in enumerate(time_data):
                    if t is not None and abs(t - x_target) < 0.001:
                        if y_data[i] is not None:
                            return y_data[i]
        
        return None
    
    def _smooth_data(self, x_data: List, y_data: List, num_points: int = 300) -> Tuple[np.ndarray, np.ndarray]:
        """使用样条插值平滑数据"""
        if not HAS_SCIPY:
            return np.array(x_data), np.array(y_data)
        
        if len(x_data) < 4:
            return np.array(x_data), np.array(y_data)
        
        x_arr = np.array(x_data)
        y_arr = np.array(y_data)
        
        sort_idx = np.argsort(x_arr)
        x_sorted = x_arr[sort_idx]
        y_sorted = y_arr[sort_idx]
        
        unique_x, unique_idx = np.unique(x_sorted, return_index=True)
        unique_y = y_sorted[unique_idx]
        
        if len(unique_x) < 4:
            return unique_x, unique_y
        
        try:
            x_new = np.linspace(unique_x.min(), unique_x.max(), num_points)
            spline = make_interp_spline(unique_x, unique_y, k=3)
            y_new = spline(x_new)
            return x_new, y_new
        except:
            return unique_x, unique_y
    
    def _update_chart(self):
        if not self.current_column or not self.data_loader.data:
            return
        
        self.ax.clear()
        
        time_col = self.data_loader.get_time_column()
        if not time_col:
            return
        
        time_data = self.data_loader.data[time_col]
        
        if self.multi_select_var.get():
            selected_columns = self.data_loader.get_multi_select_columns()
        else:
            selected_columns = [self.current_column]
        
        total_points = len(time_data)
        visible_points = max(1, int(total_points / self.zoom_level))
        
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
                    label = label.split('::')[-1] if '::' in label else label
                    
                    if self.smooth_var.get() and len(x_valid) > 10:
                        x_smooth, y_smooth = self._smooth_data(x_valid, y_valid)
                        self.ax.plot(x_smooth, y_smooth, label=label, linewidth=2, antialiased=True)
                    else:
                        self.ax.plot(x_valid, y_valid, label=label, linewidth=1.5, antialiased=True)
        
        self.ax.set_xlabel(time_col, fontsize=10)
        self.ax.set_ylabel("数值", fontsize=10)
        
        if self.current_file:
            self.ax.set_title(os.path.basename(self.current_file), fontsize=12)
        
        if len(selected_columns) > 1:
            self.ax.legend(loc='upper right', fontsize=8)
        
        self.ax.grid(True, linestyle='--', alpha=0.7)
        
        self.crosshair_vline = None
        self.crosshair_hline = None
        self.coord_annotation = None
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def _generate_compare_chart(self):
        selected_files = self.compare_file_listbox.curselection()
        if not selected_files:
            messagebox.showwarning("提示", "请至少选择一个文件")
            return
        
        selected_columns = [col for col, var in self.compare_column_vars.items() if var.get()]
        if not selected_columns:
            messagebox.showwarning("提示", "请至少选择一个数据列")
            return
        
        self.compare_ax.clear()
        
        colors = plt.cm.tab10.colors
        color_idx = 0
        
        file_names = [self.compare_file_listbox.get(i) for i in selected_files]
        
        for file_name in file_names:
            file_path = os.path.join(self.output_dir, file_name)
            loader = CSVDataLoader()
            
            if not loader.load(file_path):
                continue
            
            time_col = loader.get_time_column()
            if not time_col:
                continue
            
            time_data = loader.data[time_col]
            
            for target_col in selected_columns:
                matching_col = None
                for col in loader.columns:
                    if target_col in col:
                        matching_col = col
                        break
                
                if not matching_col:
                    continue
                
                y_data = loader.data[matching_col]
                valid_indices = [i for i, v in enumerate(y_data) if v is not None]
                
                if valid_indices:
                    x_valid = [time_data[i] for i in valid_indices]
                    y_valid = [y_data[i] for i in valid_indices]
                    
                    label = f"{file_name.replace('.csv', '')} - {target_col}"
                    
                    if self.smooth_compare_var.get() and len(x_valid) > 10:
                        x_smooth, y_smooth = self._smooth_data(x_valid, y_valid)
                        self.compare_ax.plot(x_smooth, y_smooth, label=label, 
                                            linewidth=2, color=colors[color_idx % len(colors)],
                                            antialiased=True)
                    else:
                        self.compare_ax.plot(x_valid, y_valid, label=label, 
                                            linewidth=1.5, color=colors[color_idx % len(colors)],
                                            antialiased=True)
                    color_idx += 1
        
        self.compare_ax.set_xlabel("时间 [s]", fontsize=10)
        self.compare_ax.set_ylabel("数值", fontsize=10)
        self.compare_ax.set_title("多文件数据对比", fontsize=12)
        self.compare_ax.legend(loc='upper right', fontsize=8)
        self.compare_ax.grid(True, linestyle='--', alpha=0.7)
        
        self.compare_figure.tight_layout()
        self.compare_canvas.draw()
        
        self.compare_status_label.config(text=f"已生成对比图 - 文件: {len(file_names)}, 数据列: {len(selected_columns)}")
    
    def _on_closing(self):
        if self.is_converting:
            if messagebox.askyesno("确认", "转换正在进行中，确定要退出吗？"):
                self.root.quit()
        else:
            self.root.quit()


def main():
    root = tk.Tk()
    app = MainApplication(root)
    root.mainloop()


if __name__ == "__main__":
    main()
