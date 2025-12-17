import flet as ft
import csv
import math
import os
import threading
import time
import subprocess
from itertools import islice


# ==========================================
# 1. 后端逻辑 (经过改造以适配 GUI)
# ==========================================

def detect_encoding(file_path):
    """检测文件编码"""
    encodings_to_try = ['utf-8-sig', 'gbk', 'gb2312', 'utf-8', 'cp936', 'big5']
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read(2048)
                return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    return 'gbk'


def split_csv_logic(file_path, num_parts, output_folder, log_callback, progress_callback):
    """
    核心拆分逻辑
    log_callback: 用于将文本输出到 GUI 的函数
    progress_callback: 用于控制进度条显示 (True/False)
    """
    try:
        log_callback(f"🚀 开始处理: {os.path.basename(file_path)}")
        progress_callback(True)  # 显示进度条

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            log_callback(f"📂 创建输出目录: {output_folder}")

        base_name = os.path.splitext(os.path.basename(file_path))[0]

        # --- 检测编码 ---
        log_callback("🔍 正在检测文件编码...")
        encoding = detect_encoding(file_path)
        log_callback(f"✅ 检测到编码: {encoding}")

        # --- 计算行数 ---
        log_callback("📊 正在计算总行数 (这可能需要一点时间)...")
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                total_lines = sum(1 for _ in f)
        except Exception:
            # 降级重试
            log_callback("⚠️ 标准读取失败，尝试忽略错误模式...")
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                total_lines = sum(1 for _ in f)

        data_rows = total_lines - 1
        if data_rows <= 0:
            log_callback("❌ 错误: 数据行数不足 (仅包含表头或为空)")
            progress_callback(False)
            return

        chunk_size = math.ceil(data_rows / num_parts)
        log_callback(f"📋 总行数: {data_rows} | 拆分份数: {num_parts} | 每份约: {chunk_size} 行")

        # --- 开始拆分 ---
        # 封装内部函数以复用代码
        def process_splitting(open_func_args):
            with open(file_path, 'r', **open_func_args) as f_in:
                reader = csv.reader(f_in)
                try:
                    header = next(reader)
                except StopIteration:
                    return  # 空文件

                for i in range(num_parts):
                    current_chunk_iter = islice(reader, chunk_size)
                    try:
                        first_row = next(current_chunk_iter)
                    except StopIteration:
                        log_callback(f"🏁 数据已分完，提前结束。共生成 {i} 个文件。")
                        break

                    part_filename = f"{base_name}_part_{i + 1}.csv"
                    save_path = os.path.join(output_folder, part_filename)

                    with open(save_path, 'w', encoding=encoding, newline='') as f_out:
                        writer = csv.writer(f_out)
                        writer.writerow(header)
                        writer.writerow(first_row)
                        writer.writerows(current_chunk_iter)

                    log_callback(f"💾 [{i + 1}/{num_parts}] 生成: {part_filename}")
                    time.sleep(0.05)  # 稍微延迟一点点，让UI刷新更丝滑

        # 尝试正常模式
        try:
            process_splitting({'encoding': encoding, 'newline': ''})
        except Exception as e:
            log_callback(f"⚠️ 正常模式出错: {e}，尝试忽略错误模式...")
            process_splitting({'encoding': encoding, 'errors': 'ignore', 'newline': ''})

        log_callback(f"🎉 处理完成！文件保存在: {output_folder}")

    except Exception as e:
        log_callback(f"❌ 发生未预期的错误: {str(e)}")
    finally:
        progress_callback(False)  # 隐藏进度条


# ==========================================
# 2. 前端界面 (Flet)
# ==========================================

