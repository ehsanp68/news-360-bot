"""News summaries are short, extractive, and stable across retries."""
import os
import tempfile
import unittest
from unittest.mock import patch

import bot


class NewsSummaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = patch.object(bot, 'STATE_FILE', os.path.join(self.tmp.name, 'state.json'))
        self.state.start()
        self.b = bot.SmartNewsBot(bot_token='test', channel_id='@rubika')

    async def asyncTearDown(self):
        self.state.stop()
        self.tmp.cleanup()

    async def test_short_headline_and_one_sentence(self):
        item = self.b._telegram_item(1, 'زمان انتخابات فدراسیون بسکتبال مشخص شد\n'
                                     'مجمع انتخاباتی فدراسیون بسکتبال اول دی ماه برگزار خواهد شد. '
                                     'زمان و محل ثبت نام بعداً اعلام می‌شود.')
        self.assertEqual(await self.b._format(item), 'زمان انتخابات فدراسیون بسکتبال مشخص شد\n\n'
                         'مجمع انتخاباتی فدراسیون بسکتبال اول دی ماه برگزار خواهد شد.')

    async def test_short_single_sentence_and_no_duplicate(self):
        headline = 'وزارت کار و رفاه از واریز هفتمین مرحله شارژ ۲ میلیون تومانی «کارت امید مادر» خبر داد'
        self.assertEqual(await self.b._format(self.b._telegram_item(2, headline)), headline)
        item = self.b._telegram_item(3, headline + '\n' + headline + '.\nجزئیات بعدی.')
        self.assertEqual(await self.b._format(item), headline + '\n\nجزئیات بعدی.')

    async def test_decimal_urls_and_forbidden_phrase(self):
        item = self.b._telegram_item(4, 'خبر فوری نرخ تورم اعلام شد\n'
            'نرخ تورم 1.5 درصد شد. جمله دوم نباید بیاید. https://example.com\n@akhbarefori')
        result = await self.b._format(item)
        self.assertEqual(result, 'نرخ تورم اعلام شد\n\nنرخ تورم ۱.۵ درصد شد.')
        self.assertNotIn('خبر فوری', result)
        self.assertNotIn('http', result)

    async def test_media_caption_is_summarized(self):
        item = self.b._telegram_item(5, 'عنوان خبر\nجمله نخست. جمله دوم.',
            [{'type': 'photo', 'url': 'https://cdn.example/img.jpg'}])
        sent = []
        async def photo(chat, url, caption): sent.append(caption)
        self.b.bot.send_photo = photo
        self.assertTrue(await self.b._send_domestic_direct(item))
        self.assertEqual(sent, ['عنوان خبر\n\nجمله نخست.\n\nhttps://rubika.ir/rubika\n🇮🇷'])

    async def test_resume_legacy_partial_delivery_uses_original_text(self):
        item = {'title': 'عنوان', 'summary': 'جمله اول. جمله دوم.', 'link': 'https://example.com/6',
                'category': 'عمومی', 'media': [], 'delivery_started': True, 'text_offset': 0}
        captured = []
        async def message(chat_id, text): captured.append(text)
        self.b.bot.send_message = message
        self.assertTrue(await self.b._send_domestic_direct(item))
        self.assertEqual(captured, ['عنوان\n\nجمله اول. جمله دوم.\n\nhttps://rubika.ir/rubika\n🇮🇷'])

    async def test_link_fist_emoji_removed_from_news(self):
        item = self.b._telegram_item(6, 'عنوان خبر\nمتن خبر اول.\nLink ✊')
        result = await self.b._format(item)
        self.assertNotIn('Link', result)
        self.assertNotIn('✊', result)
        item = self.b._telegram_item(7, 'عنوان خبر\nمتن خبر دوم. 👊 Link')
        self.assertNotIn('Link', await self.b._format(item))
        self.assertNotIn('👊', await self.b._format(item))

    async def test_standalone_link_fist_line_dropped(self):
        item = self.b._telegram_item(8, 'عنوان خبر\nمتن خبر.\nLink ✊')
        self.assertNotIn('Link', item['summary'])
        self.assertNotIn('✊', item['summary'])

    async def test_every_post_ends_with_channel_address_and_iran_flag(self):
        item = self.b._telegram_item(9, 'عنوان خبر\nجمله خبر.')
        sent = []
        async def message(chat_id, text): sent.append(text)
        self.b.bot.send_message = message
        self.assertTrue(await self.b._send_domestic_direct(item))
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0].endswith('https://rubika.ir/rubika\n🇮🇷'))
        self.assertTrue(sent[0].startswith('عنوان خبر'))


if __name__ == '__main__': unittest.main()
