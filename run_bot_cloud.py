"""
اجرای ربات در محیط ابری (GitHub Actions) - بدون رابط گرافیکی و بدون نیاز به سیستم شخصی.

- ربات را برای مدت مشخص (پیش‌فرض ۳۳۰ دقیقه) اجرا می‌کند و سپس به‌صورت تمیز متوقف می‌شود
  تا ورک‌فلوی GitHub Actions نوبت بعدی را شروع کند (محدودیت هر جاب در گیت‌هاب ۶ ساعت است).
- وضعیت (خبرهای ارسال‌شده) در state/bot_state.json ذخیره می‌شود تا بعد از ری‌استارت
  خبر تکراری ارسال نشود.
- با SIGTERM/SIGINT به‌صورت تمیز خاموش می‌شود (Cancel کردن ورک‌فلو = توقف امن).

کدهای خروج:
  0 = پایان عادی نوبت (ورک‌فلو بلافاصله نوبت بعدی را شروع می‌کند)
  1 = تنظیمات ناقص (توکن/کانال)
  2 = خطای اتصال به روبیکا (ورک‌فلو با تأخیر ۵ دقیقه‌ای دوباره تلاش می‌کند)
"""
import asyncio
import os
import signal
import sys

from bot import SmartNewsBot

# پیش‌فرض: ۵ ساعت و ۳۰ دقیقه (زیر محدودیت ۶ ساعته گیت‌هاب)
DEFAULT_RUNTIME_MINUTES = 330


async def main():
    print('☁️  News360 Rubika Bot - Cloud Runner (GitHub Actions)')
    try:
        bot = SmartNewsBot()
    except ValueError as e:
        print(f'❌ {e}')
        print('راهنما: سکرت‌های RUBIKA_BOT_TOKEN و RUBIKA_CHANNEL_ID را در تنظیمات مخزن گیت‌هاب اضافه کنید')
        return 1

    try:
        max_minutes = float(os.environ.get('BOT_MAX_RUNTIME_MINUTES', DEFAULT_RUNTIME_MINUTES))
    except ValueError:
        max_minutes = DEFAULT_RUNTIME_MINUTES
    if max_minutes <= 0:
        max_minutes = DEFAULT_RUNTIME_MINUTES
    print(f'⏱️ Runtime limit: {max_minutes:.0f} minutes (سپس ری‌استارت خودکار توسط ورک‌فلو)')

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, bot.stop)
        except (NotImplementedError, RuntimeError):
            pass  # ویندوز و برخی محیط‌ها

    async def watchdog():
        await asyncio.sleep(max_minutes * 60)
        bot.log(f'⏰ Runtime limit ({max_minutes:.0f}m) reached - stopping for the next shift')
        bot.stop()

    watchdog_task = asyncio.create_task(watchdog())
    try:
        ran_ok = await bot.run()
    except KeyboardInterrupt:
        bot.stop()
        ran_ok = True
    finally:
        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass

    if ran_ok is False:
        print('❌ اتصال به روبیکا برقرار نشد (کد خروج ۲)')
        return 2
    print('✅ Shift finished cleanly - state saved')
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
