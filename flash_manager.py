import os
import sys
import zipfile
import subprocess
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import platform
import json

class FlashManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Flash Manager - Умный перенос файлов")
        
        # Полноэкранный режим СРАЗУ ПРИ ЗАПУСКЕ
        self.fullscreen = True
        self.root.attributes("-fullscreen", True)
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.exit_fullscreen)
        
        # Цвета
        self.bg_color = "#000000"
        self.fg_color = "#ffffff"
        self.btn_bg = "#00aa00"
        self.btn_exit_bg = "#cc0000"
        self.btn_fg = "#ffffff"
        self.entry_bg = "#ffffff"
        self.entry_fg = "#000000"
        self.scrollbar_color = "#00aa00"
        self.back_active_color = "#00aa00"
        self.back_inactive_color = "#666666"
        self.red_color = "#cc0000"
        
        self.root.configure(bg=self.bg_color)
        
        # Определяем исходную папку (где лежит программа)
        if getattr(sys, 'frozen', False):
            self.source_path = Path(sys.executable).parent
        else:
            self.source_path = Path(__file__).parent
        
        self.current_path = self.source_path
        self.history = []
        self.is_searching = False
        self.search_results = []
        self.last_search_text = ""
        
        # КЭШ ДЛЯ РАЗМЕРА ПАПОК
        self.size_cache = {}
        
        self.target_path = tk.StringVar()
        
        # Конфиг
        self.config_file = self.source_path / "flash_config.json"
        self.saved_paths = []
        self.load_config()
        
        # Путь по умолчанию
        if not self.target_path.get():
            self.target_path.set("%DESKTOP%")
        
        self.search_var = tk.StringVar()
        self.suggestion_window = None
        self.dropdown_window = None
        
        self.drive_info = self.get_drive_info()
        self.is_over_left_panel = False
        
        self.setup_ui()
        self.update_path_status()
        self.refresh_file_list()
        self.update_right_panel()
        self.root.after(100, self.update_progress_bar)
    
    # === ПОЛНОЭКРАННЫЙ РЕЖИМ ===
    
    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)
    
    def exit_fullscreen(self, event=None):
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)
    
    # === ЖЁСТКОЕ ЗАКРЫТИЕ (НОВАЯ ВЕРСИЯ 0.9) ===
    
    def hard_exit(self):
        """Мгновенное закрытие программы без ошибок и отчётов в Microsoft"""
        try:
            self.root.quit()           # Останавливаем mainloop
            self.root.update_idletasks() # Принудительно обрабатываем все события
            self.root.destroy()        # Уничтожаем окно
        except:
            pass
        os._exit(0)                    # Полный выход из процесса (гарантия!)
    
    # === РАБОТА С ПУТЯМИ И КОНФИГОМ ===
    
    def resolve_path(self, path_template):
        if not path_template:
            return Path("")
        
        variables = {
            "%DESKTOP%": Path(os.path.expanduser("~/Desktop")),
            "%DOWNLOADS%": Path(os.path.expanduser("~/Downloads")),
            "%DOCUMENTS%": Path(os.path.expanduser("~/Documents")),
            "%MUSIC%": Path(os.path.expanduser("~/Music")),
            "%VIDEOS%": Path(os.path.expanduser("~/Videos")),
            "%PICTURES%": Path(os.path.expanduser("~/Pictures")),
            "%USERPROFILE%": Path(os.path.expanduser("~")),
            "%FLASH%": self.source_path,
        }
        
        result = path_template
        for var, path in variables.items():
            if var in result:
                result = result.replace(var, str(path))
        
        return Path(result)
    
    def get_display_name(self, path_template):
        display_names = {
            "%DESKTOP%": "📌 Рабочий стол",
            "%DOWNLOADS%": "⬇️ Загрузки",
            "%DOCUMENTS%": "📄 Документы",
            "%MUSIC%": "🎵 Музыка",
            "%VIDEOS%": "🎬 Видео",
            "%PICTURES%": "🖼️ Изображения",
            "%USERPROFILE%": "👤 Домашняя папка",
            "%FLASH%": "💾 Корень флешки",
        }
        
        if path_template in display_names:
            return display_names[path_template]
        
        real_path = self.resolve_path(path_template)
        if real_path.exists():
            return f"📁 {real_path.name}"
        return f"❓ {path_template}"
    
    def load_config(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.saved_paths = data.get("saved_paths", [])
                    last_path = data.get("last_path", "")
                    if last_path:
                        self.target_path.set(last_path)
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            self.saved_paths = []
    
    def save_config(self):
        try:
            data = {
                "saved_paths": self.saved_paths,
                "last_path": self.target_path.get()
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения: {e}")
            return False
    
    def add_current_path_to_saved(self):
        current = self.target_path.get().strip()
        if not current:
            messagebox.showwarning("Внимание", "Поле пути пустое")
            return
        
        for item in self.saved_paths:
            if item["path"] == current:
                messagebox.showinfo("Информация", "Этот путь уже в списке")
                return
        
        display = self.get_display_name(current)
        self.saved_paths.append({"display": display, "path": current})
        self.save_config()
        messagebox.showinfo("Успех", f"Путь сохранён:\n{display}")
    
    def remove_saved_path(self, index):
        if 0 <= index < len(self.saved_paths):
            self.saved_paths.pop(index)
            self.save_config()
    
    def show_dropdown(self, event=None):
        if self.dropdown_window and self.dropdown_window.winfo_exists():
            self.dropdown_window.destroy()
        
        if not self.saved_paths:
            messagebox.showinfo("Список пуст", "Нет сохранённых путей.\nНажмите ➕ чтобы добавить.")
            return
        
        btn_x = self.dropdown_btn.winfo_rootx()
        btn_y = self.dropdown_btn.winfo_rooty()
        btn_width = self.dropdown_btn.winfo_width()
        btn_height = self.dropdown_btn.winfo_height()
        
        list_width = max(450, self.target_entry.winfo_width())
        x = btn_x + btn_width - list_width
        y = btn_y + btn_height
        height = min(350, len(self.saved_paths) * 38 + 30)
        
        self.dropdown_window = tk.Toplevel(self.root)
        self.dropdown_window.title("")
        self.dropdown_window.configure(bg=self.bg_color)
        self.dropdown_window.overrideredirect(True)
        self.dropdown_window.geometry(f"{list_width}x{height}+{x}+{y}")
        
        header = tk.Frame(self.dropdown_window, bg="#222222")
        header.pack(fill=tk.X)
        tk.Label(header, text="Сохранённые пути", bg="#222222", fg=self.fg_color,
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=10, pady=5)
        
        list_frame = tk.Frame(self.dropdown_window, bg=self.bg_color)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(list_frame, bg=self.bg_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=self.bg_color)
        
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        for i, item in enumerate(self.saved_paths):
            row = tk.Frame(scrollable, bg=self.bg_color)
            row.pack(fill=tk.X, pady=2, padx=5)
            
            path_btn = tk.Label(row, text=item["display"], anchor="w",
                                bg="#222222", fg=self.fg_color, cursor="hand2",
                                font=("Segoe UI", 9))
            path_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0), pady=5)
            path_btn.bind("<Button-1>", lambda e, p=item["path"]: self.select_path_from_dropdown(p))
            
            close_btn = self.create_red_close_button(row, lambda idx=i: self.remove_and_refresh_dropdown(idx))
            close_btn.pack(side=tk.RIGHT, padx=5)
        
        def on_focus_out(e):
            if self.dropdown_window and not self.dropdown_window.focus_get():
                self.dropdown_window.destroy()
        self.dropdown_window.bind("<FocusOut>", on_focus_out)
    
    def create_red_close_button(self, parent, command):
        btn_frame = tk.Frame(parent, bg=self.bg_color)
        canvas = tk.Canvas(btn_frame, width=20, height=20, bg=self.bg_color, highlightthickness=0)
        canvas.pack()
        
        canvas.create_oval(2, 2, 18, 18, fill=self.red_color, outline=self.red_color)
        canvas.create_line(7, 7, 13, 13, fill="white", width=2)
        canvas.create_line(13, 7, 7, 13, fill="white", width=2)
        
        canvas.tag_bind("all", "<Button-1>", lambda e: command())
        canvas.config(cursor="hand2")
        return btn_frame
    
    def remove_and_refresh_dropdown(self, index):
        self.remove_saved_path(index)
        if self.dropdown_window and self.dropdown_window.winfo_exists():
            self.dropdown_window.destroy()
        self.show_dropdown()
    
    def select_path_from_dropdown(self, path_template):
        self.target_path.set(path_template)
        self.update_path_status()
        self.save_config()
        if self.dropdown_window and self.dropdown_window.winfo_exists():
            self.dropdown_window.destroy()
    
    # === ОСТАЛЬНЫЕ МЕТОДЫ ===
    
    def truncate_filename(self, name, max_len=35):
        if len(name) <= max_len:
            return name
        parts = name.rsplit('.', 1)
        if len(parts) == 2:
            base, ext = parts
            if len(base) + len(ext) + 1 <= max_len:
                return name
            max_base_len = max_len - len(ext) - 4
            if max_base_len < 3:
                return f"{name[:max_len-3]}..."
            return f"{base[:max_base_len]}...{ext}"
        else:
            if max_len <= 3:
                return "..."
            return f"{name[:max_len-3]}..."
    
    def get_drive_info(self):
        drive = str(self.source_path)[:3]
        info = {
            "drive": drive,
            "path": str(self.source_path),
            "total": 0,
            "used": 0,
            "free": 0,
            "percent": 0,
            "fs": "Unknown",
            "type": "Накопитель",
            "status": "OK"
        }
        try:
            usage = shutil.disk_usage(drive)
            info["total"] = usage.total
            info["used"] = usage.used
            info["free"] = usage.free
            info["percent"] = (usage.used / usage.total) * 100
            if "C:" in drive.upper():
                info["type"] = "SSD / HDD (системный)"
            elif any(d in drive.upper() for d in ["D:", "E:", "F:", "G:"]):
                info["type"] = "Внешний накопитель / Флешка"
            else:
                info["type"] = "Локальный диск"
        except:
            pass
        return info
    
    def get_folder_size(self, path):
        path_str = str(path)
        if path_str in self.size_cache:
            return self.size_cache[path_str]
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += self.get_folder_size(entry.path)
        except:
            pass
        self.size_cache[path_str] = total
        return total
    
    def get_top_items(self, path, limit=5):
        items = []
        try:
            for entry in os.scandir(path):
                size = 0
                if entry.is_file():
                    size = entry.stat().st_size
                elif entry.is_dir():
                    size = self.get_folder_size(entry.path)
                items.append((entry.name, size, entry.is_dir()))
            items.sort(key=lambda x: x[1], reverse=True)
            top = items[:limit]
            others_size = sum(x[1] for x in items[limit:])
            return top, others_size, sum(x[1] for x in items)
        except:
            return [], 0, 0
    
    def update_right_panel(self):
        for widget in self.center_panel.winfo_children():
            widget.destroy()
        top_items, others_size, total_size = self.get_top_items(self.current_path)
        chart_frame = tk.Frame(self.center_panel, bg=self.bg_color)
        chart_frame.pack(fill=tk.X, pady=10)
        tk.Label(chart_frame, text="📊 Размеры элементов в папке", bg=self.bg_color, fg=self.fg_color,
                 font=("Segoe UI", 12, "bold")).pack()
        if total_size > 0:
            canvas = tk.Canvas(chart_frame, width=200, height=200, bg=self.bg_color, highlightthickness=0)
            canvas.pack(pady=10)
            start_angle = 0
            colors = ["#00aa00", "#44cc44", "#88ff88", "#ffaa44", "#ff8844", "#666666"]
            color_map = []
            for i, (name, size, is_dir) in enumerate(top_items):
                angle = (size / total_size) * 360
                if angle > 0:
                    canvas.create_arc(10, 10, 190, 190, start=start_angle, extent=angle, fill=colors[i % len(colors)], outline=self.bg_color)
                    color_map.append((name, colors[i % len(colors)], is_dir))
                    start_angle += angle
            if others_size > 0:
                angle = (others_size / total_size) * 360
                canvas.create_arc(10, 10, 190, 190, start=start_angle, extent=angle, fill="#666666", outline=self.bg_color)
                color_map.append(("Другие", "#666666", False))
            table_frame = tk.Frame(self.center_panel, bg=self.bg_color)
            table_frame.pack(fill=tk.X, pady=5)
            for i, (name, color, is_dir) in enumerate(color_map[:5]):
                row = tk.Frame(table_frame, bg=self.bg_color)
                row.pack(fill=tk.X, pady=3)
                color_box = tk.Canvas(row, width=20, height=20, bg=self.bg_color, highlightthickness=0)
                color_box.pack(side=tk.LEFT, padx=(0,8))
                color_box.create_rectangle(2, 2, 18, 18, fill=color, outline=color)
                icon = "📁" if is_dir else "📄"
                color_box.create_text(10, 10, text=icon, fill="#000000", font=("Segoe UI", 9))
                tk.Label(row, text=name[:18], bg=self.bg_color, fg=self.fg_color, anchor="w", width=15, font=("Segoe UI", 9)).pack(side=tk.LEFT)
                size = next((s for n, s, d in top_items if n == name), 0) if name != "Другие" else others_size
                if size > 0:
                    tk.Label(row, text=self.format_size(size), bg=self.bg_color, fg=self.fg_color, width=10, font=("Segoe UI", 9)).pack(side=tk.RIGHT)
                    percent = (size / total_size * 100) if total_size > 0 else 0
                    tk.Label(row, text=f"{percent:.1f}%", bg=self.bg_color, fg=self.fg_color, width=6, font=("Segoe UI", 9)).pack(side=tk.RIGHT)
        else:
            tk.Label(chart_frame, text="Папка пуста", bg=self.bg_color, fg="#888", font=("Segoe UI", 10)).pack(pady=20)
        
        for widget in self.right_panel.winfo_children():
            widget.destroy()
        info_frame = tk.Frame(self.right_panel, bg=self.bg_color)
        info_frame.pack(fill=tk.X, pady=10)
        tk.Label(info_frame, text="💾 НАКОПИТЕЛЬ", bg=self.bg_color, fg=self.fg_color,
                 font=("Segoe UI", 14, "bold")).pack()
        font_large = ("Segoe UI", 12)
        info_lines = [
            f"Диск: {self.drive_info['drive']}",
            f"Тип: {self.drive_info['type']}",
            f"ФС: {self.drive_info['fs']}",
            f"Состояние: {self.drive_info['status']}",
            "",
            f"Всего: {self.format_size(self.drive_info['total'])}",
            f"Занято: {self.format_size(self.drive_info['used'])}",
            f"Свободно: {self.format_size(self.drive_info['free'])}",
            f"Занято: {self.drive_info['percent']:.1f}%"
        ]
        for line in info_lines:
            if line == "":
                tk.Label(info_frame, text=" ", bg=self.bg_color).pack()
            else:
                tk.Label(info_frame, text=line, bg=self.bg_color, fg=self.fg_color,
                         font=font_large, anchor="w").pack(fill=tk.X, pady=2)
    
    def format_size(self, size):
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ТБ"
    
    def format_size_short(self, size):
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024:
                return f"{size:.0f}{unit}"
            size /= 1024
        return f"{size:.1f}ТБ"
    
    def create_back_button(self, parent_frame, state="normal"):
        btn_frame = tk.Frame(parent_frame, bg=self.bg_color)
        color = self.back_active_color if state == "normal" else self.back_inactive_color
        canvas = tk.Canvas(btn_frame, width=80, height=30, bg=self.bg_color, highlightthickness=0)
        canvas.pack()
        cut_size = 8
        points = [cut_size, 0, 80-cut_size, 0, 80, cut_size, 80, 30-cut_size, 80-cut_size, 30, cut_size, 30, 0, 30-cut_size, 0, cut_size]
        rect_id = canvas.create_polygon(points, fill=color, outline=color, tags="rect")
        text_id = canvas.create_text(40, 15, text="← Назад", fill=self.btn_fg, font=("Segoe UI", 10), tags="text")
        if state == "normal":
            canvas.tag_bind(rect_id, "<Button-1>", lambda e: self.go_back())
            canvas.tag_bind(text_id, "<Button-1>", lambda e: self.go_back())
            canvas.config(cursor="hand2")
        else:
            canvas.config(cursor="arrow")
        return btn_frame
    
    def create_cut_corner_button(self, parent, text, command, width=None, state="normal", bg=None, height=32):
        if bg is None:
            bg = self.btn_bg
        if width:
            btn_width = width * 14
        else:
            btn_width = max(70, len(text) * 12)
        btn_frame = tk.Frame(parent, bg=self.bg_color)
        canvas = tk.Canvas(btn_frame, width=btn_width, height=height, bg=self.bg_color, highlightthickness=0)
        canvas.pack()
        cut_size = 8
        points = [cut_size, 0, btn_width-cut_size, 0, btn_width, cut_size, btn_width, height-cut_size, btn_width-cut_size, height, cut_size, height, 0, height-cut_size, 0, cut_size]
        rect_id = canvas.create_polygon(points, fill=bg, outline=bg, smooth=False, tags="polygon")
        
        font_size = 14 if text in ["📁", "➕", "▼"] else 10
        text_id = canvas.create_text(btn_width//2, height//2, text=text, fill=self.btn_fg, font=("Segoe UI", font_size), tags="text")
        
        def on_click(e):
            command()
        canvas.tag_bind(rect_id, "<Button-1>", on_click)
        canvas.tag_bind(text_id, "<Button-1>", on_click)
        canvas.config(cursor="hand2")
        if state == "disabled":
            canvas.itemconfig(rect_id, fill="#666666")
            canvas.itemconfig(text_id, fill="#aaaaaa")
            canvas.config(cursor="arrow")
        return btn_frame
    
    def create_fixed_button(self, parent, text, command, width):
        btn_frame = tk.Frame(parent, bg=self.bg_color)
        canvas = tk.Canvas(btn_frame, width=width, height=26, bg=self.bg_color, highlightthickness=0)
        canvas.pack()
        cut_size = 6
        points = [cut_size, 0, width-cut_size, 0, width, cut_size, width, 26-cut_size, width-cut_size, 26, cut_size, 26, 0, 26-cut_size, 0, cut_size]
        rect_id = canvas.create_polygon(points, fill=self.btn_bg, outline=self.btn_bg, smooth=False, tags="polygon")
        
        font_size = 12 if text in ["📁", "🗜️"] else 9
        text_id = canvas.create_text(width//2, 13, text=text, fill=self.btn_fg, font=("Segoe UI", font_size), tags="text")
        
        def on_click(e):
            command()
        canvas.tag_bind(rect_id, "<Button-1>", on_click)
        canvas.tag_bind(text_id, "<Button-1>", on_click)
        canvas.config(cursor="hand2")
        return btn_frame
    
    def setup_ui(self):
        # ========== ВЕРХНЯЯ ПАНЕЛЬ ==========
        top_frame = tk.Frame(self.root, bg=self.bg_color)
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        # Верхняя строка
        top_line = tk.Frame(top_frame, bg=self.bg_color)
        top_line.pack(fill=tk.X)
        
        # Кнопка полноэкранного режима (САМАЯ ПЕРВАЯ СЛЕВА, без фона)
        self.fullscreen_btn = tk.Label(top_line, text="⛶", font=("Segoe UI", 18), 
                                        bg=self.bg_color, fg=self.fg_color, cursor="hand2")
        self.fullscreen_btn.pack(side=tk.LEFT, padx=(0, 15))
        self.fullscreen_btn.bind("<Button-1>", lambda e: self.toggle_fullscreen())
        
        # Остальные элементы
        tk.Label(top_line, text="📂 Куда копировать:", font=("Segoe UI", 10), bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=(0,5))
        
        self.target_entry = tk.Entry(top_line, textvariable=self.target_path, width=60, bg=self.entry_bg, fg=self.entry_fg, font=("Segoe UI", 10))
        self.target_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        self.target_entry.bind("<KeyRelease>", self.on_target_path_change)
        self.target_entry.bind("<FocusOut>", self.on_target_focus_out)
        self.target_entry.bind("<Return>", self.on_target_enter)
        
        self.path_status = tk.Label(top_line, text="◯", font=("Segoe UI", 16), bg=self.bg_color)
        self.path_status.pack(side=tk.LEFT, padx=(0,5))
        
        self.browse_btn = self.create_fixed_button(top_line, "📁", self.browse_target_folder, width=40)
        self.browse_btn.pack(side=tk.LEFT, padx=(0,5))
        
        self.add_btn = self.create_cut_corner_button(top_line, text="➕", command=self.add_current_path_to_saved, width=3)
        self.add_btn.pack(side=tk.LEFT, padx=(0,5))
        
        self.dropdown_btn = self.create_cut_corner_button(top_line, text="▼", command=self.show_dropdown, width=3)
        self.dropdown_btn.pack(side=tk.LEFT, padx=(0,5))
        
        # ========== ПАНЕЛЬ С КНОПКОЙ НАЗАД И ПОИСК ==========
        middle_frame = tk.Frame(self.root, bg=self.bg_color)
        middle_frame.pack(fill=tk.X, padx=10, pady=(10, 10))
        
        # Кнопка "Назад" слева
        self.back_button_container = tk.Frame(middle_frame, bg=self.bg_color)
        self.back_button_container.pack(side=tk.LEFT, padx=(0, 15))
        self.back_btn = self.create_back_button(self.back_button_container, state="disabled")
        self.back_btn.pack()
        
        # Поиск
        search_frame = tk.Frame(middle_frame, bg=self.bg_color)
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(search_frame, text="Поиск по накопителю:", font=("Segoe UI", 10), bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=(0,5))
        
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=60, bg=self.entry_bg, fg=self.entry_fg, font=("Segoe UI", 10))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        self.search_entry.bind("<Return>", lambda e: self.start_search())
        
        self.search_btn = self.create_cut_corner_button(search_frame, text="НАЙТИ", command=self.start_search, width=8)
        self.search_btn.pack(side=tk.LEFT, padx=(0,5))
        
        self.clear_search_btn = self.create_cut_corner_button(search_frame, text="✖", command=self.clear_search, width=3, bg=self.red_color)
        self.clear_search_btn.pack(side=tk.LEFT)
        
        # ========== ОСНОВНАЯ ОБЛАСТЬ ==========
        main_container = tk.Frame(self.root, bg=self.bg_color)
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        left_frame = tk.Frame(main_container, bg=self.bg_color, width=450)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        left_frame.pack_propagate(False)
        
        self.center_panel = tk.Frame(main_container, bg=self.bg_color, width=400)
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        self.center_panel.pack_propagate(False)
        
        self.right_panel = tk.Frame(main_container, bg=self.bg_color, width=400)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.right_panel.pack_propagate(False)
        
        # Левая колонка
        canvas_frame = tk.Frame(left_frame, bg=self.bg_color)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.left_panel_container = tk.Frame(canvas_frame, bg=self.bg_color)
        self.left_panel_container.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.left_panel_container, bg=self.bg_color, highlightthickness=0)
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.bg_color)
        
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.scrollable_frame, anchor="nw")
        
        self.scrollbar_canvas = tk.Canvas(self.left_panel_container, width=8, bg=self.bg_color, highlightthickness=0)
        self.scrollbar_canvas.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.configure(yscrollcommand=self.update_scrollbar)
        
        self.left_panel_container.bind("<Enter>", self._on_left_panel_enter)
        self.left_panel_container.bind("<Leave>", self._on_left_panel_leave)
        self.canvas.bind("<Enter>", self._on_left_panel_enter)
        self.canvas.bind("<Leave>", self._on_left_panel_leave)
        self.scrollable_frame.bind("<Enter>", self._on_left_panel_enter)
        self.scrollable_frame.bind("<Leave>", self._on_left_panel_leave)
        
        self.root.bind_all("<MouseWheel>", self.on_global_mousewheel)
        self.scrollbar_canvas.bind("<B1-Motion>", self.on_drag_scrollbar)
        
        # ========== НИЖНЯЯ ПАНЕЛЬ ==========
        bottom_frame = tk.Frame(self.root, bg=self.bg_color, height=60)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0,10))
        
        tk.Frame(bottom_frame, height=1, bg="#00aa00").pack(fill=tk.X, pady=(0,8))
        
        bottom_content = tk.Frame(bottom_frame, bg=self.bg_color)
        bottom_content.pack(fill=tk.X, pady=5)
        
        left_bottom = tk.Frame(bottom_content, bg=self.bg_color)
        left_bottom.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(left_bottom, text="v.1.0", font=("Segoe UI", 9), bg=self.bg_color, fg="#888888").pack(side=tk.LEFT, padx=(0,20))
        
        self.path_label = tk.Label(left_bottom, text="", font=("Segoe UI", 9), bg=self.bg_color, fg="#cccccc", anchor="w")
        self.path_label.pack(side=tk.LEFT)
        
        right_bottom = tk.Frame(bottom_content, bg=self.bg_color)
        right_bottom.pack(side=tk.RIGHT)
        
        progress_container = tk.Frame(right_bottom, bg=self.bg_color)
        progress_container.pack(side=tk.LEFT, padx=(0, 15))
        
        self.progress_canvas = tk.Canvas(progress_container, width=280, height=14, bg="#333333", highlightthickness=0)
        self.progress_canvas.pack(side=tk.LEFT)
        
        self.progress_text = tk.Label(progress_container, text="", font=("Segoe UI", 9), bg=self.bg_color, fg="#888888")
        self.progress_text.pack(side=tk.LEFT, padx=(10, 0))
        
        # ========== КНОПКА ВЫХОДА (ВЕРСИЯ 0.9 — ЖЁСТКОЕ ЗАКРЫТИЕ) ==========
        exit_btn = self.create_cut_corner_button(right_bottom, text="Выйти", command=self.hard_exit, width=6, bg=self.btn_exit_bg)
        exit_btn.pack(side=tk.RIGHT)
    
    def _on_left_panel_enter(self, event):
        self.is_over_left_panel = True
    
    def _on_left_panel_leave(self, event):
        x, y = self.root.winfo_pointerxy()
        widget_under_mouse = self.root.winfo_containing(x, y)
        if widget_under_mouse != self.scrollbar_canvas and not self._is_child_of_left_panel(widget_under_mouse):
            self.is_over_left_panel = False
    
    def _is_child_of_left_panel(self, widget, depth=0):
        if depth > 100:  # Защита от рекурсии
            return False
        if widget is None:
            return False
        if widget == self.left_panel_container:
            return True
        try:
            return self._is_child_of_left_panel(widget.master, depth + 1)
        except:
            return False
    
    def on_global_mousewheel(self, event):
        if self.is_over_left_panel:
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            self.update_scrollbar()
    
    def update_scrollbar(self, *args):
        yview = self.canvas.yview()
        canvas_height = self.canvas.winfo_height()
        content_height = self.scrollable_frame.winfo_height()
        self.scrollbar_canvas.delete("slider")
        if content_height > canvas_height and canvas_height > 0:
            slider_height = max(30, canvas_height * (canvas_height / content_height))
            slider_y = canvas_height * yview[0]
            self.scrollbar_canvas.create_rectangle(0, slider_y, 8, slider_y + slider_height, fill=self.scrollbar_color, outline=self.scrollbar_color, tags="slider")
        self.canvas.yview_moveto(yview[0])
    
    def on_drag_scrollbar(self, event):
        y = event.y
        canvas_height = self.canvas.winfo_height()
        content_height = self.scrollable_frame.winfo_height()
        if content_height > canvas_height and canvas_height > 0:
            fraction = y / canvas_height
            fraction = max(0, min(1, fraction))
            self.canvas.yview_moveto(fraction)
            self.update_scrollbar()
    
    def on_target_enter(self, event):
        self.root.focus_set()
    
    def browse_target_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.target_path.set(str(folder))
            self.update_path_status()
            self.save_config()
    
    def on_target_path_change(self, event):
        self.update_path_status()
        self.show_suggestions()
    
    def on_target_focus_out(self, event):
        self.root.after(300, self.hide_suggestions)
        self.save_config()
    
    def show_suggestions(self):
        text = self.target_path.get().strip()
        if not text:
            self.hide_suggestions()
            return
        try:
            real_path = self.resolve_path(text)
            if real_path.exists() and real_path.is_dir():
                current_dir = real_path
                search_text = ""
            else:
                current_dir = real_path.parent
                search_text = real_path.name.lower()
            if not current_dir.exists() or not current_dir.is_dir():
                self.hide_suggestions()
                return
            items = []
            try:
                for p in current_dir.iterdir():
                    if p.is_dir():
                        if not search_text or p.name.lower().startswith(search_text):
                            items.append(p)
            except:
                pass
            if not items:
                self.hide_suggestions()
                return
            items.sort(key=lambda x: x.name.lower())
            self.hide_suggestions()
            self.suggestion_window = tk.Toplevel(self.root)
            self.suggestion_window.title("Подсказки")
            self.suggestion_window.configure(bg="#2b2b2b")
            entry_width = self.target_entry.winfo_width()
            width = max(500, entry_width)
            height = min(400, len(items) * 30 + 50)
            x = self.target_entry.winfo_rootx()
            y = self.target_entry.winfo_rooty() + self.target_entry.winfo_height()
            self.suggestion_window.geometry(f"{width}x{height}+{x}+{y}")
            header = tk.Frame(self.suggestion_window, bg="#2b2b2b")
            header.pack(fill=tk.X)
            tk.Label(header, text="Выберите папку:", bg="#2b2b2b", fg="white").pack(side=tk.LEFT, padx=5, pady=2)
            close_btn = tk.Label(header, text="✖", bg="#2b2b2b", fg="white", cursor="hand2")
            close_btn.pack(side=tk.RIGHT, padx=5, pady=2)
            close_btn.bind("<Button-1>", lambda e: self.hide_suggestions())
            listbox_frame = tk.Frame(self.suggestion_window)
            listbox_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            scrollbar = tk.Scrollbar(listbox_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            listbox = tk.Listbox(listbox_frame, bg="#3c3c3c", fg="white", selectbackground="#555", yscrollcommand=scrollbar.set, font=("Segoe UI", 10))
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            for item in items:
                listbox.insert(tk.END, str(item))
            def on_select(e):
                if listbox.curselection():
                    selected = listbox.get(listbox.curselection()[0])
                    self.target_path.set(selected)
                    self.hide_suggestions()
                    self.update_path_status()
                    self.save_config()
            listbox.bind("<ButtonRelease-1>", on_select)
            listbox.bind("<Return>", on_select)
            listbox.bind("<MouseWheel>", lambda e: self.on_listbox_mousewheel(e, listbox))
        except:
            self.hide_suggestions()
    
    def on_listbox_mousewheel(self, event, listbox):
        listbox.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def hide_suggestions(self):
        if self.suggestion_window:
            self.suggestion_window.destroy()
            self.suggestion_window = None
    
    def update_path_status(self):
        path_template = self.target_path.get()
        real_path = self.resolve_path(path_template)
        if real_path.exists():
            self.path_status.config(text="◯", fg="#00ff00")
        else:
            self.path_status.config(text="◯", fg="#ff0000")
    
    def clear_search(self):
        self.search_var.set("")
        self.is_searching = False
        self.search_results = []
        self.last_search_text = ""
        self.refresh_file_list()
    
    def start_search(self):
        search_text = self.search_var.get().strip()
        if not search_text:
            self.clear_search()
            return
        self.last_search_text = search_text
        self.is_searching = True
        self.root.update()
        self.do_search(search_text)
    
    # ИСПРАВЛЕННЫЙ МЕТОД (было root, стало dirpath)
    def do_search(self, search_text):
        try:
            results = []
            search_lower = search_text.lower()
            for dirpath, dirs, files in os.walk(self.source_path, followlinks=False):
                if len(results) > 500:
                    break
                for d in dirs:
                    if search_lower in d.lower():
                        results.append(Path(dirpath) / d)
                for f in files:
                    if search_lower in f.lower():
                        results.append(Path(dirpath) / f)
            self.search_results = results
            self.refresh_file_list()
        except:
            pass
    
    def go_back(self):
        if self.history:
            self.current_path = self.history.pop()
            self.is_searching = False
            self.search_results = []
            self.search_var.set("")
            self.last_search_text = ""
            self.refresh_file_list()
            self.update_right_panel()
            self.update_back_button_state()
    
    def update_back_button_state(self):
        for widget in self.back_button_container.winfo_children():
            widget.destroy()
        state = "normal" if self.history else "disabled"
        self.back_btn = self.create_back_button(self.back_button_container, state=state)
        self.back_btn.pack()
    
    def update_progress_bar(self):
        if self.drive_info["total"] > 0:
            width = self.progress_canvas.winfo_width()
            if width <= 1:
                self.root.after(100, self.update_progress_bar)
                return
            percent = self.drive_info["percent"] / 100
            fill_width = int(width * percent)
            self.progress_canvas.delete("fill")
            self.progress_canvas.create_rectangle(0, 0, fill_width, 14, fill="#00aa00", tags="fill")
            text = f"{self.format_size_short(self.drive_info['used'])} / {self.format_size_short(self.drive_info['total'])}"
            self.progress_text.config(text=text)
    
    def update_path_label(self):
        current_folder_path = str(self.current_path)
        self.path_label.config(text=current_folder_path)
    
    def refresh_file_list(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        if self.is_searching and self.search_results:
            for item in self.search_results:
                self.create_search_item_row(item)
        else:
            try:
                items = list(self.current_path.iterdir())
            except:
                return
            if not items:
                tk.Label(self.scrollable_frame, text="Эта папка пуста", bg=self.bg_color, fg="#888888", font=("Segoe UI", 12)).pack(expand=True, pady=50)
            else:
                items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
                for item in items:
                    self.create_item_row(item)
        self.update_path_label()
        self.update_right_panel()
        self.update_progress_bar()
    
    def create_item_row(self, item):
        frame = tk.Frame(self.scrollable_frame, bg=self.bg_color)
        frame.pack(fill=tk.X, pady=2, padx=5)
        frame.bind("<Enter>", self._on_left_panel_enter)
        frame.bind("<Leave>", self._on_left_panel_leave)
        if item.is_dir():
            icon = "📁"
        elif item.suffix.lower() in ['.zip', '.rar']:
            icon = "🗜️"
        else:
            icon = "📄"
        display_name = self.truncate_filename(item.name, max_len=35)
        full_text = f"{icon} {display_name}"
        name_label = tk.Label(frame, text=full_text, anchor="w", font=("Segoe UI", 10), bg=self.bg_color, fg=self.fg_color)
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        name_label.bind("<Enter>", self._on_left_panel_enter)
        name_label.bind("<Leave>", self._on_left_panel_leave)
        buttons_frame = tk.Frame(frame, bg=self.bg_color)
        buttons_frame.pack(side=tk.RIGHT, padx=(0, 5))
        show_btn = self.create_fixed_button(buttons_frame, "📁", lambda p=item: self.show_location(p), width=40)
        show_btn.pack(side=tk.RIGHT, padx=(2, 0))
        copy_btn = self.create_fixed_button(buttons_frame, "Копировать", lambda p=item: self.ask_copy(p), width=90)
        copy_btn.pack(side=tk.RIGHT, padx=2)
        if not item.is_dir() and item.suffix.lower() in ['.zip', '.rar']:
            extract_btn = self.create_fixed_button(buttons_frame, "Распаковать", lambda p=item: self.ask_extract(p), width=90)
            extract_btn.pack(side=tk.RIGHT, padx=2)
        if item.is_dir():
            name_label.bind("<Double-Button-1>", lambda e, p=item: self.open_folder(p))
    
    def create_search_item_row(self, item):
        frame = tk.Frame(self.scrollable_frame, bg=self.bg_color)
        frame.pack(fill=tk.X, pady=2, padx=5)
        frame.bind("<Enter>", self._on_left_panel_enter)
        frame.bind("<Leave>", self._on_left_panel_leave)
        icon = "📁" if item.is_dir() else "📄" if item.suffix.lower() not in ['.zip', '.rar'] else "🗜️"
        display_name = self.truncate_filename(item.name, max_len=35)
        full_text = f"{icon} {display_name}"
        name_label = tk.Label(frame, text=full_text, anchor="w", font=("Segoe UI", 10), bg=self.bg_color, fg=self.fg_color)
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        name_label.bind("<Enter>", self._on_left_panel_enter)
        name_label.bind("<Leave>", self._on_left_panel_leave)
        buttons_frame = tk.Frame(frame, bg=self.bg_color)
        buttons_frame.pack(side=tk.RIGHT, padx=(0, 5))
        show_btn = self.create_fixed_button(buttons_frame, "📁", lambda p=item: self.show_location(p), width=40)
        show_btn.pack(side=tk.RIGHT, padx=(2, 0))
        copy_btn = self.create_fixed_button(buttons_frame, "Копировать", lambda p=item: self.ask_copy(p), width=90)
        copy_btn.pack(side=tk.RIGHT, padx=2)
        if not item.is_dir() and item.suffix.lower() in ['.zip', '.rar']:
            extract_btn = self.create_fixed_button(buttons_frame, "Распаковать", lambda p=item: self.ask_extract(p), width=90)
            extract_btn.pack(side=tk.RIGHT, padx=2)
        if item.is_dir():
            name_label.bind("<Double-Button-1>", lambda e, p=item: self.open_folder(p))
    
    def open_folder(self, folder):
        self.history.append(self.current_path)
        self.current_path = folder
        self.is_searching = False
        self.search_var.set("")
        self.last_search_text = ""
        self.search_results = []
        self.refresh_file_list()
        self.update_back_button_state()
    
    def show_location(self, item):
        subprocess.run(['explorer', str(item.parent)])
    
    def ask_copy(self, item):
        self.ask_destination(item, "copy")
    
    def ask_extract(self, item):
        self.ask_destination(item, "extract")
    
    def ask_destination(self, item, action):
        dialog = tk.Toplevel(self.root)
        dialog.title("Выберите место назначения")
        dialog.geometry("450x220")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.bg_color)
        tk.Label(dialog, text=f"Куда {action == 'extract' and 'распаковать' or 'скопировать'} '{item.name}'?",
                 font=("Segoe UI", 10), bg=self.bg_color, fg=self.fg_color).pack(pady=15)
        def use_default():
            dest = self.resolve_path(self.target_path.get())
            self.execute_action(item, action, str(dest))
            dialog.destroy()
        def choose_manually():
            folder = filedialog.askdirectory()
            if folder:
                self.execute_action(item, action, folder)
                dialog.destroy()
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(pady=10)
        btn1 = self.create_cut_small_button(btn_frame, "📂 В указанную сверху папку", use_default, width=28)
        btn1.pack(pady=5)
        btn2 = self.create_cut_small_button(btn_frame, "🔍 Выбрать самостоятельно", choose_manually, width=28)
        btn2.pack(pady=5)
        btn3 = self.create_cut_small_button(btn_frame, "❌ Отмена", dialog.destroy, width=28)
        btn3.pack(pady=5)
    
    def create_cut_small_button(self, parent, text, command, width=None):
        if text == "📁":
            btn_width = 40
            font_size = 12
        else:
            btn_width = max(55, len(text) * 10) if not width else width * 12
            font_size = 9
        btn_frame = tk.Frame(parent, bg=self.bg_color)
        canvas = tk.Canvas(btn_frame, width=btn_width, height=26, bg=self.bg_color, highlightthickness=0)
        canvas.pack()
        cut_size = 6
        points = [cut_size, 0, btn_width-cut_size, 0, btn_width, cut_size, btn_width, 26-cut_size, btn_width-cut_size, 26, cut_size, 26, 0, 26-cut_size, 0, cut_size]
        rect_id = canvas.create_polygon(points, fill=self.btn_bg, outline=self.btn_bg, smooth=False, tags="polygon")
        
        font_size = 12 if text == "📁" else font_size
        text_id = canvas.create_text(btn_width//2, 13, text=text, fill=self.btn_fg, font=("Segoe UI", font_size), tags="text")
        
        def on_click(e):
            command()
        canvas.tag_bind(rect_id, "<Button-1>", on_click)
        canvas.tag_bind(text_id, "<Button-1>", on_click)
        canvas.config(cursor="hand2")
        return btn_frame
    
    def execute_action(self, item, action, destination):
        try:
            os.makedirs(destination, exist_ok=True)
            if action == "copy":
                if item.is_dir():
                    shutil.copytree(item, Path(destination) / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, destination)
                messagebox.showinfo("Успех", f"✅ Скопировано: {item.name}")
            elif action == "extract":
                if item.suffix.lower() == '.zip':
                    with zipfile.ZipFile(item, 'r') as zip_ref:
                        zip_ref.extractall(destination)
                    messagebox.showinfo("Успех", f"✅ Распакован ZIP: {item.name}")
                elif item.suffix.lower() == '.rar':
                    messagebox.showinfo("RAR", f"Файл {item.name} скопирован как есть.\nДля распаковки RAR требуется WinRAR или 7-Zip.")
                    shutil.copy2(item, destination)
                else:
                    messagebox.showerror("Ошибка", "Файл не является архивом (.zip или .rar)")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось выполнить действие:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FlashManager(root)
    root.mainloop()
