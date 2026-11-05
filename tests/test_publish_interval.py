"""Each Telegram post is relayed two minutes after its own publication."""
import os
import tempfile
import unittest
from unittest.mock import patch

import bot


class PublishingTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_posts_each_use_their_own_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bot, 'STATE_FILE', os.path.join(tmp, 'state.json')):
            b = bot.SmartNewsBot(bot_token='test', channel_id='@channel')
            clock = [1000.0]
            sent = []
            def news(i, published):
                return {'title': f'خبر شماره {i}', 'summary': 'متن خبر', 'link': f'https://example.com/{i}',
                        'source': 'ایرنا', 'category': 'عمومی', 'published_at': published}
            b.pending_news = [news(1, 1000), news(2, 1001)]
            b._save_state()
            b = bot.SmartNewsBot(bot_token='test', channel_id='@channel')
            b.is_running = True
            async def send_message(chat_id, text):
                sent.append((clock[0], text))
                if len(sent) == 2:
                    b.is_running = False
            async def advance(seconds): clock[0] += seconds
            b.bot.send_message = send_message
            with patch.object(bot.time, 'time', side_effect=lambda: clock[0]), patch.object(bot.asyncio, 'sleep', advance):
                await b.publish_loop()
            self.assertEqual([row[0] for row in sent], [1120, 1121])
            self.assertTrue(all('منبع' not in text and '@channel' not in text for _, text in sent))

    async def test_failed_news_does_not_block_another_due_news(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bot, 'STATE_FILE', os.path.join(tmp, 'state.json')):
            b = bot.SmartNewsBot(bot_token='test', channel_id='@channel')
            b.pending_news = [dict(title='عنوان یک', summary='متن', link='one', published_at=1),
                              dict(title='عنوان دو', summary='متن', link='two', published_at=1)]
            b.is_running = True
            seen = []
            async def send(item):
                seen.append(item['link'])
                if item['link'] == 'two':
                    b.is_running = False
                    return True
                return False
            async def advance(seconds): pass
            b._send_domestic_direct = send
            with patch.object(bot.time, 'time', return_value=200), patch.object(bot.asyncio, 'sleep', advance):
                await b.publish_loop()
            self.assertEqual(seen, ['one', 'two'])
            self.assertEqual([item['link'] for item in b.pending_news], ['one'])

    async def test_plain_output_for_all_types(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bot, 'STATE_FILE', os.path.join(tmp, 'state.json')):
            b = bot.SmartNewsBot(bot_token='test', channel_id='@channel')
            item = {'title': 'عنوان example.dev/path', 'summary': 'به گزارش ایرنا، متن خبر. https://example.dev/path',
                    'source': 'ایرنا', 'is_breaking': True, 'emoji': '🚨'}
            self.assertEqual(await b._format(item), 'عنوان\n\nمتن خبر.')


if __name__ == '__main__': unittest.main()

class TimestampTests(unittest.IsolatedAsyncioTestCase):
    async def test_telegram_timestamp_timezone_and_missing_date(self):
        html = '''<div class="tgme_widget_message" data-post="akhbarefori/10">
        <div class="tgme_widget_message_text">خبر</div>
        <time datetime="2026-01-01T15:30:00+03:30"></time></div>
        <div class="tgme_widget_message" data-post="akhbarefori/11">
        <div class="tgme_widget_message_text">خبر</div></div>'''
        from datetime import datetime, timezone
        posts = bot.SmartNewsBot._parse_telegram_page(html)
        self.assertEqual(posts[0][3], datetime(2026, 1, 1, 12, tzinfo=timezone.utc).timestamp())
        self.assertIsNone(posts[1][3])

    async def test_old_bulk_queue_is_not_replayed_but_partial_delivery_resumes(self):
        import json
        with tempfile.TemporaryDirectory() as tmp, patch.object(bot, 'STATE_FILE', os.path.join(tmp, 'state.json')):
            with open(bot.STATE_FILE, 'w', encoding='utf8') as f:
                json.dump({'pending_news': [{'link': 'old', 'title': 'old'},
                                           {'link': 'partial', 'title': 'partial', 'delivery_started': True}],
                           'telegram_cursor': 100}, f)
            b = bot.SmartNewsBot(bot_token='test', channel_id='@channel')
            self.assertEqual([n['link'] for n in b.pending_news], ['partial'])
            self.assertEqual(b.telegram_cursor, 100)
