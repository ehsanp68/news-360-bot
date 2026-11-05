"""
تست کلاینت روبیکا و جریان ارسال خبر با یک سرور Mock محلی.
اجرا: python tests/test_rubika_bot.py
نیاز به اینترنت واقعی ندارد؛ API روبیکا به صورت محلی شبیه‌سازی می‌شود.
"""
import asyncio
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiohttp import web

import bot as bot_module
from bot import (RubikaBot, RubikaAPIError, SmartNewsBot,
                 load_rubika_config, save_rubika_config,
                 RUBIKA_MAX_TEXT_LENGTH, RUBIKA_MAX_CAPTION_LENGTH)

VALID_TOKEN = "test-token-123"
CHANNEL = "@news360_24"

received = {"messages": [], "files": [], "uploads": []}


# ==================== Mock Rubika API ====================
async def api_handler(request):
    token = request.match_info["token"]
    method = request.match_info["method"]
    payload = await request.json()

    if token != VALID_TOKEN:
        return web.json_response({"status": "InvalidToken", "status_det": "token not found"})

    if method == "getMe":
        return web.json_response({"status": "OK", "data": {
            "bot_id": "b0test", "bot_title": "News360 Bot", "username": "news360_bot"}})

    if method == "getChat":
        return web.json_response({"status": "OK", "data": {"chat": {
            "chat_id": "c0test", "chat_type": "Channel",
            "title": "News 360", "username": CHANNEL.lstrip("@")}}})

    if method == "sendMessage":
        assert payload.get("chat_id") == CHANNEL, "پیام باید فقط به کانال روبیکا ارسال شود"
        assert "parse_mode" not in payload, "روبیکا parse_mode ندارد"
        received["messages"].append(payload)
        return web.json_response({"status": "OK", "data": {"message_id": str(1000 + len(received["messages"]))}})

    if method == "requestSendFile":
        assert payload.get("type") in ("File", "Image", "Voice", "Music", "Gif", "Video")
        base = str(request.url).split("/v3/")[0]
        return web.json_response({"status": "OK", "data": {"upload_url": f"{base}/upload"}})

    if method == "sendFile":
        assert payload.get("chat_id") == CHANNEL
        assert payload.get("file_id")
        received["files"].append(payload)
        return web.json_response({"status": "OK", "data": {"message_id": str(2000 + len(received["files"]))}})

    return web.json_response({"status": "InvalidMethod", "status_det": method})


async def upload_handler(request):
    reader = await request.multipart()
    field = await reader.next()
    assert field.name == "file"
    data = await field.read()
    received["uploads"].append({"filename": field.filename, "size": len(data)})
    return web.json_response({"status": "OK", "data": {"file_id": f"f{len(received['uploads'])}"}})


async def media_handler(request):
    kind = request.match_info["kind"]
    if kind == "missing.jpg":
        return web.Response(status=404)
    return web.Response(body=b"\x89PNG-fake-image-bytes" * 10, content_type="image/png")


