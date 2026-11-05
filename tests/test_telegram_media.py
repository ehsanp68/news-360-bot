import os
import tempfile
import unittest
from unittest.mock import patch
import bot


class TelegramMediaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = patch.object(bot, 'STATE_FILE', os.path.join(self.tmp.name, 'state.json'))
        self.state.start()
        self.b = bot.SmartNewsBot(bot_token='token', channel_id='@rubika')

    async def asyncTearDown(self):
        self.state.stop()
        self.tmp.cleanup()

    async def test_parse_and_send_correct_album_with_clean_caption(self):
        html = '''<div class="tgme_widget_message" data-post="akhbarefori/50">
            <a class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn.example/real.jpg')"></a>
            <div class="tgme_widget_message_video_player"><video class="tgme_widget_message_video" src="https://cdn.example/real.mp4" poster="https://cdn.example/thumbnail.jpg"></video></div>
            <div class="tgme_widget_message_text">خبر فوری<br>عنوان خبر<br>خبر‌ فوری: متن خبر و خبر فوری دیگر<br>@akhbarefori https://example.com</div>
        </div>'''
        [(ident, text, media, _)] = self.b._parse_telegram_page(html)
        self.assertEqual(media, [{'type': 'photo', 'url': 'https://cdn.example/real.jpg'},
                                 {'type': 'video', 'url': 'https://cdn.example/real.mp4'}])
        item = self.b._telegram_item(ident, text, media)
        self.assertEqual(item['title'], 'عنوان خبر')
        sent = []
        async def photo(chat, url, caption): sent.append(('photo', url, caption))
        async def video(chat, url, caption): sent.append(('video', url, caption))
        self.b.bot.send_photo = photo
        self.b.bot.send_video = video
        self.assertTrue(await self.b._send_domestic_direct(item))
        self.assertEqual([x[1] for x in sent], ['https://cdn.example/real.jpg', 'https://cdn.example/real.mp4'])
        self.assertIn('عنوان خبر', sent[0][2])
        self.assertNotIn('خبر فوری', sent[0][2])
        self.assertNotIn('خبر‌ فوری', sent[0][2])
        # The only URL allowed in a post is the fixed Rubika channel footer.
        self.assertNotIn('http', sent[0][2].replace('https://rubika.ir/rubika', ''))
        self.assertIn('https://rubika.ir/rubika', sent[0][2])
        self.assertTrue(sent[0][2].endswith('🇮🇷'))
        self.assertEqual(sent[1][2], '')

    async def test_partial_failure_resumes_after_restart_without_repeating_media(self):
        item = self.b._telegram_item(77, 'خبر فوری عنوان\nمتن خبر', [
            {'type': 'photo', 'url': 'https://cdn.example/a.jpg'},
            {'type': 'video', 'url': 'https://cdn.example/b.mp4'}])
        self.b.pending_news = [item]
        sent = []
        async def photo(*args, **kwargs): sent.append('photo')
        async def failure(*args, **kwargs): raise bot.RubikaAPIError('offline')
        self.b.bot.send_photo = photo
        self.b.bot.send_video = failure
        self.assertFalse(await self.b._send_domestic_direct(item))
        restarted = bot.SmartNewsBot(bot_token='token', channel_id='@rubika')
        self.assertEqual(restarted.pending_news[0]['media_index'], 1)
        self.assertTrue(restarted.pending_news[0]['delivery_started'])
        self.assertEqual(restarted._post_wait_seconds(), 0)
        async def refresh(news): news['media_needs_refresh'] = False; return True
        async def video(*args, **kwargs): sent.append('video')
        restarted._refresh_telegram_media = refresh
        restarted.bot.send_photo = photo
        restarted.bot.send_video = video
        self.assertTrue(await restarted._send_domestic_direct(restarted.pending_news[0]))
        self.assertEqual(sent, ['photo', 'video'])

    async def test_unavailable_video_never_uses_poster(self):
        html = '''<div class="tgme_widget_message" data-post="akhbarefori/7">
        <div class="tgme_widget_message_video_player"><video poster="https://cdn.example/preview.jpg"></video></div>
        <div class="tgme_widget_message_text">عنوان</div></div>'''
        ident, text, media, _ = self.b._parse_telegram_page(html)[0]
        self.assertEqual(media, [{'type': 'video', 'url': None}])
        item = self.b._telegram_item(ident, text, media)
        async def refresh(news): return False
        self.b._refresh_telegram_media = refresh
        self.assertFalse(await self.b._send_domestic_direct(item))
        self.assertNotIn(item['link'], self.b.sent_links)

    async def test_legacy_queue_refreshes_before_sending(self):
        item = {'title': 'عنوان', 'summary': 'متن', 'link': 'https://t.me/akhbarefori/42', 'category': 'عمومی'}
        sent = []
        async def refresh(news):
            news['media'] = [{'type': 'photo', 'url': 'https://cdn.example/42.jpg'}]
            return True
        async def photo(chat, url, caption): sent.append((url, caption))
        self.b._refresh_telegram_media = refresh
        self.b.bot.send_photo = photo
        self.assertTrue(await self.b._send_domestic_direct(item))
        self.assertEqual(sent[0][0], 'https://cdn.example/42.jpg')

    async def test_long_caption_remainder_and_media_only(self):
        item = self.b._telegram_item(8, 'عنوان\n' + 'الف ' * 400, [{'type': 'photo', 'url': 'https://cdn.example/photo.jpg'}])
        delivered = []
        async def photo(chat, url, caption): delivered.append(caption)
        async def message(chat_id, text): delivered.append(text)
        self.b.bot.send_photo, self.b.bot.send_message = photo, message
        self.assertTrue(await self.b._send_domestic_direct(item))
        self.assertEqual(''.join(delivered), self.b._with_footer(await self.b._format(item)))
        self.assertTrue(delivered[-1].endswith('🇮🇷'))
        media_only = self.b._telegram_item(9, '', [{'type': 'video', 'url': 'https://cdn.example/v.mp4'}])
        self.b.pending_news = [media_only]
        self.b._save_state()
        reloaded = bot.SmartNewsBot(bot_token='token', channel_id='@rubika')
        self.assertEqual(reloaded.pending_news[0]['media'], media_only['media'])

if __name__ == '__main__': unittest.main()
