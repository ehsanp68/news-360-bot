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
    assert CHANNEL in text and "ایرنا" in text
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
    assert ok and received["files"][-1]["file_id"]
    print("✅ domestic post with photo → sendFile OK")

    news_video = dict(news, link="https://example.com/news/3",
                      video_url=f"{base_url}/media/clip2.mp4")
    ok = await news_bot._send_domestic_direct(news_video)
    assert ok and news_bot.total_videos_posted == 1
    print("✅ domestic post with video → sendFile OK")

    breaking = dict(news, link="https://example.com/news/4", is_breaking=True)
    ok = await news_bot._send_breaking(breaking)
    assert ok and "خبر فوری" in received["messages"][-1]["text"]
    print("✅ breaking post OK")

    viral = dict(news, link="https://example.com/news/5", is_viral=True)
    ok = await news_bot._send_viral(viral)
    assert ok and "وایرال" in received["messages"][-1]["text"]
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
    # چرخه انتشار نباید اسلات بین‌المللی داشته باشد
    for slot in bot_module.PUBLISH_CYCLE_SLOTS:
        assert slot.get("type") != "international"
    print(f"✅ domestic-only: {len(bot_module.NEWS_SOURCES)} sources, "
          f"{len(bot_module.SOURCE_ROTATION_CYCLE)} rotation steps, "
          f"{len(bot_module.PUBLISH_CYCLE_SLOTS)} cycle slots (no foreign sources)")


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
