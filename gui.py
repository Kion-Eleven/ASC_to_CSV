# asc_to_csv/gui.py
"""
图形用户界面模块
提供可视化的操作界面
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional
import traceback
import gc

from config import Config, get_config, resolve_path


class ASCToCSVApp:
    """
    ASC to CSV 转换器图形界面
    
    提供文件选择、参数配置和转换操作的图形界面
    """
    
    def __init__(self, root: tk.Tk):
        """
        初始化GUI应用
        
        Args:
            root: Tkinter根窗口
        """
        self.root = root
        self.root.title("ASC to CSV 转换工具 v1.2.0")
        self.root.geometry("700x650")
        self.root.resizable(True, True)
        
        self.config: Optional[Config] = None
        self._convert_lock = threading.Lock()
        self._is_converting = False
        
        self._setup_styles()
        self._create_widgets()
        self._load_config()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    @property
    def is_converting(self) -> bool:
        """线程安全的转换状态检查"""
        with self._convert_lock:
            return self._is_converting
    
    @is_converting.setter
    def is_converting(self, value: bool):
        """线程安全的转换状态设置"""
        with self._convert_lock:
            self._is_converting = value
    
    def _setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Microsoft YaHei", 14, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Microsoft YaHei", 10, "bold"))
        style.configure("Action.TButton", font=("Microsoft YaHei", 10))
    
    def _create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(
            main_frame, 
            text="ASC to CSV 转换工具",
            style="Title.TLabel"
        )
        title_label.pack(pady=(0, 10))
        
        self._create_file_section(main_frame)
        self._create_param_section(main_frame)
        self._create_action_section(main_frame)
        self._create_log_section(main_frame)
    
    def _create_file_section(self, parent):
        """创建文件选择区域"""
        file_frame = ttk.LabelFrame(parent, text="文件设置", style="Section.TLabelframe", padding="10")
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
    
    def _create_param_section(self, parent):
        """创建参数配置区域"""
        param_frame = ttk.LabelFrame(parent, text="转换参数", style="Section.TLabelframe", padding="10")
        param_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(param_frame, text="采样间隔(秒):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.sample_interval_var = tk.StringVar(value="0.1")
        self.sample_interval_entry = ttk.Entry(param_frame, textvariable=self.sample_interval_var, width=15)
        self.sample_interval_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(param_frame, text="CSV编码:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.encoding_var = tk.StringVar(value="utf-8-sig")
        encoding_combo = ttk.Combobox(param_frame, textvariable=self.encoding_var, width=12, state="readonly")
        encoding_combo["values"] = ("utf-8-sig", "utf-8", "gbk", "gb2312")
        encoding_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(param_frame, text="调试模式", variable=self.debug_var).grid(row=1, column=2, sticky=tk.W, padx=(20, 0), pady=2)
    
    def _create_action_section(self, parent):
        """创建操作按钮区域"""
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(
            action_frame, 
            text="保存配置", 
            command=self._save_config,
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        self.convert_btn = ttk.Button(
            action_frame, 
            text="开始转换", 
            command=self._start_convert,
            style="Action.TButton",
            width=15
        )
        self.convert_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            action_frame, 
            text="退出", 
            command=self._on_closing,
            width=12
        ).pack(side=tk.RIGHT, padx=5)
    
    def _create_log_section(self, parent):
        """创建日志输出区域"""
        log_frame = ttk.LabelFrame(parent, text="运行日志", style="Section.TLabelframe", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _log(self, message: str):
        """
        输出日志信息
        
        Args:
            message: 日志消息
        """
        try:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
            self.root.update_idletasks()
        except tk.TclError:
            pass
    
    def _clear_log(self):
        """清空日志"""
        try:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass
    
    def _browse_asc(self):
        """浏览ASC文件"""
        filename = filedialog.askopenfilename(
            title="选择ASC文件",
            filetypes=[("ASC文件", "*.asc"), ("所有文件", "*.*")]
        )
        if filename:
            self.asc_entry.delete(0, tk.END)
            self.asc_entry.insert(0, filename)
    
    def _add_dbc(self):
        """添加DBC文件"""
        filenames = filedialog.askopenfilenames(
            title="选择DBC文件",
            filetypes=[("DBC文件", "*.dbc"), ("所有文件", "*.*")]
        )
        for filename in filenames:
            if filename not in self.dbc_listbox.get(0, tk.END):
                self.dbc_listbox.insert(tk.END, filename)
    
    def _remove_dbc(self):
        """删除选中的DBC文件"""
        selection = self.dbc_listbox.curselection()
        for index in reversed(selection):
            self.dbc_listbox.delete(index)
    
    def _browse_output(self):
        """浏览输出目录"""
        dirname = filedialog.askdirectory(title="选择输出目录")
        if dirname:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, dirname)
    
    def _load_config(self):
        """加载配置"""
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
        """保存配置到文件"""
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
        except PermissionError:
            self._log("保存配置失败: 无权限写入文件")
            messagebox.showerror("错误", "无权限写入配置文件")
        except Exception as e:
            self._log(f"保存配置失败: {type(e).__name__}: {e}")
            messagebox.showerror("错误", f"保存配置失败: {e}")
    
    def _validate_inputs(self) -> bool:
        """
        验证输入参数
        
        Returns:
            bool: 验证是否通过
        """
        asc_file = self.asc_entry.get().strip()
        if not asc_file:
            messagebox.showerror("错误", "请选择ASC文件")
            return False
        
        if not os.path.exists(asc_file):
            messagebox.showerror("错误", f"ASC文件不存在: {asc_file}")
            return False
        
        if not os.access(asc_file, os.R_OK):
            messagebox.showerror("错误", f"无权限读取ASC文件: {asc_file}")
            return False
        
        if self.dbc_listbox.size() == 0:
            messagebox.showerror("错误", "请至少添加一个DBC文件")
            return False
        
        for dbc in self.dbc_listbox.get(0, tk.END):
            if not os.path.exists(dbc):
                messagebox.showerror("错误", f"DBC文件不存在: {dbc}")
                return False
            if not os.access(dbc, os.R_OK):
                messagebox.showerror("错误", f"无权限读取DBC文件: {dbc}")
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
        """开始转换"""
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
        """执行转换（在后台线程中运行）"""
        dbc_loader = None
        asc_parser = None
        data_processor = None
        
        try:
            from dbc_loader import DBCLoader
            from asc_parser import ASCParser
            from data_processor import DataProcessor
            from csv_writer import CSVWriter
            
            config = Config(
                asc_file=self.asc_entry.get(),
                dbc_files=list(self.dbc_listbox.get(0, tk.END)),
                output_dir=self.output_entry.get(),
                sample_interval=float(self.sample_interval_var.get()),
                csv_encoding=self.encoding_var.get(),
                debug=self.debug_var.get()
            )
            
            self._log("开始转换...")
            self._log(f"分组规则: 按BatP+数字模式分组")
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
            asc_parser = ASCParser(
                sample_interval=config.sample_interval,
                debug=config.debug
            )
            if not asc_parser.parse(config.asc_file, dbc_loader.message_map):
                self._log("ASC文件解析失败")
                return
            
            original_count, sampled_count, signal_count = asc_parser.get_statistics()
            self._log(f"解析完成：")
            self._log(f"  原始数据点数: {original_count}")
            self._log(f"  采样后时间点数: {sampled_count}")
            self._log(f"  实际信号数: {signal_count}")
            self._log("")
            
            self._log("正在处理数据...")
            data_processor = DataProcessor()
            data_processor.aggregate(asc_parser.sampled_data)
            data_processor.classify_signals(asc_parser.found_signals)
            
            self._log("分组结果：")
            for group_name, count in data_processor.get_group_statistics().items():
                self._log(f"  {group_name}: {count}个信号")
            self._log("")
            
            self._log("正在创建CSV文件...")
            config.create_output_dir()
            csv_writer = CSVWriter(
                output_dir=config.output_dir,
                encoding=config.csv_encoding,
                group_size=config.group_size
            )
            
            created_files = csv_writer.write_all(
                sorted_groups=data_processor.sorted_groups,
                classified_signals=data_processor.classified_signals,
                sorted_timestamps=data_processor.get_sorted_timestamps(),
                aggregated_data=data_processor.aggregated_data,
                signal_info=dbc_loader.signal_info,
                statistics={
                    'original_count': original_count,
                    'sampled_count': sampled_count,
                    'signal_count': signal_count
                }
            )
            
            self._log("")
            self._log("=" * 50)
            self._log("转换完成！")
            self._log(f"输出目录: {config.output_dir}")
            self._log(f"生成文件数: {len(created_files)}")
            self._log("=" * 50)
            
            self.root.after(0, lambda: messagebox.showinfo("成功", f"转换完成！\n输出目录: {config.output_dir}"))
            
        except MemoryError:
            self._log("错误：内存不足，请尝试增加采样间隔或处理较小的文件")
            self.root.after(0, lambda: messagebox.showerror("错误", "内存不足，请尝试增加采样间隔"))
        except PermissionError as e:
            self._log(f"错误：权限不足 - {e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"权限不足: {e}"))
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
    
    def _on_closing(self):
        """窗口关闭处理"""
        if self.is_converting:
            if messagebox.askyesno("确认", "转换正在进行中，确定要退出吗？"):
                self.root.quit()
        else:
            self.root.quit()


def get_resource_path(relative_path: str) -> str:
    """
    获取资源文件路径（兼容PyInstaller打包）
    
    Args:
        relative_path: 相对路径
        
    Returns:
        str: 绝对路径
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def main():
    """GUI主函数"""
    root = tk.Tk()
    app = ASCToCSVApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
