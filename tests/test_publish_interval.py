"""Regression tests for the shared publication interval and text-only output."""
import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import bot


class Clock(datetime):
    current = datetime(2026, 1, 1, 12)

    @classmethod
    def now(cls, tz=None):
        return cls.current


class PublishingTests(unittest.IsolatedAsyncioTestCase):
    async def test_priority_and_restart_obey_interval(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bot, 'STATE_FILE', os.path.join(tmp, 'state.json')), patch.object(bot, 'datetime', Clock):
            Clock.current = datetime(2026, 1, 1, 12)
            b = bot.SmartNewsBot(bot_token='test', channel_id='@channel')
            sent = []

            async def send_message(chat_id, text):
                sent.append((Clock.now(), text))
                if len(sent) == 3:
                    b.is_running = False

            b.bot.send_message = send_message
            def news(i):
                return {'title': f'عنوان خبر شماره {i}', 'summary': 'متن خبر',
                        'source': 'ایرنا', 'link': f'https://example.com/{i}',
                        'category': 'عمومی'}

            # A normal successful send before a restart must delay priority news too.
            self.assertTrue(await b._send_domestic_direct(news(1)))
            restarted = bot.SmartNewsBot(bot_token='test', channel_id='@channel')
            self.assertEqual(restarted._post_wait_seconds(), 300)
            b = restarted
            b.bot.send_message = send_message
            b.news_pool.add_breaking(news(2))
            b.news_pool.add_viral(news(3))
            b.is_running = True

            async def advance(seconds):
                Clock.current += timedelta(seconds=seconds)

            with patch.object(bot.asyncio, 'sleep', advance):
                await b.publish_loop_source_rotation()
            self.assertEqual(len(sent), 3)
            self.assertGreaterEqual((sent[1][0] - sent[0][0]).total_seconds(), 300)
            self.assertGreaterEqual((sent[2][0] - sent[1][0]).total_seconds(), 300)
            self.assertTrue(all('منبع' not in text and '@channel' not in text for _, text in sent))

    async def test_plain_output_for_all_types(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bot, 'STATE_FILE', os.path.join(tmp, 'state.json')):
            b = bot.SmartNewsBot(bot_token='test', channel_id='@channel')
            item = {'title': 'عنوان example.dev/path', 'summary': 'به گزارش ایرنا، متن خبر. https://example.dev/path',
                    'source': 'ایرنا', 'is_breaking': True, 'emoji': '🚨'}
            regular = await b._format(item)
            self.assertEqual(regular, b._format_viral(item))
            self.assertEqual(regular, 'عنوان\n\nمتن خبر.')


if __name__ == '__main__':
    unittest.main()
