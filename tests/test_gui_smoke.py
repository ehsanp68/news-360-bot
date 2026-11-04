"""
تست دود (Smoke Test) رابط گرافیکی بدون نیاز به نمایشگر/tkinter واقعی.
tkinter با یک نسخه ساختگی جایگزین می‌شود تا ساخت کل UI و منطق دکمه‌ها بررسی شود.
اجرا: python tests/test_gui_smoke.py
"""
import os
import sys
import json
import time
import tempfile
import types
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==================== Fake tkinter ====================
class FakeWidget:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        m = MagicMock()
        setattr(self, name, m)
        return m


class FakeVar:
    def __init__(self, value=None, **kwargs):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


def install_fake_tkinter():
    tk = types.ModuleType("tkinter")

    class FakeTk(FakeWidget):
        def winfo_screenwidth(self):
            return 1920

        def winfo_screenheight(self):
            return 1080

    tk.Tk = FakeTk
    tk.Frame = FakeWidget
    tk.Canvas = FakeWidget
    tk.Scrollbar = FakeWidget
    tk.Label = FakeWidget
    tk.Button = FakeWidget
    tk.Entry = FakeWidget
    tk.Checkbutton = FakeWidget
    tk.Scale = FakeWidget
    tk.Text = FakeWidget
    tk.Toplevel = FakeWidget
    tk.StringVar = FakeVar
    tk.BooleanVar = FakeVar
    for const in ("BOTH", "LEFT", "RIGHT", "TOP", "BOTTOM", "X", "Y", "W", "E",
                  "END", "FLAT", "HORIZONTAL", "VERTICAL", "WORD", "NORMAL",
                  "DISABLED", "CENTER", "N", "S", "NW", "NE", "SW", "SE", "TRUE", "FALSE"):
        setattr(tk, const, const)

    scrolledtext = types.ModuleType("tkinter.scrolledtext")
    scrolledtext.ScrolledText = FakeWidget
    messagebox = types.ModuleType("tkinter.messagebox")
    for fn in ("showinfo", "showwarning", "showerror", "askyesno"):
        setattr(messagebox, fn, MagicMock())
    font_mod = types.ModuleType("tkinter.font")
    font_mod.Font = MagicMock()

    tk.scrolledtext = scrolledtext
    tk.messagebox = messagebox
    tk.font = font_mod

    sys.modules["tkinter"] = tk
    sys.modules["tkinter.scrolledtext"] = scrolledtext
    sys.modules["tkinter.messagebox"] = messagebox
    sys.modules["tkinter.font"] = font_mod
    return tk


install_fake_tkinter()

import bot as bot_module                      # noqa: E402
import run_bot_gui_advanced as gui            # noqa: E402


def main():
    app = gui.GlassmorphicUI()
    print("✅ GUI constructed - all sections built without errors")

    # فقط روبیکا باید باقی مانده باشد (منابع خارجی و ترجمه حذف شده‌اند)
    assert set(app.platform_status.keys()) == {"rubika"}
    assert set(app.platform_indicators.keys()) == {"rubika"}
    assert not hasattr(app, "test_translation"), "تستر ترجمه باید حذف شده باشد"
    assert set(app.rss_status_labels.keys()) == set(gui.NEWS_SOURCES.keys()), \
        "لیست RSS باید فقط منابع داخلی باشد"
    print("✅ Platform status contains ONLY Rubika; RSS list is domestic-only")

    # ویجت‌های تنظیمات روبیکا ساخته شده‌اند
    assert hasattr(app, "rubika_token_var") and hasattr(app, "rubika_channel_var")
    assert hasattr(app, "token_entry") and hasattr(app, "channel_entry")
    print("✅ Rubika settings widgets exist")

    # ذخیره تنظیمات از طریق GUI
    old_file = bot_module.CONFIG_FILE
    old_state = bot_module.STATE_FILE
    try:
        with tempfile.TemporaryDirectory() as tmp:
            bot_module.CONFIG_FILE = os.path.join(tmp, "rubika_config.json")
            bot_module.STATE_FILE = os.path.join(tmp, "bot_state.json")
            app.rubika_token_var.set("my-rubika-token")
            app.rubika_channel_var.set("@news360_24")
            app.save_rubika_settings()
            with open(bot_module.CONFIG_FILE, encoding="utf-8") as f:
                saved = json.load(f)
            assert saved == {"bot_token": "my-rubika-token", "channel_id": "@news360_24"}
            print("✅ SAVE SETTINGS writes rubika_config.json correctly")

            # خالی بودن فیلدها باید هشدار بدهد و چیزی ذخیره نکند
            gui.messagebox.showwarning.reset_mock()
            app.rubika_token_var.set("")
            app.save_rubika_settings()
            assert gui.messagebox.showwarning.called
            print("✅ Empty settings show warning")

            # استارت ربات با تنظیمات GUI (اتصال واقعی ممکن نیست؛ فقط جریان بررسی می‌شود)
            app.rubika_token_var.set("my-rubika-token")
            app.rubika_channel_var.set("@news360_24")
            app.start_bot()
            assert app.is_running and app.bot is not None
            assert app.bot.channel_id == "@news360_24"
            assert app.bot.bot.token == "my-rubika-token"
            print("✅ START passes Rubika token/channel to SmartNewsBot")

            # ترد ربات به دلیل نبود اینترنت واقعی شکست می‌خورد و بسته می‌شود
            deadline = time.time() + 30
            while app.bot_thread.is_alive() and time.time() < deadline:
                time.sleep(0.2)
            assert not app.bot_thread.is_alive(), "bot thread should exit after connection failure"
            assert app.bot.rubika_connected is False
            app.check_connection_status()
            assert app.is_running is False, "UI must reset to stopped after failed connection"
            print("✅ Failed Rubika connection resets UI to OFFLINE (no fake ONLINE)")

            # وضعیت پلتفرم هنگام اجرای متصل
            app.is_running = True
            app.bot.rubika_connected = True
            app.update_platform_status()
            assert app.platform_status["rubika"] is True
            app.is_running = False
            app.update_platform_status()
            assert app.platform_status["rubika"] is False
            print("✅ Platform indicator follows real Rubika connection state")
    finally:
        bot_module.CONFIG_FILE = old_file
        bot_module.STATE_FILE = old_state

    print("\n🎉 GUI SMOKE TEST PASSED — Rubika-only UI is wired correctly")


if __name__ == "__main__":
    main()
