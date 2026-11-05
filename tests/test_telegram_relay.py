import os
import tempfile
import unittest
from datetime import datetime, timezone
import time
from unittest.mock import patch

import aiohttp
import bot


def page(*posts):
    return ''.join(f'<div class="tgme_widget_message" data-post="akhbarefori/{i}">'
                   f'{body}<time datetime="{datetime.now(timezone.utc).isoformat()}"></time></div>' for i, body in posts)


def text(value):
    return f'<div class="tgme_widget_message_text">{value}</div>'


class Response:
    def __init__(self, body): self.body = body
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    def raise_for_status(self): pass
    async def text(self): return self.body


class FakeSession:
    pages = {}
    calls = []
    def __init__(self, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    def get(self, url, params=None, **kwargs):
        assert url == bot.TELEGRAM_URL
        before = params['before'] if params else None
        self.calls.append(before)
        result = self.pages[before]
        if isinstance(result, Exception): raise result
        return Response(result)


class TelegramTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = patch.object(bot, 'STATE_FILE', os.path.join(self.tmp.name, 'state.json'))
        self.state.start()
        self.b = bot.SmartNewsBot(bot_token='test', channel_id='@rubika')
        FakeSession.calls = []

    async def asyncTearDown(self):
        self.state.stop()
        self.tmp.cleanup()

    async def test_fetch_pagination_restart_and_dedup(self):
        self.b.telegram_cursor = 10
        FakeSession.pages = {
            None: page((14, text('عنوان چهارم<br>متن چهارم<br>@akhbarefori')), (15, '')),
            14: page((10, text('قدیمی')), (11, text('عنوان اول<br>متن اول<br>https://example.com')), (12, text('عنوان دوم<br>متن دوم'))),
        }
        with patch.object(bot.aiohttp, 'ClientSession', FakeSession):
            await self.b.fetch_all_news()
            self.assertEqual(FakeSession.calls, [None, 14])
            self.assertEqual(self.b.telegram_cursor, 15)
            self.assertEqual([n['link'].split('/')[-1] for n in self.b.pending_news], ['11', '12', '14'])
            self.assertEqual(await self.b._format(self.b.pending_news[-1]), 'عنوان چهارم\n\nمتن چهارم.')
            restarted = bot.SmartNewsBot(bot_token='test', channel_id='@rubika')
            self.assertEqual(restarted.pending_news, self.b.pending_news)
            self.assertEqual(restarted.telegram_cursor, 15)
            await restarted.fetch_all_news()
            self.assertEqual(len(restarted.pending_news), 3)

    async def test_initial_fetch_and_failure_keeps_cursor_and_queue(self):
        FakeSession.pages = {None: page((1, text('خبر<br>متن')), (2, ''))}
        with patch.object(bot.aiohttp, 'ClientSession', FakeSession):
            await self.b.fetch_all_news()
            self.assertEqual(self.b.telegram_cursor, 2)
            self.assertEqual(len(self.b.pending_news), 1)
            FakeSession.pages = {None: aiohttp.ClientConnectionError('offline')}
            await self.b.fetch_all_news()
            self.assertEqual(self.b.telegram_cursor, 2)
            self.assertEqual(len(self.b.pending_news), 1)
            self.assertEqual(self.b.rss_health_check['@akhbarefori'], 'offline')

    async def test_failed_rubika_send_keeps_queued_post(self):
        item = self.b._telegram_item(42, 'عنوان\nمتن خبر')
        item['published_at'] = time.time() - 121
        self.b.pending_news = [item]
        self.b._save_state()
        self.b.last_fetch_time = bot.datetime.now()
        self.b.is_running = True

        async def fail_send(**kwargs):
            raise bot.RubikaAPIError('temporary failure')

        async def stop_after_retry(seconds):
            self.assertEqual(seconds, 1)
            self.b.is_running = False

        self.b.bot.send_message = fail_send
        with patch.object(bot.asyncio, 'sleep', stop_after_retry):
            await self.b.publish_loop()
        self.assertEqual(self.b.pending_news, [item])
        restarted = bot.SmartNewsBot(bot_token='test', channel_id='@rubika')
        self.assertEqual(restarted.pending_news, [item])
        self.assertIsNone(restarted.last_post_time)

    async def test_first_start_ignores_old_posts_and_schedules_recent(self):
        FakeSession.pages = {None: (
            '<div class="tgme_widget_message" data-post="akhbarefori/1">'
            '<div class="tgme_widget_message_text">قدیمی</div>'
            '<time datetime="2026-01-01T00:00:00Z"></time></div>'
            '<div class="tgme_widget_message" data-post="akhbarefori/2">'
            '<div class="tgme_widget_message_text">جدید</div>'
            '<time datetime="2026-01-01T00:09:00Z"></time></div>'
            '<div class="tgme_widget_message" data-post="akhbarefori/3">'
            '<div class="tgme_widget_message_text">بدون تاریخ</div></div>')}
        from datetime import datetime, timezone
        now = datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc).timestamp()
        with patch.object(bot.aiohttp, 'ClientSession', FakeSession), patch.object(bot.time, 'time', return_value=now):
            await self.b.fetch_all_news()
            self.assertEqual([n['link'].split('/')[-1] for n in self.b.pending_news], ['2'])
            self.assertEqual(self.b._post_wait_seconds(), 60)
            self.assertEqual(self.b.telegram_cursor, 3)
            # Manually omit timestamp; after startup the safe fallback is discovery time.
            FakeSession.pages = {None: '<div class="tgme_widget_message" data-post="akhbarefori/4"><div class="tgme_widget_message_text">جدید</div></div>', 4: page((3, text("قبلی")))}
            await self.b.fetch_all_news()
            self.assertEqual(self.b.pending_news[-1]['published_at'], now)
            self.assertEqual(self.b._post_wait_seconds(self.b.pending_news[-1]), 120)

    async def test_bad_pagination_does_not_advance_cursor(self):
        self.b.telegram_cursor = 1
        FakeSession.pages = {None: page((10, text('عنوان'))), 10: page((10, text('عنوان')))}
        with patch.object(bot.aiohttp, 'ClientSession', FakeSession):
            await self.b.fetch_all_news()
        self.assertEqual(self.b.telegram_cursor, 1)
        self.assertEqual(self.b.pending_news, [])


if __name__ == '__main__': unittest.main()