def main(page: ft.Page):
    # 2.1 页面基础设置
    page.title = "CSV 智能拆分工具 v1.0"
    page.window_width = 800
    page.window_height = 950
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 25
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.bgcolor = "#F5F7FA"
    page.scroll = ft.ScrollMode.AUTO

    # 2.2 定义 UI 控件

    # --- 标题栏 ---
    header = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.AUTO_AWESOME, size=36, color="#4F46E5"),
                        ft.Text(
                            "CSV 智能拆分工具",
                            size=28,
                            weight=ft.FontWeight.BOLD,
                            color="#1E293B"
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                ),
                ft.Text(
                    "v1.0  ·  作者: 石岩",
                    size=13,
                    color="#64748B",
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        padding=ft.padding.only(bottom=10),
    )

    # --- 文件选择部分 ---
    txt_file_path = ft.TextField(
        label="CSV 文件路径",
        hint_text="点击右侧按钮选择文件",
        read_only=True,
        expand=True,
        border_radius=8,
        filled=True,
        bgcolor="#FFFFFF",
    )

    # --- 参数设置部分 ---
    txt_num_parts = ft.TextField(
        label="拆分份数",
        value="3",
        width=120,
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.CENTER,
        border_radius=8,
        filled=True,
        bgcolor="#FFFFFF",
    )

    txt_output_path = ft.TextField(
        label="输出文件夹",
        value="output_csv",
        expand=True,
        border_radius=8,
        filled=True,
        bgcolor="#FFFFFF",
    )

    # --- 文件选择器 (跨平台支持) ---
    import platform
    
    def pick_file_cross_platform():
        """跨平台文件选择对话框"""
        system = platform.system()
        
        if system == "Darwin":  # macOS
            script = '''
            tell application "System Events"
                activate
                set theFile to choose file with prompt "选择 CSV 文件" of type {"csv", "public.comma-separated-values-text"}
                return POSIX path of theFile
            end tell
            '''
            try:
                result = subprocess.run(
                    ['osascript', '-e', script],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                pass
                
        elif system == "Windows":
            ps_script = '''
            Add-Type -AssemblyName System.Windows.Forms
            $dialog = New-Object System.Windows.Forms.OpenFileDialog
            $dialog.Title = "选择 CSV 文件"
            $dialog.Filter = "CSV 文件 (*.csv)|*.csv|所有文件 (*.*)|*.*"
            $dialog.InitialDirectory = [Environment]::GetFolderPath('Desktop')
            if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
                Write-Output $dialog.FileName
            }
            '''
            try:
                result = subprocess.run(
                    ['powershell', '-Command', ps_script],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass
                
        else:  # Linux
            try:
                result = subprocess.run(
                    ['zenity', '--file-selection', '--title=选择 CSV 文件', '--file-filter=CSV files (csv) | *.csv'],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                pass
        
        return None

    # 定义按钮点击事件处理函数
    def pick_file_clicked(e):
        file_path = pick_file_cross_platform()
        if file_path:
            txt_file_path.value = file_path
            dir_name = os.path.dirname(file_path)
            txt_output_path.value = os.path.join(dir_name, "output_csv")
            page.update()
    
    btn_pick_file = ft.ElevatedButton(
        "选择文件",
        icon=ft.Icons.FOLDER_OPEN,
        on_click=pick_file_clicked,
        style=ft.ButtonStyle(
            color="#FFFFFF",
            bgcolor="#6366F1",
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
        height=48,
    )

    # --- 进度条 ---
    progress_bar = ft.ProgressBar(
        width=500,
        color="#6366F1",
        bgcolor="#E2E8F0",
        visible=False
    )

    # --- 日志显示区域 ---
    log_view = ft.ListView(
        expand=True,
        spacing=4,
        auto_scroll=True,
        padding=ft.padding.only(right=10),  # 为滚动条留空间
    )

    log_container = ft.Container(
        content=log_view,
        border=ft.border.all(1, "#E2E8F0"),
        border_radius=12,
        padding=15,
        height=250,  # 加大高度
        bgcolor="#FFFFFF",
    )

    # --- 辅助函数：更新日志 ---
    from datetime import datetime
    
    def append_log(message: str):
        # 获取当前时间
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 根据消息类型设置颜色
        color = "#334155"
        bg_color = None
        if "❌" in message:
            color = "#DC2626"
            bg_color = "#FEF2F2"
        elif "⚠️" in message:
            color = "#D97706"
            bg_color = "#FFFBEB"
        elif "🎉" in message:
            color = "#059669"
            bg_color = "#ECFDF5"
        elif "📂" in message or "💾" in message:
            color = "#4F46E5"
        elif "⏳" in message or "🚀" in message:
            color = "#6366F1"

        # 创建日志条目
        log_entry = ft.Container(
            content=ft.Row(
                [
                    ft.Text(f"[{timestamp}]", size=11, color="#94A3B8", width=70),
                    ft.Text(message, size=13, color=color, expand=True),
                ],
                spacing=8,
            ),
            bgcolor=bg_color,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=6,
        )
        
        log_view.controls.append(log_entry)
        page.update()

    # 初始欢迎消息
    append_log("📋 欢迎使用 CSV 智能拆分工具，请选择文件开始操作")

    def set_loading(is_loading: bool):
        progress_bar.visible = is_loading
        btn_run.disabled = is_loading
        btn_pick_file.disabled = is_loading
        page.update()

    # --- 按钮点击事件 ---
    def on_run_click(e):
        file_path = txt_file_path.value
        num_str = txt_num_parts.value
        output_folder = txt_output_path.value

        if not file_path:
            append_log("❌ 错误：请先选择 CSV 文件")
            return
        if not num_str.isdigit() or int(num_str) <= 0:
            append_log("❌ 错误：拆分份数必须是正整数")
            return

        log_view.controls.clear()
        append_log("⏳ 准备开始任务...")

        task_thread = threading.Thread(
            target=split_csv_logic,
            args=(file_path, int(num_str), output_folder, append_log, set_loading),
            daemon=True
        )
        task_thread.start()

    btn_run = ft.ElevatedButton(
        "🚀 开始执行拆分",
        on_click=on_run_click,
        style=ft.ButtonStyle(
            color="#FFFFFF",
            bgcolor="#4F46E5",
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.padding.symmetric(horizontal=40, vertical=15),
        ),
        height=50,
    )

    # 2.3 组装布局

    # 配置卡片
    config_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.SETTINGS, size=20, color="#4F46E5"),
                        ft.Text("配置参数", weight=ft.FontWeight.W_600, size=16, color="#1E293B"),
                    ],
                    spacing=8,
                ),
                ft.Divider(height=20, color="#E2E8F0"),
                ft.Row([txt_file_path, btn_pick_file], spacing=10),
                ft.Row([txt_num_parts, txt_output_path], spacing=15),
            ],
            spacing=15,
        ),
        padding=25,
        border_radius=16,
        bgcolor="#FFFFFF",
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=10,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
    )

    # 底部操作栏
    action_section = ft.Column(
        [
            progress_bar,
            btn_run,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=15,
    )

    # 日志区域标题
    log_header = ft.Row(
        [
            ft.Icon(ft.Icons.TERMINAL, size=18, color="#64748B"),
            ft.Text("执行日志", weight=ft.FontWeight.W_600, size=14, color="#64748B"),
        ],
        spacing=6,
    )

    # 将所有组件添加到页面
    page.add(
        header,
        config_card,
        ft.Container(height=20),
        action_section,
        ft.Container(height=15),
        log_header,
        ft.Container(height=8),
        log_container,
    )
    
    page.update()


# 运行 App
if __name__ == "__main__":
    ft.app(target=main)