# asc_to_csv/ui/convert_tab.py
"""
数据转换标签页模块

本模块提供ASC到CSV转换功能的图形用户界面，包括文件选择、参数配置、
转换执行和日志显示等功能。

界面布局：
    ┌─────────────────────────────────────────────────────────────┐
    │ 文件设置                                                     │
    │   ASC文件: [________________________] [浏览...]              │
    │   DBC文件: [________________________] [添加] [删除]          │
    │   输出目录: [________________________] [浏览...]              │
    ├─────────────────────────────────────────────────────────────┤
    │ 转换参数                                                     │
    │   采样间隔(秒): [0.1]    分组规则: BatP+数字/字母            │
    │   CSV编码: [utf-8-sig]  □ 调试模式                          │
    ├─────────────────────────────────────────────────────────────┤
    │ [保存配置] [开始转换]                                        │
    ├─────────────────────────────────────────────────────────────┤
    │ 运日志                                                       │
    │   _______________________________________________           │
    │   _______________________________________________           │
    │   _______________________________________________           │
    └─────────────────────────────────────────────────────────────┘

分组规则：
    - BatP + 数字：BATP1, BATP10, BATP28 等
    - BatP + 1-2个字母：BATPS, BATPQ, BATPL, BATPR 等
    - 不符合规则的归入 Others

使用示例：
    >>> import tkinter as tk
    >>> from ui.convert_tab import ConvertTab
    >>> 
    >>> root = tk.Tk()
    >>> app_context = {'root': root}
    >>> tab = ConvertTab(root, app_context)
    >>> tab.pack(fill=tk.BOTH, expand=True)
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional
import json
import traceback

from .base import BaseTab, LogMixin
from config import Config
from enhanced_conversion_service import EnhancedConversionService


class ConvertTab(BaseTab, LogMixin):
    """
    数据转换标签页
    
    提供ASC文件到CSV文件的转换功能，包括：
    - 文件选择：ASC文件、DBC文件、输出目录
    - 参数配置：采样间隔、CSV编码、调试模式
    - 转换执行：多线程执行，避免界面冻结
    - 日志显示：实时显示转换进度和结果
    
    继承自：
        BaseTab: 标签页基类
        LogMixin: 日志输出混入类
    
    Attributes:
        convert_btn (ttk.Button): 开始转换按钮
        log_text (tk.Text): 日志文本框
        asc_entry (ttk.Entry): ASC文件路径输入框
        dbc_listbox (tk.Listbox): DBC文件列表
        output_entry (ttk.Entry): 输出目录输入框
        sample_interval_var (tk.StringVar): 采样间隔变量
        encoding_var (tk.StringVar): CSV编码变量
        debug_var (tk.BooleanVar): 调试模式变量
    
    分组规则：
        - BatP + 数字：BATP1, BATP10, BATP28 等
        - BatP + 1-2个字母：BATPS, BATPQ, BATPL, BATPR 等
        - 不符合规则的归入 Others
    
    线程安全：
        - 转换操作在后台线程执行
        - UI更新通过 root.after() 在主线程执行
        - 使用 is_converting 标志防止重复执行
    """
    
    def __init__(self, parent: tk.Widget, app_context: dict):
        """
        初始化转换标签页

        Args:
            parent: 父容器（通常是ttk.Notebook）
            app_context: 应用上下文字典，包含以下键：
                - 'root': Tk根窗口实例
                - 'is_converting': 转换状态标志
                - 'output_dir': 输出目录路径
                - 'refresh_callback': 刷新回调函数
        """
        self.asc_listbox: Optional[tk.Listbox] = None
        self.asc_entry: Optional[ttk.Entry] = None
        self.asc_mode_var: tk.BooleanVar = None
        self.log_text: Optional[tk.Text] = None
        self.dbc_listbox: Optional[tk.Listbox] = None
        self.output_entry: Optional[ttk.Entry] = None
        self.sample_interval_var: Optional[tk.StringVar] = None
        self.encoding_var: Optional[tk.StringVar] = None
        self.debug_var: Optional[tk.BooleanVar] = None
        self.convert_btn: Optional[ttk.Button] = None
        self._save_config_btn: Optional[ttk.Button] = None
        self._save_in_progress: bool = False

        super().__init__(parent, app_context)
    
    def _create_widgets(self):
        """
        创建界面组件
        
        构建完整的界面布局，包括：
        1. 文件设置区域
        2. 参数配置区域
        3. 操作按钮区域
        4. 日志输出区域
        """
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self._create_file_section(main_frame)
        self._create_param_section(main_frame)
        self._create_action_section(main_frame)
        self._create_log_section(main_frame)
    
    def _create_file_section(self, parent: ttk.Frame):
        """
        创建文件选择区域

        包含：
        - ASC文件选择（支持单文件和多文件模式）
        - DBC文件列表（支持多文件）
        - 输出目录选择

        Args:
            parent: 父容器
        """
        file_frame = ttk.LabelFrame(parent, text="文件设置", padding="10")
        file_frame.pack(fill=tk.X, pady=5)

        self.asc_mode_var = tk.BooleanVar(value=False)

        asc_mode_frame = ttk.Frame(file_frame)
        asc_mode_frame.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 5))
        ttk.Radiobutton(asc_mode_frame, text="单文件模式", variable=self.asc_mode_var,
                       value=False, command=self._on_asc_mode_changed).pack(side=tk.LEFT)
        ttk.Radiobutton(asc_mode_frame, text="多文件拼接模式", variable=self.asc_mode_var,
                       value=True, command=self._on_asc_mode_changed).pack(side=tk.LEFT)

        single_frame = ttk.Frame(file_frame)
        single_frame.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=2)
        ttk.Label(single_frame, text="ASC文件:").pack(side=tk.LEFT)
        self.asc_entry = ttk.Entry(single_frame, width=60)
        self.asc_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(single_frame, text="浏览...", command=self._browse_asc).pack(side=tk.LEFT)

        multi_frame = ttk.Frame(file_frame)
        multi_frame.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=2)
        ttk.Label(multi_frame, text="ASC文件列表:").pack(side=tk.LEFT)
        self.asc_listbox = tk.Listbox(multi_frame, height=4, selectmode=tk.EXTENDED)
        self.asc_listbox.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        asc_btn_frame = ttk.Frame(multi_frame)
        asc_btn_frame.pack(side=tk.LEFT, padx=5)
        ttk.Button(asc_btn_frame, text="添加", command=self._add_asc_files, width=6).pack(pady=1)
        ttk.Button(asc_btn_frame, text="删除", command=self._remove_asc_files, width=6).pack(pady=1)
        ttk.Button(asc_btn_frame, text="清空", command=self._clear_asc_files, width=6).pack(pady=1)
        ttk.Button(asc_btn_frame, text="排序", command=self._sort_asc_files, width=6).pack(pady=1)

        multi_frame.grid_remove()

        self._single_asc_frame = single_frame
        self._multi_asc_frame = multi_frame

        ttk.Label(file_frame, text="DBC文件:").grid(row=3, column=0, sticky=tk.W, pady=2)
        dbc_frame = ttk.Frame(file_frame)
        dbc_frame.grid(row=3, column=1, columnspan=2, sticky=tk.EW, pady=2)

        self.dbc_listbox = tk.Listbox(dbc_frame, height=3, selectmode=tk.EXTENDED)
        self.dbc_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)

        dbc_btn_frame = ttk.Frame(dbc_frame)
        dbc_btn_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Button(dbc_btn_frame, text="添加", command=self._add_dbc, width=6).pack(pady=1)
        ttk.Button(dbc_btn_frame, text="删除", command=self._remove_dbc, width=6).pack(pady=1)

        ttk.Label(file_frame, text="输出目录:").grid(row=4, column=0, sticky=tk.W, pady=2)
        output_frame = ttk.Frame(file_frame)
        output_frame.grid(row=4, column=1, columnspan=2, sticky=tk.EW, pady=2)
        self.output_entry = ttk.Entry(output_frame, width=60)
        self.output_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="浏览...", command=self._browse_output).pack(side=tk.LEFT)

        file_frame.columnconfigure(1, weight=1)

    def _on_asc_mode_changed(self):
        """ASC文件模式切换事件处理"""
        if self.asc_mode_var.get():
            self._single_asc_frame.grid_remove()
            self._multi_asc_frame.grid()
        else:
            self._multi_asc_frame.grid_remove()
            self._single_asc_frame.grid()

    def _add_asc_files(self):
        """添加ASC文件到列表"""
        filenames = filedialog.askopenfilenames(
            title="选择ASC文件（多选）",
            filetypes=[("ASC文件", "*.asc"), ("所有文件", "*.*")]
        )
        for filename in filenames:
            if filename not in self.asc_listbox.get(0, tk.END):
                self.asc_listbox.insert(tk.END, filename)

    def _remove_asc_files(self):
        """删除选中的ASC文件"""
        selection = self.asc_listbox.curselection()
        for index in reversed(selection):
            self.asc_listbox.delete(index)

    def _clear_asc_files(self):
        """清空ASC文件列表"""
        self.asc_listbox.delete(0, tk.END)

    def _sort_asc_files(self):
        """手动排序ASC文件（基于文件名时间戳）"""
        from asc_file_merger import ASCFileMerger
        merger = ASCFileMerger()

        files = list(self.asc_listbox.get(0, tk.END))
        if not files:
            return

        try:
            sorted_files = merger.sort_files_by_time(files)
            self.asc_listbox.delete(0, tk.END)
            for f in sorted_files:
                self.asc_listbox.insert(tk.END, f)
            messagebox.showinfo("排序完成", f"已按时间戳排序 {len(sorted_files)} 个文件")
        except Exception as e:
            messagebox.showerror("排序失败", str(e))
    
    def _create_param_section(self, parent: ttk.Frame):
        """
        创建参数配置区域
        
        包含：
        - 采样间隔设置
        - 分组规则说明
        - CSV编码选择
        - 调试模式开关
        
        Args:
            parent: 父容器
        """
        param_frame = ttk.LabelFrame(parent, text="转换参数", padding="10")
        param_frame.pack(fill=tk.X, pady=5)
        
        # 采样间隔
        ttk.Label(param_frame, text="采样间隔(秒):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.sample_interval_var = tk.StringVar(value="0.1")
        ttk.Entry(param_frame, textvariable=self.sample_interval_var, width=15).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        # 分组规则说明
        ttk.Label(param_frame, text="分组规则:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0), pady=2)
        ttk.Label(param_frame, text="BatP+数字/字母 → 独立分组\n其他 → Others.csv").grid(
            row=0, column=3, sticky=tk.W, padx=5, pady=2)
        
        # CSV编码
        ttk.Label(param_frame, text="CSV编码:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.encoding_var = tk.StringVar(value="utf-8-sig")
        encoding_combo = ttk.Combobox(param_frame, textvariable=self.encoding_var, 
                                       width=12, state="readonly")
        encoding_combo["values"] = ("utf-8-sig", "utf-8", "gbk", "gb2312")
        encoding_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # 调试模式
        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(param_frame, text="调试模式", 
                        variable=self.debug_var).grid(row=1, column=2, sticky=tk.W, padx=(20, 0), pady=2)
    
    def _create_action_section(self, parent: ttk.Frame):
        """
        创建操作按钮区域
        
        包含：
        - 保存配置按钮
        - 开始转换按钮
        
        Args:
            parent: 父容器
        """
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=10)

        self._save_config_btn = ttk.Button(action_frame, text="保存配置",
                                          command=self._save_config, width=12)
        self._save_config_btn.pack(side=tk.LEFT, padx=5)

        self.convert_btn = ttk.Button(action_frame, text="开始转换",
                                      command=self._start_convert, width=15)
        self.convert_btn.pack(side=tk.LEFT, padx=5)
    
    def _create_log_section(self, parent: ttk.Frame):
        """
        创建日志输出区域
        
        包含：
        - 日志文本框
        - 垂直滚动条
        
        Args:
            parent: 父容器
        """
        log_frame = ttk.LabelFrame(parent, text="运行日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _browse_asc(self):
        """
        浏览ASC文件
        
        打开文件选择对话框，选择ASC格式的CAN日志文件。
        支持的文件类型：*.asc, 所有文件
        """
        filename = filedialog.askopenfilename(
            title="选择ASC文件",
            filetypes=[("ASC文件", "*.asc"), ("所有文件", "*.*")]
        )
        if filename:
            self.asc_entry.delete(0, tk.END)
            self.asc_entry.insert(0, filename)
    
    def _add_dbc(self):
        """
        添加DBC文件
        
        打开文件选择对话框，选择一个或多个DBC文件。
        已添加的文件不会重复添加。
        """
        filenames = filedialog.askopenfilenames(
            title="选择DBC文件",
            filetypes=[("DBC文件", "*.dbc"), ("所有文件", "*.*")]
        )
        for filename in filenames:
            if filename not in self.dbc_listbox.get(0, tk.END):
                self.dbc_listbox.insert(tk.END, filename)
    
    def _remove_dbc(self):
        """
        删除选中的DBC文件
        
        从DBC文件列表中删除用户选中的文件。
        支持多选删除。
        """
        selection = self.dbc_listbox.curselection()
        for index in reversed(selection):
            self.dbc_listbox.delete(index)
    
    def _browse_output(self):
        """
        浏览输出目录
        
        打开目录选择对话框，选择CSV文件的输出目录。
        """
        dirname = filedialog.askdirectory(title="选择输出目录")
        if dirname:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, dirname)
    
    def _save_config(self):
        """
        保存配置

        将当前的配置保存到config.json文件中。
        配置包括：ASC文件路径/列表、DBC文件列表、输出目录、采样间隔、编码、调试模式。

        成功时显示提示对话框，失败时显示错误对话框。
        """
        if self._save_in_progress:
            return

        self._save_in_progress = True
        self._save_config_btn.config(state=tk.DISABLED)

        try:
            multi_file_mode = self.asc_mode_var.get()

            if multi_file_mode:
                asc_list_for_save = list(self.asc_listbox.get(0, tk.END))
                asc_file_for_save = ""
            else:
                asc_list_for_save = []
                asc_file_for_save = self.asc_entry.get().strip()

            sample_interval_str = self.sample_interval_var.get().strip()
            try:
                sample_interval = float(sample_interval_str) if sample_interval_str else 0.1
            except ValueError:
                sample_interval = 0.1

            config_data = {
                "asc_file": asc_file_for_save,
                "asc_files": asc_list_for_save,
                "multi_file_mode": multi_file_mode,
                "dbc_files": list(self.dbc_listbox.get(0, tk.END)),
                "output_dir": self.output_entry.get().strip(),
                "sample_interval": sample_interval,
                "csv_encoding": self.encoding_var.get(),
                "debug": self.debug_var.get()
            }

            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(project_root, "config.json")

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            with open(config_path, 'r', encoding='utf-8') as f:
                verification = json.load(f)

            if verification.get("sample_interval") != config_data["sample_interval"]:
                raise IOError("配置保存验证失败：数据不一致")

            self._log(f"配置已保存到: {config_path}")
            messagebox.showinfo("成功", f"配置保存成功！\n\n文件路径: {config_path}")
        except Exception as e:
            self._log(f"保存配置失败: {e}")
            messagebox.showerror("错误", f"保存配置失败: {e}")
        finally:
            self._save_in_progress = False
            self._save_config_btn.config(state=tk.NORMAL)
    
    def _validate_inputs(self) -> bool:
        """
        验证输入参数

        检查以下内容：
        1. ASC文件是否已选择且存在（单文件或多文件模式）
        2. 是否至少添加了一个DBC文件
        3. 所有DBC文件是否存在
        4. 输出目录是否已选择
        5. 采样间隔是否为有效的正数

        Returns:
            bool: 输入是否有效
        """
        if self.asc_mode_var.get():
            asc_files = list(self.asc_listbox.get(0, tk.END))
            if not asc_files:
                messagebox.showerror("错误", "请添加ASC文件")
                return False

            for asc_file in asc_files:
                if not os.path.exists(asc_file):
                    messagebox.showerror("错误", f"ASC文件不存在: {asc_file}")
                    return False
        else:
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
        """
        开始转换
        
        验证输入后，在后台线程启动转换任务。
        转换过程中禁用转换按钮，防止重复执行。
        """
        if not self._validate_inputs():
            return
        
        if self.app_context.get('is_converting', False):
            messagebox.showwarning("提示", "转换正在进行中，请稍候...")
            return
        
        self.app_context['is_converting'] = True
        self.convert_btn.configure(state=tk.DISABLED)
        self._clear_log()
        
        thread = threading.Thread(target=self._do_convert, daemon=True)
        thread.start()
    
    def _do_convert(self):
        """
        执行转换（后台线程）

        创建配置对象和转换服务，执行转换流程。
        支持单文件和多文件两种模式。
        使用 root.after() 在主线程更新UI。

        转换完成后：
        - 成功：显示分组统计信息
        - 失败：显示错误信息

        Note:
            此方法在后台线程中执行，不应直接操作UI。
            所有UI更新必须通过 root.after() 在主线程执行。
        """
        try:
            multi_file_mode = self.asc_mode_var.get()

            if multi_file_mode:
                asc_files = list(self.asc_listbox.get(0, tk.END))
                asc_file = ""
            else:
                asc_files = []
                asc_file = self.asc_entry.get()

            config = Config(
                single_asc_file=asc_file,
                asc_files=asc_files,
                multi_file_mode=multi_file_mode,
                dbc_files=list(self.dbc_listbox.get(0, tk.END)),
                output_dir=self.output_entry.get(),
                sample_interval=float(self.sample_interval_var.get()),
                csv_encoding=self.encoding_var.get(),
                debug=self.debug_var.get()
            )

            service = EnhancedConversionService(config)

            def progress_callback(progress: float, line_count: int):
                self.app_context['root'].after(0,
                    lambda: self._update_progress_display(progress, line_count))

            def log_callback(message: str):
                self.app_context['root'].after(0, lambda m=message: self._log(m))

            result = service.convert(
                progress_callback=progress_callback,
                log_callback=log_callback
            )

            if result.success:
                self.app_context['output_dir'] = result.output_dir
                self.app_context['root'].after(0,
                    lambda: self.app_context.get('refresh_callback', lambda: None)())

                group_info = "\n".join([f"  {g}: {result.group_statistics.get(g, 0)}个信号"
                                       for g in result.discovered_groups])
                mode_str = "多文件拼接" if multi_file_mode else "单文件"
                self.app_context['root'].after(0,
                    lambda: messagebox.showinfo("成功",
                        f"转换完成！({mode_str})\n输出目录: {result.output_dir}\n发现分组: {len(result.discovered_groups)}个\n{group_info}"))
            else:
                self.app_context['root'].after(0,
                    lambda: messagebox.showerror("错误", f"转换失败: {result.error_message}"))

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            self.app_context['root'].after(0, lambda: self._log(f"转换失败: {error_msg}"))
            if self.debug_var.get():
                self.app_context['root'].after(0,
                    lambda: self._log(traceback.format_exc()))
            self.app_context['root'].after(0,
                lambda: messagebox.showerror("错误", f"转换失败: {error_msg}"))

        finally:
            self.app_context['is_converting'] = False
            self.app_context['root'].after(0,
                lambda: self.convert_btn.configure(state=tk.NORMAL))
    
    def _update_progress_display(self, progress: float, line_count: int):
        """
        更新进度显示
        
        在日志文本框中更新进度信息。找到最后一条进度信息并更新。
        
        Args:
            progress: 进度百分比 (0.0 - 100.0)
            line_count: 已处理的行数
        """
        try:
            content = self.log_text.get("1.0", tk.END)
            lines = content.strip().split('\n')
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].startswith("进度:"):
                    lines[i] = f"进度: {progress:.1f}% (已处理 {line_count:,} 行)"
                    break
            
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert(tk.END, '\n'.join(lines) + '\n')
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
            self.app_context['root'].update_idletasks()
        except tk.TclError:
            pass
    
    def load_config(self, config: Config):
        """
        加载配置

        从配置对象加载设置到界面控件。

        Args:
            config: 配置对象，包含ASC文件、DBC文件、输出目录等设置
        """
        if config:
            if hasattr(config, 'multi_file_mode') and config.multi_file_mode:
                self.asc_mode_var.set(True)
                self._on_asc_mode_changed()
                for asc_file in config.asc_files:
                    self.asc_listbox.insert(tk.END, asc_file)
            elif config.single_asc_file:
                self.asc_mode_var.set(False)
                self._on_asc_mode_changed()
                self.asc_entry.insert(0, config.single_asc_file)

            for dbc in config.dbc_files:
                self.dbc_listbox.insert(tk.END, dbc)
            if config.output_dir:
                self.output_entry.insert(0, config.output_dir)
            self.sample_interval_var.set(str(config.sample_interval))
            self.encoding_var.set(config.csv_encoding)
            self.debug_var.set(config.debug)
            self._log("已加载配置文件")
