"""
تست ذخیره وضعیت (State) و اجرای ابری (Cloud Runner) بدون نیاز به اینترنت واقعی.
اجرا: python tests/test_state_and_cloud.py
"""
import asyncio
import os
import sys
import json
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bot as bot_module
from bot import SmartNewsBot, RubikaBot
from test_rubika_bot import start_mock_server, VALID_TOKEN, CHANNEL, received


def make_bot(state_file):
    bot_module.STATE_FILE = state_file
    return SmartNewsBot(bot_token=VALID_TOKEN, channel_id=CHANNEL)


async def test_state_persistence(base_url, tmp):
    state_file = os.path.join(tmp, "state", "bot_state.json")

    bot1 = make_bot(state_file)
    bot1.bot.api_base = f"{base_url}/v3"
    bot1.log_callback = lambda msg: None

    news = {
        "title": "خبر آزمایشی برای تست وضعیت پایدار",
        "summary": "خلاصه خبر آزمایشی.",
        "link": "https://example.com/state/1",
        "source": "ایرنا", "category": "عمومی", "emoji": "📰",
    }
    assert await bot1._send_domestic_direct(dict(news))
    await bot1.bot.close()
    assert os.path.exists(state_file), "state file must be written after a post"
    print("✅ state file written after post")

    # نمونه جدید (شبیه ری‌استارت نوبت بعدی در GitHub Actions)
    bot2 = make_bot(state_file)
    bot2.bot.api_base = f"{base_url}/v3"
    bot2.log_callback = lambda msg: None
    assert news["link"] in bot2.sent_links
    assert bot2._is_duplicate(news["title"]), "باید خبر قبلی را تکراری تشخیص دهد"
    assert bot2.daily_posts == bot1.daily_posts
    sent_before = len(received["messages"]) + len(received["files"])
    ok = await bot2._send_domestic_direct(dict(news))
    assert not ok, "خبر تکراری نباید بعد از ری‌استارت دوباره ارسال شود"
    sent_after = len(received["messages"]) + len(received["files"])
    assert sent_before == sent_after
    await bot2.bot.close()
    print("✅ restart does NOT resend old news (dedup state survives)")

    # فایل وضعیت باید JSON معتبر و شامل شمارنده‌ها باشد
    with open(state_file, encoding="utf-8") as f:
        data = json.load(f)
    for key in ("sent_links", "sent_hashes", "daily_posts", "last_reset_date", "updated_at"):
        assert key in data
    print("✅ state file structure OK")

    # فایل خراب نباید ربات را بشکند
    with open(state_file, "w", encoding="utf-8") as f:
        f.write("{corrupted json!")
    bot3 = make_bot(state_file)
    await bot3.bot.close()
    print("✅ corrupted state file handled gracefully")


async def test_cloud_runner(base_url, tmp):
    import run_bot_cloud as cloud

    state_file = os.path.join(tmp, "cloud_state", "bot_state.json")
    bot_module.STATE_FILE = state_file

    class CloudTestBot(SmartNewsBot):
        def __init__(self):
            super().__init__(bot_token=VALID_TOKEN, channel_id=CHANNEL)
            self.bot = RubikaBot(VALID_TOKEN, api_base=f"{base_url}/v3")
            self.log_callback = lambda msg: None

        async def fetch_all_news(self, is_initial=False):
            # یک خبر در مخزن می‌گذاریم تا ربات واقعاً پست کند
            self.pending_news.append({
                "title": "خبر ابری آزمایشی", "summary": "خلاصه",
                "link": f"https://example.com/cloud/{datetime.now().timestamp()}",
                "source": "ایرنا", "category": "عمومی", "emoji": "📰",
            })
            self.last_fetch_time = datetime.now()

    original_cls = cloud.SmartNewsBot
    cloud.SmartNewsBot = CloudTestBot
    old_runtime = os.environ.get("BOT_MAX_RUNTIME_MINUTES")
    os.environ["BOT_MAX_RUNTIME_MINUTES"] = "0.04"  # ~2.4 ثانیه
    try:
        code = await asyncio.wait_for(cloud.main(), timeout=60)
        assert code == 0, f"cloud runner must exit 0 after watchdog stop, got {code}"
        assert os.path.exists(state_file)
        print("✅ cloud runner: watchdog stops bot cleanly, state saved, exit code 0")

        # خطای اتصال باید کد خروج ۲ بدهد (تا ورک‌فلو backoff کند)
        class BadConnBot(CloudTestBot):
            def __init__(self):
                super().__init__()
                self.bot = RubikaBot(VALID_TOKEN, api_base="http://127.0.0.1:9/v3")
        cloud.SmartNewsBot = BadConnBot
        code = await asyncio.wait_for(cloud.main(), timeout=60)
        assert code == 2, f"connection failure must exit 2, got {code}"
        print("✅ cloud runner: connection failure exits with code 2 (workflow backoff)")
    finally:
        cloud.SmartNewsBot = original_cls
        if old_runtime is None:
            os.environ.pop("BOT_MAX_RUNTIME_MINUTES", None)
        else:
            os.environ["BOT_MAX_RUNTIME_MINUTES"] = old_runtime


async def main():
    runner, base_url = await start_mock_server()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            await test_state_persistence(base_url, tmp)
            await test_cloud_runner(base_url, tmp)
    finally:
        await runner.cleanup()
        bot_module.STATE_FILE = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "bot_state.json")
    print("\n🎉 STATE + CLOUD TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