async def start_mock_server():
    app = web.Application()
    app.router.add_post("/v3/{token}/{method}", api_handler)
    app.router.add_post("/upload", upload_handler)
    app.router.add_get("/media/{kind}", media_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


# ==================== Tests ====================
async def test_client(base_url):
    client = RubikaBot(VALID_TOKEN, api_base=f"{base_url}/v3")

    me = await client.get_me()
    assert me["username"] == "news360_bot"
    print("✅ getMe OK")

    chat = await client.get_chat(CHANNEL)
    assert chat["chat_type"] == "Channel"
    print("✅ getChat OK")

    await client.send_message(CHANNEL, "سلام روبیکا")
    assert received["messages"][-1]["text"] == "سلام روبیکا"
    print("✅ sendMessage OK")

    long_text = "خ" * (RUBIKA_MAX_TEXT_LENGTH + 500)
    await client.send_message(CHANNEL, long_text)
    assert len(received["messages"][-1]["text"]) == RUBIKA_MAX_TEXT_LENGTH
    print("✅ text truncation OK")

    await client.send_photo(CHANNEL, f"{base_url}/media/photo.jpg", caption="کپشن عکس")
    assert received["files"][-1]["text"] == "کپشن عکس"
    assert received["uploads"][-1]["filename"] == "photo.jpg"
    print("✅ sendPhoto (download → upload → sendFile) OK")

    long_caption = "ک" * (RUBIKA_MAX_CAPTION_LENGTH + 300)
    await client.send_video(CHANNEL, f"{base_url}/media/clip.mp4", caption=long_caption)
    assert len(received["files"][-1]["text"]) == RUBIKA_MAX_CAPTION_LENGTH
    assert received["uploads"][-1]["filename"] == "clip.mp4"
    print("✅ sendVideo + caption truncation OK")

    try:
        await client.send_photo(CHANNEL, f"{base_url}/media/missing.jpg")
        raise AssertionError("باید خطا می‌داد")
    except RubikaAPIError:
        print("✅ media download failure raises RubikaAPIError OK")

    bad = RubikaBot("wrong-token", api_base=f"{base_url}/v3")
    try:
        await bad.get_me()
        raise AssertionError("باید خطا می‌داد")
    except RubikaAPIError:
        print("✅ invalid token raises RubikaAPIError OK")
    finally:
        await bad.close()

    await client.close()


async def test_smart_bot(base_url):
    news_bot = SmartNewsBot(bot_token=VALID_TOKEN, channel_id=CHANNEL)
    news_bot.bot.api_base = f"{base_url}/v3"
    news_bot.log_callback = lambda msg: None  # silent

    news = {
        "title": "افتتاح خط جدید مترو تهران",
        "summary": "خط جدید مترو با حضور مقامات افتتاح شد.",
        "link": "https://example.com/news/1",
        "source": "ایرنا", "category": "اجتماعی", "emoji": "👥",
    }

    ok = await news_bot._send_domestic_direct(dict(news))
    assert ok
    text = received["messages"][-1]["text"]
    assert "<b>" not in text and "<a href" not in text and "&amp;" not in text, "پیام باید متن ساده باشد"
    assert CHANNEL not in text and "ایرنا" not in text and "منبع" not in text
    assert news["link"] not in text and "لینک خبر" not in text, "لینک خبر نباید در پست باشد"
    assert "http" not in text, "هیچ لینکی نباید در پست باشد"
    print("✅ domestic post → Rubika channel (plain text, NO link) OK")

    # duplicate link must not be sent twice
    ok2 = await news_bot._send_domestic_direct(dict(news))
    assert not ok2
    print("✅ duplicate protection OK")

    news_photo = dict(news, link="https://example.com/news/2",
                      image_url=f"{base_url}/media/photo2.jpg")
    ok = await news_bot._send_domestic_direct(news_photo)
    assert ok and received["messages"][-1]["text"] == text
    print("✅ photo ignored; text-only post OK")

    news_video = dict(news, link="https://example.com/news/3",
                      video_url=f"{base_url}/media/clip2.mp4")
    ok = await news_bot._send_domestic_direct(news_video)
    assert ok and received["messages"][-1]["text"] == text
    print("✅ video ignored; text-only post OK")

    breaking = dict(news, link="https://example.com/news/4", is_breaking=True)
    ok = await news_bot._send_breaking(breaking)
    assert ok and received["messages"][-1]["text"] == text
    print("✅ breaking post OK")

    viral = dict(news, link="https://example.com/news/5", is_viral=True)
    ok = await news_bot._send_viral(viral)
    assert ok and received["messages"][-1]["text"] == text
    assert "http" not in received["messages"][-1]["text"], "پست وایرال هم نباید لینک داشته باشد"
    print("✅ viral post (no link) OK")

    # image failure must fall back to text message
    bad_photo = dict(news, link="https://example.com/news/7",
                     image_url=f"{base_url}/media/missing.jpg")
    ok = await news_bot._send_domestic_direct(bad_photo)
    assert ok
    print("✅ photo failure falls back to text OK")

    await news_bot.bot.close()


def test_domestic_only():
    # هیچ منبع خارجی نباید باقی مانده باشد
    assert not hasattr(bot_module, "INTERNATIONAL_SOURCES"), "منابع خارجی باید حذف شده باشند"
    assert not hasattr(bot_module, "TRANSLATION_MAX_RETRIES"), "تنظیمات ترجمه باید حذف شده باشند"
    assert not hasattr(SmartNewsBot, "_send_international_direct")
    assert not hasattr(SmartNewsBot, "_smart_translate")
    # چرخش منبع فقط باید به منابع داخلی اشاره کند
    for step_type, source, _wait in bot_module.SOURCE_ROTATION_CYCLE:
        if step_type == "publish":
            assert source in bot_module.NEWS_SOURCES, f"منبع خارجی در چرخش: {source}"
    print(f"✅ domestic-only: {len(bot_module.NEWS_SOURCES)} sources, "
          f"{len(bot_module.SOURCE_ROTATION_CYCLE)} rotation steps (no foreign sources)")


def test_single_algorithm():
    # Smart Priority باید کاملاً حذف شده باشد؛ فقط Source Rotation بماند
    assert not hasattr(bot_module, "ALGORITHM_SMART_PRIORITY")
    assert not hasattr(bot_module, "PUBLISH_CYCLE_SLOTS")
    assert not hasattr(SmartNewsBot, "publish_loop_smart_priority")
    assert not hasattr(SmartNewsBot, "set_algorithm")
    assert not hasattr(SmartNewsBot, "get_algorithm_name")
    assert not hasattr(SmartNewsBot, "current_algorithm")
    pool = bot_module.BalancedNewsPool()
    assert not hasattr(pool, "get_next_by_cycle")
    assert not hasattr(pool, "get_next_slot")
    assert not hasattr(pool, "cycle_slots")
    assert hasattr(SmartNewsBot, "publish_loop_source_rotation")
    print("✅ single algorithm: Smart Priority removed, Source Rotation is the only publisher")


def test_news_style():
    b = SmartNewsBot.__new__(SmartNewsBot)
    # اعداد فارسی + جداکننده هزارگان + نشانه‌گذاری فارسی + حذف تکرار
    out = b._news_style("قیمت دلار به 50,000 تومان رسید ; بازار ملتهب است? خبر خبر", is_title=False)
    assert "۵۰٬۰۰۰" in out and "؛" in out and "؟" in out and "خبر خبر" not in out
    # نیم‌فاصله استاندارد
    out = b._news_style("می گوید که کتاب ها ارزان می شود")
    assert "می\u200cگوید" in out and "کتاب\u200cها" in out and "می\u200cشود" in out
    # ی/ک عربی → فارسی
    assert b._news_style("علي و كريم", is_title=True) == "علی و کریم"
    # عنوان بدون نقطه پایانی، خلاصه با نقطه پایانی
    assert b._news_style("خبر مهم.", is_title=True) == "خبر مهم"
    assert b._news_style("خبر مهم") == "خبر مهم."
    # اعشار و سه‌نقطه سالم بمانند
    assert "۱.۵" in b._news_style("تورم 1.5 درصد شد")
    assert b._news_style("ادامه دارد...") == "ادامه دارد..."
    # idempotent: اجرای دوباره نباید چیزی را تغییر دهد
    for text, is_title in [("زلزله ٤.٥ ریشتری تهران را لرزاند.", True),
                           ("وزیر گفت:جلسه برگزار شد,و تصمیمات اعلام شد؟!", False)]:
        once = b._news_style(text, is_title=is_title)
        assert b._news_style(once, is_title=is_title) == once, f"not idempotent: {once!r}"
    print("✅ news style: Persian digits/punctuation/half-space/cleanup, idempotent")


async def test_no_links_in_content():
    # هیچ لینکی (حتی داخل متن خلاصه/عنوان RSS) نباید به پست روبیکا برسد
    b = SmartNewsBot.__new__(SmartNewsBot)
    samples = [
        "به گزارش ایرنا، جلسه برگزار شد. https://www.irna.ir/news/85123456",
        "متن کامل خبر در لینک زیر: irna.ir/xjQRST",
        "مشروح خبر: mehrnews.com/x3ABCD",
        "جزئیات بیشتر در www.farsnews.ir/news/123456789",
        "قیمت دلار اعلام شد؛ ادامه مطلب: https://www.khabaronline.ir/tiny/98765",
        "کانال ما: t.me/news360 و سایت example.com/path?a=1",
    ]
    for s in samples:
        out = b._news_style(s).lower()
        for marker in ("http", "www.", ".ir/", ".com", "t.me", "irna.ir", "mehrnews"):
            assert marker not in out, f"لینک باقی مانده: {out!r}"
        assert b._news_style(out) == out
    # عنوان لینک‌دار + قالب‌بندی نهایی پست (متنی و وایرال)
    news = {"title": "افتتاح خط مترو https://irna.ir/xjAB12",
            "summary": "خط جدید افتتاح شد. مشروح خبر: irna.ir/xjAB12",
            "source": "ایرنا", "emoji": "🚇", "link": "https://irna.ir/xjAB12"}
    b.channel_id = "@news360_24"
    text = await b._format(news)
    viral = b._format_viral(dict(news, is_viral=True))
    for t in (text, viral):
        assert "http" not in t and "irna.ir" not in t and "www." not in t
    # متن سالم بدون لینک نباید آسیب ببیند
    assert b._news_style("تورم 1.5 درصد اعلام شد") == "تورم ۱.۵ درصد اعلام شد."
    print("✅ no-links: URLs stripped from titles/summaries/posts (incl. short links)")


def test_breaking_accuracy():
    b = SmartNewsBot.__new__(SmartNewsBot)
    positives = [
        ("حمله موشکی به تهران", ""),
        ("فوری: انفجار در خط لوله گاز پایتخت", ""),
        ("زلزله ۵.۲ ریشتری تهران را لرزاند", ""),
        ("ترور نافرجام یک مقام مسئول", ""),
        ("زلزله شدید خوزستان را لرزاند", ""),
    ]
    negatives = [
        ("تکذیب شایعه حمله به ایران", "منابع آگاه خبر حمله را تکذیب کردند"),
        ("شایعه انفجار در پایتخت کذب است", ""),
        ("جلسه عادی مجلس برگزار شد", "نمایندگان درباره بودجه بحث کردند"),
        ("زلزله ۳ ریشتری در حومه تهران", ""),
        ("برگزاری مانور نظامی در کویر", ""),
        ("قیمت دلار امروز چند است؟", ""),
    ]
    for t, s in positives:
        assert b._is_breaking_news(t, s), f"باید فوری می‌بود: {t}"
    for t, s in negatives:
        assert not b._is_breaking_news(t, s), f"نباید فوری می‌بود: {t}"
    print(f"✅ breaking accuracy: {len(positives)} true positives, {len(negatives)} true negatives")


def test_viral_accuracy():
    from datetime import datetime, timedelta
    t1 = "آتش سوزی گسترده در بازار بزرگ تهران مهار شد"
    t2 = "مهار آتش سوزی بازار بزرگ تهران پس از چند ساعت"
    t3 = "آتش\u200cسوزی بازار تهران مهار شد"
    # همان رویداد در ۳ منبع → سومی وایرال است
    pool = bot_module.BalancedNewsPool()
    assert [pool.check_and_mark_viral(t, s)
            for t, s in [(t1, "ایرنا"), (t2, "مهر"), (t3, "ایسنا")]] == [False, False, True]
    # خبر نامرتبط → وایرال نیست
    assert not pool.check_and_mark_viral("قیمت طلا در بازار امروز کاهش یافت", "فارس")
    # تکرار از همان منبع → وایرال نیست
    p2 = bot_module.BalancedNewsPool()
    p2.check_and_mark_viral(t1, "ایرنا")
    assert not p2.check_and_mark_viral(t2, "ایرنا")
    # خارج از پنجره زمانی → وایرال نیست
    p3 = bot_module.BalancedNewsPool()
    old = datetime.now() - timedelta(hours=bot_module.VIRAL_TIME_WINDOW_HOURS + 4)
    p3.recent_titles_by_source["ایرنا"] = [(t1, p3._viral_tokens(t1), old)]
    p3.recent_titles_by_source["مهر"] = [(t2, p3._viral_tokens(t2), old)]
    assert not p3.check_and_mark_viral(t3, "ایسنا")
    # اعداد متفاوت → رویدادهای متفاوت → وایرال نیست
    p4 = bot_module.BalancedNewsPool()
    p4.check_and_mark_viral("زلزله ۳ ریشتری تهران را لرزاند", "ایرنا")
    p4.check_and_mark_viral("زلزله ۶ ریشتری تهران را لرزاند", "مهر")
    assert not p4.check_and_mark_viral("زلزله ۴ ریشتری تهران را لرزاند", "ایسنا")
    # عدد یکسان + ۳ منبع → وایرال
    p5 = bot_module.BalancedNewsPool()
    p5.check_and_mark_viral("زلزله ۵.۲ ریشتری تهران را لرزاند", "ایرنا")
    p5.check_and_mark_viral("زلزله ۵.۲ ریشتری در تهران", "مهر")
    assert p5.check_and_mark_viral("تهران با زلزله ۵.۲ ریشتری لرزید", "ایسنا")
    print("✅ viral accuracy: multi-source + time window + number guard + same-source guard")


def test_config():
    # save/load roundtrip in a temp dir
    old_file = bot_module.CONFIG_FILE
    old_env = {k: os.environ.pop(k, None) for k in ("RUBIKA_BOT_TOKEN", "RUBIKA_CHANNEL_ID")}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            bot_module.CONFIG_FILE = os.path.join(tmp, "rubika_config.json")
            save_rubika_config("tok-abc", "@my_channel")
            token, channel = load_rubika_config()
            assert token == "tok-abc" and channel == "@my_channel"
            print("✅ config save/load roundtrip OK")

            os.environ["RUBIKA_BOT_TOKEN"] = "env-tok"
            os.environ["RUBIKA_CHANNEL_ID"] = "@env_channel"
            token, channel = load_rubika_config()
            assert token == "env-tok" and channel == "@env_channel"
            print("✅ env vars override config file OK")
    finally:
        bot_module.CONFIG_FILE = old_file
        for k, v in old_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    # missing token/channel must raise a clear error
    try:
        SmartNewsBot(bot_token="", channel_id="")
        if not bot_module.RUBIKA_BOT_TOKEN:
            raise AssertionError("باید خطای تنظیمات می‌داد")
    except ValueError as e:
        assert "روبیکا" in str(e)
        print("✅ missing settings raise Persian ValueError OK")


async def main():
    test_config()
    test_domestic_only()
    test_single_algorithm()
    test_news_style()
    await test_no_links_in_content()
    test_breaking_accuracy()
    test_viral_accuracy()
    runner, base_url = await start_mock_server()
    old_state = bot_module.STATE_FILE
    try:
        with tempfile.TemporaryDirectory() as tmp:
            # وضعیت تست‌ها در پوشه موقت نوشته شود، نه داخل مخزن
            bot_module.STATE_FILE = os.path.join(tmp, "bot_state.json")
            await test_client(base_url)
            await test_smart_bot(base_url)
    finally:
        bot_module.STATE_FILE = old_state
        await runner.cleanup()
    print("\n🎉 ALL TESTS PASSED — Rubika-only pipeline works end-to-end")


if __name__ == "__main__":
    asyncio.run(main())
