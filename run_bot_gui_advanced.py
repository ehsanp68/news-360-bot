"""
News360 Rubika Bot - Glassmorphism UI - RESPONSIVE VERSION
✅ Responsive Design - سازگار با همه رزولوشن‌ها
✅ ScrolledFrame برای همه پنل‌ها
✅ Auto-scroll در مانیتورهای کوچک
✅ Minimum window size
✅ Telegram @akhbarefori → Rubika
✅ سبک خبری + تشخیص دقیق فوری/وایرال
✅ F11 Fullscreen Toggle
✅ انتشار فقط و فقط در کانال روبیکا (Rubika-only)
✅ فقط متن خبر بدون لینک و منبع
"""
import tkinter as tk
from tkinter import scrolledtext, messagebox, Canvas
from tkinter import font
import asyncio
import threading
from datetime import datetime, timedelta
import sys
import os
import io
import psutil

# ==================== ✅ رفع مشکل لاگ در CMD ====================
try:
    if sys.stdout and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'
except Exception as e:
    print(f"Warning: Could not set UTF-8 encoding: {e}")


# ==================== ✅ ✅ ✅ کلاس ScrolledFrame (جدید) ====================
class ScrolledFrame(tk.Frame):
    """✅ فریم اسکرول‌پذیر - برای responsive design
    
    استفاده:
        sf = ScrolledFrame(parent, bg='black')
        sf.pack(fill=tk.BOTH, expand=True)
        # محتوا را به sf.interior اضافه کنید
        tk.Label(sf.interior, text="Hello").pack()
    """
    def __init__(self, parent, *args, **kw):
        tk.Frame.__init__(self, parent, *args, **kw)
        
        # ✅ ایجاد Canvas و Scrollbar
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0,
                               bg=kw.get('bg', '#0a0e27'))
        self.scrollbar = tk.Scrollbar(self, orient="vertical", 
                                     command=self.canvas.yview,
                                     bg='#1a2540', troughcolor='#0f1729',
                                     width=12)
        
        # ✅ فریم داخلی برای محتوا
        self.interior = tk.Frame(self.canvas, bg=kw.get('bg', '#0a0e27'))
        
        # ✅ اتصال رویدادها
        self.interior_id = self.canvas.create_window((0, 0), 
                                                     window=self.interior, 
                                                     anchor="nw")
        
        # ✅ تنظیم اسکرول وقتی محتوا تغییر می‌کند
        self.interior.bind('<Configure>', self._on_interior_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        # ✅ اتصال Canvas به Scrollbar
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # ✅ Layout
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # ✅ پشتیبانی از Mouse Wheel
        self._bind_mousewheel()
    
    def _on_interior_configure(self, event):
        """✅ به‌روزرسانی ناحیه اسکرول"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):
        """✅ تنظیم عرض interior به اندازه Canvas"""
        canvas_width = event.width
        self.canvas.itemconfig(self.interior_id, width=canvas_width)
    
    def _bind_mousewheel(self):
        """✅ پشتیبانی از Mouse Wheel"""
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.interior.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def _on_mousewheel(self, event):
        """✅ اسکرول با Mouse Wheel"""
        # ویندوز
        if sys.platform == 'win32':
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # لینوکس
        elif event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")


# ==================== CUSTOM FONTS LOADER ====================
class FontManager:
    def __init__(self, fonts_dir="fonts"):
        self.fonts_dir = fonts_dir
        self.fonts = {}
        self.poppins_bold = None
        self.load_custom_fonts()

    def load_custom_fonts(self):
        if not os.path.exists(self.fonts_dir):
            self.use_default_fonts()
            return
        try:
            poppins_path = os.path.join(self.fonts_dir, "Poppins-Bold.ttf")
            if os.path.exists(poppins_path):
                self.poppins_bold = (poppins_path, 28)
            else:
                self.poppins_bold = ("Helvetica", 28, "bold")
            self.load_font_if_exists("JetBrains-Mono.ttf", "timer", size=28)
            self.load_font_if_exists("Inter-Bold.ttf", "header", size=11)
            self.load_font_if_exists("Roboto-Regular.ttf", "body", size=10)
            self.load_font_if_exists("Courier-Prime.ttf", "console", size=9)
            self.use_defaults_for_missing()
        except:
            self.use_default_fonts()

    def load_font_if_exists(self, filename, font_name, size=12):
        font_path = os.path.join(self.fonts_dir, filename)
        try:
            if os.path.exists(font_path):
                self.fonts[font_name] = (font_path, size)
                return True
        except:
            pass
        return False

    def use_defaults_for_missing(self):
        defaults = {
            "title": ("Helvetica", 28, "bold"),
            "timer": ("Courier New", 28, "bold"),
            "header": ("Segoe UI", 11, "bold"),
            "body": ("Segoe UI", 10),
            "console": ("Consolas", 9),
            "small": ("Segoe UI", 9),
            "tiny": ("Segoe UI", 8),
            "micro": ("Segoe UI", 7),
        }
        for key, default_font in defaults.items():
            if key not in self.fonts:
                self.fonts[key] = default_font

    def use_default_fonts(self):
        self.fonts = {
            "title": ("Helvetica", 28, "bold"),
            "timer": ("Courier New", 28, "bold"),
            "header": ("Segoe UI", 11, "bold"),
            "body": ("Segoe UI", 10),
            "console": ("Consolas", 9),
            "small": ("Segoe UI", 9),
            "tiny": ("Segoe UI", 8),
            "micro": ("Segoe UI", 7),
        }
        self.poppins_bold = ("Helvetica", 28, "bold")

    def get_font(self, name):
        return self.fonts.get(name, self.fonts.get("body", ("Segoe UI", 10)))


# ==================== LOAD BOT ====================
try:
    from bot import (SmartNewsBot, RUBIKA_BOT_TOKEN, RUBIKA_CHANNEL_ID,
                     NEWS_SOURCES,
                     load_rubika_config, save_rubika_config)
except ImportError as e:
    print(f"❌ Error loading bot: {e}")
    print("Make sure bot.py exists in the same directory!")
    sys.exit(1)
except Exception as e:
    print(f"❌ Critical error: {e}")
    sys.exit(1)


class GlassmorphicUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("News360 Rubika Bot - Responsive")

        self.root.attributes('-topmost', True)
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        # ✅ ✅ ✅ تنظیم حداقل اندازه پنجره
        # این باعث می‌شود کاربر نتواند پنجره را کوچک‌تر از این کند
        self.root.minsize(1280, 720)  # حداقل HD
        
        try:
            self.root.state('zoomed')
        except:
            # ✅ استفاده از 95% از صفحه برای جلوگیری از overflow
            w = int(self.screen_width * 0.95)
            h = int(self.screen_height * 0.92)
            x = int((self.screen_width - w) / 2)
            y = int((self.screen_height - h) / 2)
            self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.root.configure(bg="#0a0e27")
        self.is_fullscreen = False

        self.font_manager = FontManager(fonts_dir="fonts")

        self.colors = {
            'glass_dark': '#0f1729',
            'glass_light': '#1a2540',
            'glass_lighter': '#252f4d',
            'neon_blue': '#00d4ff',
            'neon_purple': '#b540ff',
            'neon_pink': '#ff00ff',
            'neon_cyan': '#00ffff',
            'neon_green': '#39ff14',
            'neon_orange': '#ff6b35',
            'neon_red': '#ff0055',
            'neon_yellow': '#ffd700',
            'bg_main': '#0a0e27',
            'bg_gradient_top': '#1a0033',
            'bg_gradient_bottom': '#000a2e',
            'text_primary': '#e0e6ff',
            'text_secondary': '#8899cc',
            'text_muted': '#556b9f',
        }

        self.bot = None
        self.bot_thread = None
        self.is_running = False
        self.fetch_interval = 5 * 60
        self.next_fetch_time = None
        self.connection_status = "OFFLINE"
        self.connection_color = self.colors['neon_pink']
        self.category_labels = {}
        # ✅ فقط روبیکا (تنها مقصد انتشار)
        self.platform_status = {
            'rubika': False,
        }
        self.platform_indicators = {}
        self.rss_status_labels = {}
        self.cpu_percent = 0
        self.ram_percent = 0
        self.cpu_label = None
        self.ram_label = None
        self.bot_start_time = None
        self.uptime_label = None
        self.viral_label = None
        self.breaking_label = None

        self.algorithm_info_label = None
        self.step_display_label = None

        self.create_glassmorphic_ui()

        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<Escape>', self.exit_fullscreen)
        # ✅ ✅ ✅ اضافه کردن Resize Handler برای responsive
        self.root.bind('<Configure>', self.on_window_resize)

        self.update_time()
        self.update_timer()
        self.update_stats()
        self.update_system_monitor()
        self.check_connection_status()
        self.update_platform_status()
        self.update_rss_status()
        self.update_uptime()
        self.update_algorithm_step_display()

    # ==================== ✅ ✅ ✅ Resize Handler ====================
    def on_window_resize(self, event):
        """✅ وقتی پنجره تغییر اندازه می‌دهد، ScrolledFrame ها به‌روز می‌شوند"""
        # این رویداد به طور خودکار توسط ScrolledFrame مدیریت می‌شود
        # اما می‌توانیم اینجا کارهای اضافی انجام دهیم
        pass

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.root.attributes('-fullscreen', True)
            self.log("🖥️ Fullscreen mode: ON (F11)", "info")
        else:
            self.root.attributes('-fullscreen', False)
            try:
                self.root.state('zoomed')
            except:
                w = int(self.screen_width * 0.95)
                h = int(self.screen_height * 0.92)
                self.root.geometry(f"{w}x{h}+0+0")
            self.log("🖥️ Fullscreen mode: OFF (Status Bar visible)", "info")

    def exit_fullscreen(self, event=None):
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.root.attributes('-fullscreen', False)
            try:
                self.root.state('zoomed')
            except:
                w = int(self.screen_width * 0.95)
                h = int(self.screen_height * 0.92)
                self.root.geometry(f"{w}x{h}+0+0")

    # ==================== نمایش الگوریتم انتشار ====================
    def update_algorithm_step_display(self):
        if self.is_running and self.bot and self.step_display_label:
            self.step_display_label.config(
                text=f"📊 Queue: {len(self.bot.pending_news)} | Next post: {int(self.bot._post_wait_seconds())}s")
        self.root.after(1000, self.update_algorithm_step_display)

    def force_fetch(self):
        if not self.is_running or not self.bot:
            messagebox.showwarning("Warning", "Bot is not running!")
            return
        self.bot.last_fetch_time = None
        self.log("🔄 Force fetch triggered by user", "warning")
        messagebox.showinfo("Force Fetch", "✅ Fetch will start in next cycle")

    # ==================== ✅ ✅ ✅ UI BUILD - RESPONSIVE ====================
    def create_glassmorphic_ui(self):
        bg_frame = tk.Frame(self.root, bg=self.colors['bg_main'])
        bg_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.create_gradient_canvas(
            bg_frame, self.screen_width, self.screen_height,
            self.colors['bg_gradient_top'],
            self.colors['bg_gradient_bottom']
        ).place(relx=0, rely=0, relwidth=1, relheight=1)

        # ✅ ✅ ✅ Header - ارتفاع ثابت (همیشه دیده می‌شود)
        self.create_header()
        self.create_timer_bar()
        self.create_top_info_bar()

        # ✅ ✅ ✅ Main Container - فضای باقی‌مانده
        main_container = tk.Frame(self.root, bg=self.colors['bg_main'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))

        # ✅ ✅ ✅ LEFT PANEL - ScrolledFrame
        # ✅ حذف pack_propagate و width ثابت
        left_sf = ScrolledFrame(main_container, bg=self.colors['bg_main'])
        left_sf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # ✅ تنظیم حداقل عرض
        left_sf.canvas.configure(width=320)
        
        self.create_stats_section(left_sf.interior)
        self.create_system_monitor_section(left_sf.interior)
        self.create_algorithm_section(left_sf.interior)

        # ✅ ✅ ✅ MIDDLE PANEL - ScrolledFrame
        middle_sf = ScrolledFrame(main_container, bg=self.colors['bg_main'])
        middle_sf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        middle_sf.canvas.configure(width=380)
        
        self.create_fetch_interval_section(middle_sf.interior)
        self.create_controls_section(middle_sf.interior)

        # ✅ ✅ ✅ RIGHT PANEL - ScrolledFrame
        right_sf = ScrolledFrame(main_container, bg=self.colors['bg_main'])
        right_sf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        right_sf.canvas.configure(width=450)
        
        self.create_console_section(right_sf.interior)

        # ✅ ✅ ✅ EXTRA PANEL - ScrolledFrame
        extra_sf = ScrolledFrame(main_container, bg=self.colors['bg_main'])
        extra_sf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        extra_sf.canvas.configure(width=320)
        
        self.create_rubika_settings_section(extra_sf.interior)
        self.create_platform_status_section(extra_sf.interior)
        self.create_rss_status_section(extra_sf.interior)

        # ✅ Footer - ارتفاع ثابت
        self.create_footer()

    def create_header(self):
        header_glass = self.create_glass_frame(
            self.root, bg_color=self.colors['glass_dark'],
            border_color=self.colors['neon_cyan'], border_width=3
        )
        header_glass.pack(fill=tk.X, padx=10, pady=(5, 3))

        tk.Label(
            header_glass, text="NEWS 360 SMART BOT",
            font=self.get_bold_font(28),
            bg=self.colors['glass_dark'], fg=self.colors['neon_blue']
        ).pack(pady=(3, 0))

        tk.Label(
            header_glass,
            text="Telegram @akhbarefori → Rubika • Text only",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_dark'], fg=self.colors['neon_purple']
        ).pack(pady=(0, 3))

    def create_timer_bar(self):
        timer_glass = self.create_glass_frame(
            self.root, bg_color=self.colors['glass_lighter'],
            border_color=self.colors['neon_pink'], border_width=3
        )
        timer_glass.pack(fill=tk.X, padx=10, pady=(0, 3))

        timer_inner = tk.Frame(timer_glass, bg=self.colors['glass_lighter'])
        timer_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=3)

        self.timer_label = tk.Label(
            timer_inner, text="30:00",
            font=("Courier New", 20, "bold"),
            bg=self.colors['glass_lighter'], fg=self.colors['neon_pink']
        )
        self.timer_label.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(
            timer_inner, text="⏱ NEXT FETCH CYCLE",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_lighter'], fg=self.colors['neon_cyan']
        ).pack(side=tk.LEFT)

    def create_top_info_bar(self):
        info_glass = self.create_glass_frame(
            self.root, bg_color=self.colors['glass_light'],
            border_color=self.colors['neon_purple'], border_width=2
        )
        info_glass.pack(fill=tk.X, padx=10, pady=(0, 5))

        inner = tk.Frame(info_glass, bg=self.colors['glass_light'])
        inner.pack(fill=tk.X, padx=10, pady=5)

        self.time_label = tk.Label(
            inner, text="00:00:00",
            font=("Courier New", 16, "bold"),
            bg=self.colors['glass_light'], fg=self.colors['neon_cyan']
        )
        self.time_label.pack(side=tk.LEFT)

        _cfg_token, _cfg_channel = load_rubika_config()
        self.channel_label = tk.Label(
            inner, text=f"📡 Rubika: {_cfg_channel or '(تنظیم نشده)'}",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_light'], fg=self.colors['text_primary']
        )
        self.channel_label.pack(side=tk.LEFT, padx=20)

        self.uptime_label = tk.Label(
            inner, text="⏱ --:--:--",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_light'], fg=self.colors['neon_orange']
        )
        self.uptime_label.pack(side=tk.RIGHT, padx=(10, 0))

        self.status_label = tk.Label(
            inner, text="🔴 OFFLINE",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_light'], fg=self.colors['neon_pink']
        )
        self.status_label.pack(side=tk.RIGHT)

    # ==================== STATISTICS ====================
    def create_stats_section(self, parent):
        tk.Label(
            parent, text="▌ STATISTICS",
            font=self.font_manager.get_font("header"),
            bg=self.colors['bg_main'], fg=self.colors['neon_blue']
        ).pack(anchor=tk.W, pady=(5, 3))

        stats_glass = self.create_glass_frame(
            parent, bg_color=self.colors['glass_lighter'],
            border_color=self.colors['neon_blue'], border_width=2
        )
        stats_glass.pack(fill=tk.X, pady=(0, 5), padx=2)

        stats = [
            ('━━━ POOL STATS ━━━', None, None, self.colors['neon_cyan']),
            ('📊', 'TOTAL POOL SIZE', 'pool', self.colors['neon_blue']),
            ('', '', None, None),
            ('━━━ POST STATS ━━━', None, None, self.colors['neon_green']),
            ('✅', 'POSTED TODAY', 'posted', self.colors['neon_green']),
            ('⏱', 'PER HOUR', 'hour', self.colors['neon_cyan']),
            ('', '', None, None),
            ('', '', None, None),
            ('━━━ FILTER STATS ━━━', None, None, self.colors['neon_purple']),
            ('⏭', 'DUPLICATES', 'dups', self.colors['neon_purple']),
        ]

        self.stat_labels = {}
        for emoji, label, key, color in stats:
            if key is None:
                if label:
                    tk.Label(
                        stats_glass, text=f"{emoji}",
                        font=self.font_manager.get_font("tiny"),
                        bg=self.colors['glass_lighter'], fg=color
                    ).pack(fill=tk.X, padx=8, pady=(3, 1))
                else:
                    tk.Frame(stats_glass, bg=self.colors['glass_dark'], height=1
                    ).pack(fill=tk.X, padx=10, pady=2)
                continue

            row_frame = tk.Frame(stats_glass, bg=self.colors['glass_lighter'])
            row_frame.pack(fill=tk.X, padx=8, pady=1)

            tk.Label(
                row_frame, text=f"{emoji} {label}",
                font=self.font_manager.get_font("tiny"),
                bg=self.colors['glass_lighter'], fg=self.colors['text_secondary']
            ).pack(side=tk.LEFT)

            val_label = tk.Label(
                row_frame, text="0",
                font=self.font_manager.get_font("small"),
                bg=self.colors['glass_lighter'], fg=color
            )
            val_label.pack(side=tk.RIGHT)
            self.stat_labels[key] = val_label

        self.viral_label = self.stat_labels.get('viral')
        self.breaking_label = self.stat_labels.get('breaking')

    # ==================== SYSTEM MONITOR ====================
    def create_system_monitor_section(self, parent):
        tk.Label(
            parent, text="▌ SYSTEM MONITOR",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['bg_main'], fg=self.colors['neon_green']
        ).pack(anchor=tk.W, pady=(5, 2))

        monitor_glass = self.create_glass_frame(
            parent, bg_color=self.colors['glass_lighter'],
            border_color=self.colors['neon_green'], border_width=2
        )
        monitor_glass.pack(fill=tk.X, pady=(0, 5), padx=2)

        # CPU
        cpu_frame = tk.Frame(monitor_glass, bg=self.colors['glass_lighter'])
        cpu_frame.pack(fill=tk.X, padx=8, pady=(3, 1))

        cpu_info = tk.Frame(cpu_frame, bg=self.colors['glass_lighter'])
        cpu_info.pack(fill=tk.X)

        tk.Label(
            cpu_info, text="💻 CPU:",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_lighter'], fg=self.colors['text_secondary']
        ).pack(side=tk.LEFT)

        self.cpu_label = tk.Label(
            cpu_info, text="0.0%",
            font=self.font_manager.get_font("small"),
            bg=self.colors['glass_lighter'], fg=self.colors['neon_cyan']
        )
        self.cpu_label.pack(side=tk.RIGHT)

        cpu_progress_frame = tk.Frame(
            monitor_glass, bg=self.colors['glass_dark'],
            highlightthickness=1, highlightbackground=self.colors['neon_cyan']
        )
        cpu_progress_frame.pack(fill=tk.X, padx=8, pady=(0, 3))

        self.cpu_progress = tk.Canvas(
            cpu_progress_frame, bg=self.colors['glass_dark'],
            height=8, highlightthickness=0, relief=tk.FLAT, bd=0
        )
        self.cpu_progress.pack(fill=tk.X, padx=1, pady=1)

        # RAM
        ram_frame = tk.Frame(monitor_glass, bg=self.colors['glass_lighter'])
        ram_frame.pack(fill=tk.X, padx=8, pady=(1, 1))

        ram_info = tk.Frame(ram_frame, bg=self.colors['glass_lighter'])
        ram_info.pack(fill=tk.X)

        tk.Label(
            ram_info, text="🧠 RAM:",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_lighter'], fg=self.colors['text_secondary']
        ).pack(side=tk.LEFT)

        self.ram_label = tk.Label(
            ram_info, text="0.0%",
            font=self.font_manager.get_font("small"),
            bg=self.colors['glass_lighter'], fg=self.colors['neon_pink']
        )
        self.ram_label.pack(side=tk.RIGHT)

        ram_progress_frame = tk.Frame(
            monitor_glass, bg=self.colors['glass_dark'],
            highlightthickness=1, highlightbackground=self.colors['neon_pink']
        )
        ram_progress_frame.pack(fill=tk.X, padx=8, pady=(0, 3))

        self.ram_progress = tk.Canvas(
            ram_progress_frame, bg=self.colors['glass_dark'],
            height=8, highlightthickness=0, relief=tk.FLAT, bd=0
        )
        self.ram_progress.pack(fill=tk.X, padx=1, pady=1)

        info_frame = tk.Frame(monitor_glass, bg=self.colors['glass_lighter'])
        info_frame.pack(fill=tk.X, padx=8, pady=(0, 3))

        self.sys_info_label = tk.Label(
            info_frame, text="⚡ Monitoring...",
            font=self.font_manager.get_font("micro"),
            bg=self.colors['glass_lighter'], fg=self.colors['text_muted']
        )
        self.sys_info_label.pack(side=tk.LEFT)

    # ==================== PUBLISH ALGORITHM ====================
    def create_algorithm_section(self, parent):
        tk.Label(
            parent, text="▌ NEWS RELAY",
            font=self.font_manager.get_font("header"),
            bg=self.colors['bg_main'], fg=self.colors['neon_orange']
        ).pack(anchor=tk.W, pady=(5, 3))

        algo_glass = self.create_glass_frame(
            parent, bg_color=self.colors['glass_lighter'],
            border_color=self.colors['neon_orange'], border_width=2
        )
        algo_glass.pack(fill=tk.X, pady=(0, 5), padx=2)

        tk.Label(
            algo_glass, text="📥 Telegram @akhbarefori",
            font=self.font_manager.get_font("header"),
            bg=self.colors['glass_lighter'], fg=self.colors['neon_orange']
        ).pack(anchor=tk.W, padx=10, pady=(5, 0))

        tk.Label(
            algo_glass,
            text="FIFO • حداقل ۵ دقیقه فاصله بین پست‌ها",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_lighter'], fg=self.colors['text_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(0, 3))

        status_frame = tk.Frame(
            algo_glass, bg=self.colors['glass_dark'],
            highlightthickness=2, highlightbackground=self.colors['neon_orange']
        )
        status_frame.pack(fill=tk.X, padx=10, pady=(5, 5))

        self.algorithm_info_label = tk.Label(
            status_frame,
            text="✅ Telegram → Rubika",
            font=self.font_manager.get_font("small"),
            bg=self.colors['glass_dark'], fg=self.colors['neon_orange']
        )
        self.algorithm_info_label.pack(pady=(5, 2))

        self.step_display_label = tk.Label(
            status_frame,
            text="📊 Queue: 0",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_dark'], fg=self.colors['neon_yellow']
        )
        self.step_display_label.pack(pady=(0, 5))

    # ==================== CATEGORIES ====================
    def create_categories_section(self, parent):
        tk.Label(
            parent, text="▌ CATEGORIES",
            font=self.font_manager.get_font("header"),
            bg=self.colors['bg_main'], fg=self.colors['neon_purple']
        ).pack(anchor=tk.W, pady=(5, 3))

        cat_glass = self.create_glass_frame(
            parent, bg_color=self.colors['glass_lighter'],
            border_color=self.colors['neon_purple'], border_width=2
        )
        cat_glass.pack(fill=tk.X, pady=(0, 5), padx=2)

        categories = [
            ('🏛', 'Politics', 'سیاسی', '#6667ab'),
            ('💰', 'Economy', 'اقتصادی', '#bb78a8'),
            ('⚽', 'Sports', 'ورزشی', '#ed8936'),
            ('💻', 'Technology', 'فناوری', '#4299e1'),
            ('🌍', 'International', 'بین‌الملل', '#f9aeae'),
            ('🚨', 'Accidents', 'حوادث', '#f56565'),
            ('🎭', 'Culture', 'فرهنگی', '#ed64a6'),
            ('🔬', 'Science', 'علمی', '#b2ac38'),
            ('🏥', 'Health', 'بهداشت', '#fc8181'),
            ('👥', 'Social', 'اجتماعی', '#a0aec0'),
            ('🌱', 'Environment', 'محیط‌زیست', '#68d391'),
            ('📰', 'General', 'عمومی', '#718096'),
        ]

        for emoji, english_name, persian_name, color in categories:
            cat_item = tk.Frame(cat_glass, bg=self.colors['glass_lighter'])
            cat_item.pack(fill=tk.X, padx=6, pady=1)

            tk.Label(
                cat_item, text=f"{emoji} {english_name}",
                font=self.font_manager.get_font("tiny"),
                bg=self.colors['glass_lighter'], fg=self.colors['text_secondary']
            ).pack(side=tk.LEFT)

            count_label = tk.Label(
                cat_item, text="0",
                font=self.font_manager.get_font("small"),
                bg=self.colors['glass_lighter'], fg=color
            )
            count_label.pack(side=tk.RIGHT)
            self.category_labels[persian_name] = count_label

    # ==================== FETCH INTERVAL ====================
    def create_fetch_interval_section(self, parent):
        tk.Label(
            parent, text="▌ FETCH INTERVAL",
            font=self.font_manager.get_font("header"),
            bg=self.colors['bg_main'], fg=self.colors['neon_purple']
        ).pack(anchor=tk.W, pady=(5, 3))

        interval_glass = self.create_glass_frame(
            parent, bg_color=self.colors['glass_lighter'],
            border_color=self.colors['neon_purple'], border_width=2
        )
        interval_glass.pack(fill=tk.X, pady=(0, 5), padx=2)

        slider_frame = tk.Frame(interval_glass, bg=self.colors['glass_lighter'])
        slider_frame.pack(fill=tk.X, padx=8, pady=(5, 0))

        tk.Label(
            slider_frame, text="Interval:",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_lighter'], fg=self.colors['text_secondary']
        ).pack(side=tk.LEFT)

        self.interval_display = tk.Label(
            slider_frame, text="5 min",
            font=self.font_manager.get_font("small"),
            bg=self.colors['glass_lighter'], fg=self.colors['neon_blue']
        )
        self.interval_display.pack(side=tk.RIGHT)

        slider_container = tk.Frame(interval_glass, bg=self.colors['glass_lighter'])
        slider_container.pack(fill=tk.X, padx=8, pady=3)

        self.interval_slider = tk.Scale(
            slider_container, from_=1, to=60, orient=tk.HORIZONTAL,
            command=self.on_interval_change,
            bg=self.colors['glass_light'], fg=self.colors['neon_blue'],
            troughcolor=self.colors['glass_dark'],
            activebackground=self.colors['neon_cyan'],
            highlightthickness=0, relief=tk.FLAT, bd=0
        )
        self.interval_slider.set(5)
        self.interval_slider.pack(fill=tk.X)

        buttons_frame = tk.Frame(interval_glass, bg=self.colors['glass_lighter'])
        buttons_frame.pack(fill=tk.X, padx=6, pady=3)

        for interval in [1, 5, 15, 30, 60]:
            btn = tk.Button(
                buttons_frame, text=f"{interval}m",
                command=lambda i=interval: self.set_interval(i),
                font=self.font_manager.get_font("tiny"),
                bg=self.colors['glass_light'], fg=self.colors['text_secondary'],
                activebackground=self.colors['neon_cyan'],
                activeforeground=self.colors['glass_dark'],
                relief=tk.FLAT, bd=0, padx=3, pady=1, cursor='hand2'
            )
            btn.pack(side=tk.LEFT, padx=1, fill=tk.BOTH, expand=True)

        tk.Button(
            interval_glass, text="✅ APPLY",
            command=self.apply_interval_settings,
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['neon_green'], fg="#000000",
            activebackground=self.colors['neon_cyan'],
            relief=tk.FLAT, bd=0, padx=8, pady=3, cursor='hand2'
        ).pack(fill=tk.X, padx=8, pady=(0, 5))

    # ==================== CONTROL PANEL ====================
    def create_controls_section(self, parent):
        tk.Label(
            parent, text="▌ CONTROL PANEL",
            font=self.font_manager.get_font("header"),
            bg=self.colors['bg_main'], fg=self.colors['neon_cyan']
        ).pack(anchor=tk.W, pady=(5, 3))

        controls_glass = self.create_glass_frame(
            parent, bg_color=self.colors['glass_lighter'],
            border_color=self.colors['neon_cyan'], border_width=2
        )
        controls_glass.pack(fill=tk.X, pady=(0, 5), padx=2)

        button_style = {
            'font': self.font_manager.get_font("tiny"),
            'relief': tk.FLAT, 'bd': 0,
            'width': 10, 'height': 2,
            'cursor': 'hand2'
        }

        row1 = tk.Frame(controls_glass, bg=self.colors['glass_lighter'])
        row1.pack(fill=tk.X, padx=6, pady=(5, 3))

        self.start_btn = tk.Button(
            row1, text="▶ START", command=self.start_bot,
            bg=self.colors['neon_green'], fg="#000000",
            activebackground=self.colors['neon_cyan'], **button_style
        )
        self.start_btn.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.BOTH)

        self.stop_btn = tk.Button(
            row1, text="⏹ STOP", command=self.stop_bot,
            bg=self.colors['neon_pink'], fg="#ffffff",
            activebackground='#ff1493', state=tk.DISABLED, **button_style
        )
        self.stop_btn.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.BOTH)

        tk.Button(
            row1, text="🔽 MIN", command=self.minimize_window,
            bg=self.colors['neon_cyan'], fg="#000000",
            activebackground=self.colors['neon_green'], **button_style
        ).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.BOTH)

        tk.Button(
            row1, text="🚪 EXIT", command=self.exit_application,
            bg=self.colors['neon_purple'], fg="#ffffff",
            activebackground='#8b00ff', **button_style
        ).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.BOTH)

        row2 = tk.Frame(controls_glass, bg=self.colors['glass_lighter'])
        row2.pack(fill=tk.X, padx=6, pady=(3, 5))

        tk.Button(
            row2, text="🗑 LOGS", command=self.clear_logs,
            bg=self.colors['glass_light'], fg=self.colors['neon_purple'],
            activebackground=self.colors['glass_lighter'], **button_style
        ).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.BOTH)

        tk.Button(
            row2, text="🔄 FETCH", command=self.force_fetch,
            bg=self.colors['neon_blue'], fg="#000000",
            activebackground=self.colors['neon_cyan'], **button_style
        ).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.BOTH)


    # ==================== RUBIKA SETTINGS ====================
    def create_rubika_settings_section(self, parent):
        tk.Label(
            parent, text="▌ RUBIKA SETTINGS",
            font=self.font_manager.get_font("header"),
            bg=self.colors['bg_main'], fg=self.colors['neon_green']
        ).pack(anchor=tk.W, pady=(5, 3))

        settings_glass = self.create_glass_frame(
            parent, bg_color=self.colors['glass_lighter'],
            border_color=self.colors['neon_green'], border_width=2
        )
        settings_glass.pack(fill=tk.X, pady=(0, 5), padx=2)

        cfg_token, cfg_channel = load_rubika_config()
        self.rubika_token_var = tk.StringVar(value=cfg_token)
        self.rubika_channel_var = tk.StringVar(value=cfg_channel)
        self.show_token_var = tk.BooleanVar(value=False)

        tk.Label(
            settings_glass, text="🔑 Bot Token (توکن ربات روبیکا):",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_lighter'], fg=self.colors['text_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(6, 0))

        self.token_entry = tk.Entry(
            settings_glass, textvariable=self.rubika_token_var, show="•",
            bg=self.colors['glass_dark'], fg=self.colors['neon_green'],
            insertbackground=self.colors['neon_green'],
            relief=tk.FLAT, bd=0, font=self.font_manager.get_font("small")
        )
        self.token_entry.pack(fill=tk.X, padx=10, pady=(2, 2), ipady=4)

        tk.Checkbutton(
            settings_glass, text="نمایش توکن", variable=self.show_token_var,
            command=self._toggle_token_visibility,
            bg=self.colors['glass_lighter'], fg=self.colors['text_muted'],
            activebackground=self.colors['glass_lighter'],
            activeforeground=self.colors['text_secondary'],
            selectcolor=self.colors['glass_dark'],
            font=self.font_manager.get_font("tiny"),
            relief=tk.FLAT, bd=0, highlightthickness=0
        ).pack(anchor=tk.W, padx=8)

        tk.Label(
            settings_glass, text="📢 Channel ID (آیدی کانال روبیکا):",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_lighter'], fg=self.colors['text_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(4, 0))

        self.channel_entry = tk.Entry(
            settings_glass, textvariable=self.rubika_channel_var,
            bg=self.colors['glass_dark'], fg=self.colors['neon_cyan'],
            insertbackground=self.colors['neon_cyan'],
            relief=tk.FLAT, bd=0, font=self.font_manager.get_font("small")
        )
        self.channel_entry.pack(fill=tk.X, padx=10, pady=(2, 6), ipady=4)

        tk.Button(
            settings_glass, text="💾 SAVE SETTINGS",
            command=self.save_rubika_settings,
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['neon_green'], fg="#000000",
            activebackground=self.colors['neon_cyan'],
            relief=tk.FLAT, bd=0, padx=8, pady=4, cursor='hand2'
        ).pack(fill=tk.X, padx=10, pady=(0, 4))

        tk.Label(
            settings_glass, text="💡 ربات را در کانال روبیکا ادمین کنید",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_lighter'], fg=self.colors['text_muted']
        ).pack(padx=10, pady=(0, 6))

    def _toggle_token_visibility(self):
        try:
            self.token_entry.config(show="" if self.show_token_var.get() else "•")
        except:
            pass

    def save_rubika_settings(self):
        token = self.rubika_token_var.get().strip()
        channel = self.rubika_channel_var.get().strip()
        if not token or not channel:
            messagebox.showwarning(
                "تنظیمات روبیکا",
                "توکن ربات و آیدی کانال روبیکا را کامل وارد کنید!"
            )
            return
        try:
            save_rubika_config(token, channel)
        except Exception as e:
            messagebox.showerror("خطا", f"❌ ذخیره تنظیمات ناموفق: {e}")
            return
        try:
            self.channel_label.config(text=f"📡 Rubika: {channel}")
        except:
            pass
        self.log(f"💾 Rubika settings saved | Channel: {channel}", "success")
        if self.is_running:
            messagebox.showinfo(
                "تنظیمات روبیکا",
                "✅ تنظیمات ذخیره شد.\nبرای اعمال، ربات را Stop و دوباره Start کنید."
            )
        else:
            messagebox.showinfo("تنظیمات روبیکا", "✅ تنظیمات ذخیره شد.")

    # ==================== PLATFORM STATUS ====================
    def create_platform_status_section(self, parent):
        tk.Label(
            parent, text="▌ PLATFORM STATUS",
            font=self.font_manager.get_font("header"),
            bg=self.colors['bg_main'], fg=self.colors['neon_cyan']
        ).pack(anchor=tk.W, pady=(5, 3))

        platform_glass = self.create_glass_frame(
            parent, bg_color=self.colors['glass_lighter'],
            border_color=self.colors['neon_cyan'], border_width=2
        )
        platform_glass.pack(fill=tk.X, pady=(0, 5), padx=2)

        # ✅ فقط روبیکا به عنوان مقصد انتشار
        platforms = [
            ('💎', 'Rubika Channel', 'rubika'),
        ]

        tk.Label(
            platform_glass, text="📤 انتشار اخبار فقط در کانال روبیکا",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_lighter'], fg=self.colors['neon_green']
        ).pack(anchor=tk.W, padx=10, pady=(5, 0))

        for emoji, name, key in platforms:
            row_frame = tk.Frame(platform_glass, bg=self.colors['glass_lighter'])
            row_frame.pack(fill=tk.X, padx=10, pady=3)

            tk.Label(
                row_frame, text=f"{emoji} {name}:",
                font=self.font_manager.get_font("tiny"),
                bg=self.colors['glass_lighter'], fg=self.colors['text_secondary']
            ).pack(side=tk.LEFT)

            indicator = tk.Label(
                row_frame, text="🔴 OFFLINE",
                font=self.font_manager.get_font("small"),
                bg=self.colors['glass_lighter'], fg=self.colors['neon_pink']
            )
            indicator.pack(side=tk.RIGHT)
            self.platform_indicators[key] = indicator

    def update_platform_status(self):
        # ✅ وضعیت واقعی اتصال به روبیکا از خود ربات خوانده می‌شود
        if self.is_running and self.bot:
            self.platform_status['rubika'] = bool(getattr(self.bot, 'rubika_connected', False))
        else:
            self.platform_status['rubika'] = False

        try:
            for platform, is_online in self.platform_status.items():
                if platform in self.platform_indicators:
                    if is_online:
                        self.platform_indicators[platform].config(
                            text="🟢 ONLINE", fg=self.colors['neon_green']
                        )
                    else:
                        self.platform_indicators[platform].config(
                            text="🔴 OFFLINE", fg=self.colors['neon_pink']
                        )
        except:
            pass

        self.root.after(3000, self.update_platform_status)

    # ==================== RSS STATUS ====================
    def create_rss_status_section(self, parent):
        tk.Label(
            parent, text="▌ TELEGRAM SOURCE STATUS",
            font=self.font_manager.get_font("header"),
            bg=self.colors['bg_main'], fg=self.colors['neon_green']
        ).pack(anchor=tk.W, pady=(5, 3))

        rss_glass = self.create_glass_frame(
            parent, bg_color=self.colors['glass_lighter'],
            border_color=self.colors['neon_green'], border_width=2
        )
        rss_glass.pack(fill=tk.BOTH, expand=True, pady=(0, 5), padx=2)

        # ✅ لیست منابع مستقیماً از bot.py خوانده می‌شود (فقط داخلی)
        all_sources = list(NEWS_SOURCES.keys())

        for source in all_sources:
            row = tk.Frame(rss_glass, bg=self.colors['glass_lighter'])
            row.pack(fill=tk.X, padx=6, pady=1)

            tk.Label(row, text=source,
                    font=self.font_manager.get_font("tiny"),
                    bg=self.colors['glass_lighter'], fg=self.colors['text_secondary'],
                    anchor='w', width=12
            ).pack(side=tk.LEFT)

            status_label = tk.Label(row, text="⚪ Checking...",
                                   font=self.font_manager.get_font("tiny"),
                                   bg=self.colors['glass_lighter'], fg=self.colors['text_muted'])
            status_label.pack(side=tk.RIGHT)
            self.rss_status_labels[source] = status_label

        self.rss_summary = tk.Label(
            rss_glass, text="0/0 sources active (0%)",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_lighter'], fg=self.colors['neon_cyan']
        )
        self.rss_summary.pack(side=tk.BOTTOM, pady=3)

    def update_rss_status(self):
        if self.is_running and self.bot:
            try:
                if hasattr(self.bot, 'rss_health_check'):
                    health = self.bot.rss_health_check
                    active_count = 0
                    total_count = len(self.rss_status_labels)
                    for source, status_label in self.rss_status_labels.items():
                        status = health.get(source, 'unknown')
                        if status == 'online':
                            status_label.config(text="✅ Online", fg=self.colors['neon_green'])
                            active_count += 1
                        elif status == 'slow':
                            status_label.config(text="⚠ Slow", fg=self.colors['neon_blue'])
                            active_count += 1
                        elif status == 'offline':
                            status_label.config(text="❌ Offline", fg=self.colors['neon_pink'])
                        else:
                            status_label.config(text="⚪ Unknown", fg=self.colors['text_muted'])
                    percentage = int((active_count / total_count) * 100) if total_count > 0 else 0
                    self.rss_summary.config(
                        text=f"{active_count}/{total_count} sources active ({percentage}%)"
                    )
            except:
                pass

        self.root.after(10000, self.update_rss_status)

    # ==================== CONSOLE ====================
    def create_console_section(self, parent):
        tk.Label(
            parent, text="▌ SYSTEM CONSOLE",
            font=self.font_manager.get_font("header"),
            bg=self.colors['bg_main'], fg=self.colors['neon_cyan']
        ).pack(anchor=tk.W, pady=(5, 3))

        console_glass = self.create_glass_frame(
            parent, bg_color=self.colors['glass_dark'],
            border_color=self.colors['neon_cyan'], border_width=2
        )
        # ✅ ✅ ✅ Console با fill=BOTH و expand=True - اندازه خودکار
        console_glass.pack(fill=tk.BOTH, expand=True, padx=2)

        self.console = scrolledtext.ScrolledText(
            console_glass, bg=self.colors['glass_dark'],
            fg=self.colors['neon_green'],
            font=self.font_manager.get_font("console"),
            insertbackground=self.colors['neon_green'],
            wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=8, pady=6
        )
        self.console.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.console.tag_config("success", foreground=self.colors['neon_green'])
        self.console.tag_config("error", foreground=self.colors['neon_pink'])
        self.console.tag_config("info", foreground=self.colors['neon_cyan'])
        self.console.tag_config("warning", foreground=self.colors['neon_blue'])
        self.console.tag_config("system", foreground=self.colors['neon_purple'])

    # ==================== FOOTER ====================
    def create_footer(self):
        footer_container = tk.Frame(self.root, bg=self.colors['bg_main'])
        footer_container.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0, 5))

        connection_glass = self.create_glass_frame(
            footer_container, bg_color=self.colors['glass_light'],
            border_color=self.colors['neon_cyan'], border_width=2
        )
        connection_glass.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))

        connection_inner = tk.Frame(connection_glass, bg=self.colors['glass_light'])
        connection_inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        tk.Label(connection_inner, text="📡 Rubika:",
                font=self.font_manager.get_font("tiny"),
                bg=self.colors['glass_light'], fg=self.colors['text_secondary']
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.connection_indicator = tk.Label(
            connection_inner, text="🔴 OFFLINE",
            font=self.font_manager.get_font("small"),
            bg=self.colors['glass_light'], fg=self.connection_color
        )
        self.connection_indicator.pack(side=tk.LEFT)

        footer_glass = self.create_glass_frame(
            footer_container, bg_color=self.colors['glass_light'],
            border_color=self.colors['neon_blue'], border_width=1
        )
        footer_glass.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(
            footer_glass,
            text="◆ F11: Fullscreen | ESC: Exit | Responsive Design ◆",
            font=self.font_manager.get_font("tiny"),
            bg=self.colors['glass_light'], fg=self.colors['neon_blue']
        ).pack(pady=4)

    # ==================== UPDATE FUNCTIONS ====================
    def update_timer(self):
        if self.is_running:
            if self.next_fetch_time is None:
                self.next_fetch_time = datetime.now() + timedelta(seconds=self.fetch_interval)
            now = datetime.now()
            remaining = self.next_fetch_time - now
            if remaining.total_seconds() <= 0:
                self.next_fetch_time = datetime.now() + timedelta(seconds=self.fetch_interval)
                remaining = timedelta(seconds=self.fetch_interval)
            total_seconds = int(remaining.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
            if minutes == 0 and seconds <= 10:
                self.timer_label.config(fg='#ff0000')
            elif minutes <= 5:
                self.timer_label.config(fg='#ffff00')
            else:
                self.timer_label.config(fg=self.colors['neon_pink'])
        else:
            self.timer_label.config(text="--:--", fg=self.colors['text_muted'])

        self.root.after(1000, self.update_timer)

    def update_system_monitor(self):
        try:
            self.cpu_percent = psutil.cpu_percent(interval=0.1)
            self.cpu_label.config(text=f"{self.cpu_percent:.1f}%")

            ram = psutil.virtual_memory()
            self.ram_percent = ram.percent
            ram_used_gb = ram.used / (1024**3)
            self.ram_label.config(text=f"{self.ram_percent:.0f}% ({ram_used_gb:.1f}GB)")

            self.draw_progress_bar(self.cpu_progress, self.cpu_percent, self.colors['neon_cyan'])
            self.draw_progress_bar(self.ram_progress, self.ram_percent, self.colors['neon_pink'])

            if hasattr(self, 'sys_info_label'):
                cpu_color = "🟢" if self.cpu_percent < 50 else ("🟡" if self.cpu_percent < 80 else "🔴")
                ram_color = "🟢" if self.ram_percent < 50 else ("🟡" if self.ram_percent < 80 else "🔴")
                self.sys_info_label.config(
                    text=f"{cpu_color} CPU:{self.cpu_percent:.0f}% | {ram_color} RAM:{self.ram_percent:.0f}%"
                )
        except Exception as e:
            self.log(f"⚠ Monitor error: {e}", "warning")

        self.root.after(2000, self.update_system_monitor)

    def draw_progress_bar(self, canvas, percent, color):
        canvas.delete("all")
        try:
            self.root.update_idletasks()
        except:
            pass

        width = canvas.winfo_width()
        if width <= 1:
            try:
                width = canvas.master.winfo_width() - 10
            except:
                width = 300

        height = canvas.winfo_height()
        if height <= 1:
            height = 8

        canvas.create_rectangle(0, 0, width, height,
                               fill=self.colors['glass_dark'], outline="")

        filled_width = max(0, int((width * percent) / 100))

        if percent < 50:
            bar_color = self.colors['neon_green']
        elif percent < 80:
            bar_color = self.colors['neon_blue']
        else:
            bar_color = self.colors['neon_pink']

        if filled_width > 0:
            canvas.create_rectangle(0, 0, filled_width, height,
                                   fill=bar_color, outline="")
            canvas.create_rectangle(0, 0, filled_width, 2,
                                   fill='#ffffff', stipple='gray25', outline="")

    def check_connection_status(self):
        # ✅ اگر ترد ربات به دلیل خطای اتصال بسته شده، وضعیت UI را درست کن
        if self.is_running and self.bot_thread and not self.bot_thread.is_alive():
            self.log("⚠️ Bot thread exited (connection failed or stopped)", "warning")
            self.stop_bot()

        if self.is_running and self.bot and getattr(self.bot, 'rubika_connected', False):
            self.connection_status = "ONLINE"
            self.connection_color = self.colors['neon_green']
            indicator_text = "🟢 ONLINE"
        elif self.is_running and self.bot:
            self.connection_status = "CONNECTING"
            self.connection_color = self.colors['neon_yellow']
            indicator_text = "🟡 CONNECTING"
        else:
            self.connection_status = "OFFLINE"
            self.connection_color = self.colors['neon_pink']
            indicator_text = "🔴 OFFLINE"

        try:
            self.connection_indicator.config(text=indicator_text, fg=self.connection_color)
            if self.is_running:
                self.status_label.config(text=indicator_text, fg=self.connection_color)
        except:
            pass

        self.root.after(3000, self.check_connection_status)

    def update_uptime(self):
        if self.bot_start_time and self.is_running:
            delta = datetime.now() - self.bot_start_time
            total_seconds = int(delta.total_seconds())
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if days > 0:
                text = f"⏱ {days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                text = f"⏱ {hours:02d}:{minutes:02d}:{seconds:02d}"
            self.uptime_label.config(text=text)
        else:
            self.uptime_label.config(text="⏱ --:--:--")

        self.root.after(1000, self.update_uptime)

    def on_interval_change(self, value):
        interval_minutes = int(float(value))
        self.interval_display.config(text=f"{interval_minutes} min")

    def set_interval(self, minutes):
        self.interval_slider.set(minutes)
        self.interval_display.config(text=f"{minutes} min")

    def apply_interval_settings(self):
        selected_minutes = int(float(self.interval_slider.get()))
        self.fetch_interval = selected_minutes * 60
        if self.bot:
            self.bot.fetch_interval = self.fetch_interval
        self.next_fetch_time = datetime.now() + timedelta(seconds=self.fetch_interval)
        self.log(f"✅ Fetch interval changed to {selected_minutes} minutes", "success")
        messagebox.showinfo("Settings Applied",
                           f"Fetch interval set to {selected_minutes} minutes")

    def log(self, msg, tag="info"):
        t = datetime.now().strftime("%H:%M:%S")
        if "❌" in msg or "Error" in msg: tag = "error"
        elif "✅" in msg: tag = "success"
        elif "⚠" in msg: tag = "warning"
        elif "═" in msg or "▌" in msg or "FETCH" in msg: tag = "system"

        try:
            self.console.insert(tk.END, f"[{t}] {msg}\n", tag)
            self.console.see(tk.END)
        except Exception as e:
            try:
                safe_msg = msg.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                self.console.insert(tk.END, f"[{t}] {safe_msg}\n", tag)
                self.console.see(tk.END)
            except:
                pass

        try:
            self.root.update_idletasks()
        except:
            pass

    def update_time(self):
        try:
            t = datetime.now().strftime("%H:%M:%S")
            self.time_label.config(text=t)
        except:
            pass
        self.root.after(1000, self.update_time)

    def update_stats(self):
        if self.is_running and self.bot:
            try:
                self.stat_labels['pool'].config(text=str(len(self.bot.pending_news)))
                self.stat_labels['posted'].config(text=str(self.bot.daily_posts))
                self.stat_labels['hour'].config(text=str(self.bot.hourly_posts))
                self.stat_labels['dups'].config(text=str(self.bot.total_duplicates))

            except:
                pass

        self.root.after(2000, self.update_stats)

    def start_bot(self):
        if self.is_running:
            return

        # ✅ فقط روبیکا - توکن و کانال از بخش RUBIKA SETTINGS خوانده می‌شود
        token = self.rubika_token_var.get().strip() if hasattr(self, 'rubika_token_var') else RUBIKA_BOT_TOKEN
        channel = self.rubika_channel_var.get().strip() if hasattr(self, 'rubika_channel_var') else RUBIKA_CHANNEL_ID

        if not token:
            messagebox.showerror("خطا", "توکن ربات روبیکا تنظیم نشده!\nبخش RUBIKA SETTINGS را کامل کنید.")
            return
        if not channel:
            messagebox.showerror("خطا", "آیدی کانال روبیکا تنظیم نشده!\nبخش RUBIKA SETTINGS را کامل کنید.")
            return

        try:
            self.bot = SmartNewsBot(log_callback=self.log, bot_token=token, channel_id=channel)
        except ValueError as e:
            messagebox.showerror("خطا", str(e))
            return

        self.is_running = True
        self.bot_start_time = datetime.now()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="🟡 CONNECTING", fg=self.colors['neon_yellow'])
        self.next_fetch_time = datetime.now() + timedelta(seconds=self.fetch_interval)

        self.log("═══════════════════════════════════════════════", "system")
        self.log("🚀 SYSTEM BOOTING...", "success")
        self.log(f"⏱ Fetch cycle set to {self.fetch_interval//60} minutes", "info")
        self.log("📥 Telegram @akhbarefori: enabled", "success")
        self.log("✍️ News Style: ENABLED (سبک خبری برای همه خبرها)", "success")
        self.log(f"📤 Publishing target: Rubika channel {channel} ONLY", "success")
        self.log("📡 Initializing Rubika Connection...", "warning")

        self.bot.fetch_interval = self.fetch_interval

        self.bot_thread = threading.Thread(target=lambda: asyncio.run(self.bot.run()), daemon=True)
        self.bot_thread.start()

    def stop_bot(self):
        self.log("⛔ SHUTDOWN INITIATED", "error")
        if self.bot:
            self.bot.stop()
        self.is_running = False
        self.bot_start_time = None
        self.next_fetch_time = None
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="🔴 OFFLINE", fg=self.colors['neon_pink'])
        self.log("⏸ System Stopped", "warning")

    def clear_logs(self):
        self.console.delete(1.0, tk.END)
        self.log("🗑 Logs Cleared", "info")

    def minimize_window(self):
        try:
            self.root.iconify()
        except:
            pass

    def exit_application(self):
        if self.is_running:
            if messagebox.askyesno("EXIT", "Bot is running!\n\nStop bot and exit?"):
                self.stop_bot()
                self.root.after(500, self.close_window)
        else:
            if messagebox.askyesno("EXIT", "Are you sure you want to exit?"):
                self.close_window()

    def close_window(self):
        try:
            self.root.destroy()
        except:
            pass

    def on_close(self):
        self.exit_application()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.log("✅ SYSTEM READY", "success")
        self.log("💎 Rubika-only publishing: Active (فقط کانال روبیکا)", "success")
        self.log("📌 Responsive Design: Active", "success")
        self.log("📌 Minimum Size: 1280x720", "success")
        self.log("📌 Auto-Scroll: Enabled", "success")
        self.log("✍️ News Style: Active (سبک خبری برای همه خبرها)", "success")
        self.log("📌 Status Bar: Visible (maximized mode)", "success")
        self.log("🔘 F11: Toggle Fullscreen | ESC: Exit Fullscreen", "success")
        _token, _channel = load_rubika_config()
        if not _token or not _channel:
            self.log("⚠️ توکن/کانال روبیکا تنظیم نشده - بخش RUBIKA SETTINGS را کامل کنید", "warning")
        else:
            self.log(f"📢 Rubika channel: {_channel}", "info")
        self.root.mainloop()

    def get_bold_font(self, size=42):
        fonts_dir = "fonts"
        bold_fonts = ["Poppins-Bold.ttf", "Inter-Bold.ttf", "Roboto-Bold.ttf"]
        for font_name in bold_fonts:
            font_path = os.path.join(fonts_dir, font_name)
            if os.path.exists(font_path):
                try:
                    return font.Font(family=font_name.replace('.ttf', ''), size=size, weight="bold")
                except:
                    pass
        
        system_fonts = ["Segoe UI", "Arial", "Helvetica", "Tahoma"]
        for sys_font in system_fonts:
            try:
                return font.Font(family=sys_font, size=size, weight="bold")
            except:
                continue
        
        return font.Font(family="Helvetica", size=size, weight="bold")

    def create_gradient_canvas(self, parent, width, height, color1, color2):
        canvas = Canvas(parent, width=width, height=height, bg=color1,
                       highlightthickness=0, relief=tk.FLAT, bd=0)
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        for i in range(height):
            ratio = i / height
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            canvas.create_line(0, i, width, i, fill=f'#{r:02x}{g:02x}{b:02x}', width=1)
        return canvas

    def create_glass_frame(self, parent, bg_color='#1a2540', border_color='#00d4ff',
                          border_width=2, **kwargs):
        frame = tk.Frame(parent, bg=bg_color, relief=tk.FLAT, bd=0, **kwargs)
        def add_border(evt=None):
            try:
                frame.configure(highlightthickness=border_width,
                              highlightbackground=border_color)
            except:
                pass
        frame.after(10, add_border)
        return frame


# ==================== RUN ====================
if __name__ == "__main__":
    try:
        app = GlassmorphicUI()
        app.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")