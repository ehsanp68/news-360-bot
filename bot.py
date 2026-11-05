"""Relay public Telegram channel posts to a Rubika channel."""
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import re
from difflib import SequenceMatcher
import hashlib
import aiohttp
import json
import time
import os

# ==================== تنظیمات اصلی (فقط روبیکا) ====================
# این ربات اخبار را فقط و فقط در کانال روبیکا منتشر می‌کند.
# هیچ شبکه اجتماعی دیگری (تلگرام، بله و ...) پشتیبانی نمی‌شود.
#
# روش‌های تنظیم توکن و کانال (به ترتیب اولویت):
#   1) متغیرهای محیطی RUBIKA_BOT_TOKEN و RUBIKA_CHANNEL_ID
#   2) فایل rubika_config.json (از طریق بخش RUBIKA SETTINGS در رابط گرافیکی)
#   3) مقداردهی مستقیم همین‌جا:
DEFAULT_RUBIKA_BOT_TOKEN = ""   # توکن ربات روبیکا (ساخت ربات از طریق BotFather روبیکا)
DEFAULT_RUBIKA_CHANNEL_ID = ""  # آیدی کانال روبیکا، مثل: @news360_24

RUBIKA_API_BASE = "https://botapi.rubika.ir/v3"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rubika_config.json")


def load_rubika_config():
    """بارگذاری تنظیمات روبیکا: متغیر محیطی → فایل تنظیمات → مقدار پیش‌فرض"""
    cfg = {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        pass
    token = (os.environ.get('RUBIKA_BOT_TOKEN') or cfg.get('bot_token')
             or DEFAULT_RUBIKA_BOT_TOKEN or '').strip()
    channel = (os.environ.get('RUBIKA_CHANNEL_ID') or cfg.get('channel_id')
               or DEFAULT_RUBIKA_CHANNEL_ID or '').strip()
    return token, channel


def save_rubika_config(bot_token, channel_id):
    """ذخیره تنظیمات روبیکا (توسط رابط گرافیکی استفاده می‌شود)"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump({'bot_token': bot_token.strip(), 'channel_id': channel_id.strip()},
                  f, ensure_ascii=False, indent=2)


RUBIKA_BOT_TOKEN, RUBIKA_CHANNEL_ID = load_rubika_config()

# ==================== محدودیت‌های ارسال روبیکا ====================
RUBIKA_MAX_TEXT_LENGTH = 4000
RUBIKA_MAX_CAPTION_LENGTH = 1000
RUBIKA_MAX_MEDIA_BYTES = 20 * 1024 * 1024

# ==================== وضعیت پایدار (برای اجرای ابری در GitHub Actions) ====================
# بین نوبت‌های اجرا، لیست خبرهای ارسال‌شده ذخیره می‌شود تا خبر تکراری ارسال نشود.
STATE_FILE = os.environ.get('BOT_STATE_FILE') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'state', 'bot_state.json')
STATE_MAX_LINKS = 5000

# Telegram's public channel preview, no Telegram credentials required.
TELEGRAM_CHANNEL = 'akhbarefori'
TELEGRAM_URL = f'https://t.me/s/{TELEGRAM_CHANNEL}'
NEWS_SOURCES = {'@akhbarefori': TELEGRAM_URL}  # for the GUI status indicator
FETCH_INTERVAL = 10  # seconds between Telegram checks
POST_DELAY = 2 * 60  # seconds after the Telegram post
RETRY_DELAY = 30
TELEGRAM_MAX_PAGES = 100

# ==================== تنظیمات محتوا ====================
INCLUDE_IMAGES = True
INCLUDE_VIDEOS = True
SUMMARY_WORDS = 90

# ==================== ✍️ سبک خبری (اعمال روی همه خبرها) ====================
NEWS_STYLE_ENABLED = True

# ==================== 🏁 فوتر ثابت پایین همه پست‌ها ====================
IRAN_FLAG_EMOJI = '🇮🇷'          # پرچم ایران - همیشه پایین پست
FIST_EMOJIS = '✊👊🤜🤛💪'        # ایموجی مشت گره‌کرده (همراه «Link» در انتهای برخی خبرها)
_DIGITS_TO_FA = str.maketrans('0123456789' + '٠١٢٣٤٥٦٧٨٩', '۰۱۲۳۴۵۶۷۸۹' * 2)
_DIGITS_TO_EN = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '0123456789' * 2)

# ==================== 🔥 تنظیمات وایرال (تشخیص دقیق) ====================
# وایرال = بازتاب یک رویداد در حداقل ۲ منبع دیگر، در پنجره زمانی مشخص،
# با شباهت معنایی بالا (نرمال‌سازی ی/ک، نیم‌فاصله، حذف کلمات اضافی)
VIRAL_SIMILARITY_THRESHOLD = 0.65   # آستانه شباهت (ترکیب توالی + اشتراک کلمات)
VIRAL_SOURCES_MIN = 2               # حداقل تعداد منابع دیگر
VIRAL_TIME_WINDOW_HOURS = 6         # فقط خبرهای ۶ ساعت اخیر مقایسه می‌شوند
VIRAL_MAX_TITLES_PER_SOURCE = 80    # سقف عنوان‌های نگهداری‌شده per منبع
VIRAL_MIN_SHARED_TOKENS = 3         # اشتراک ≥۳ کلمه کلیدی → تقویت شباهت
VIRAL_SHARED_TOKEN_BONUS = 0.1
VIRAL_KEYWORDS_FA = [
    'فوری', 'واکنش', 'جنجال', 'بحران', 'شوکه',
    'تکان‌دهنده', 'اعتراض', 'آشوب', 'شورش', 'استعفا', 'برکناری',
    'ترور', 'اعدام', 'درگیری', 'محاکمه', 'فساد',
]

# ==================== تنظیمات مخزن ====================
DAILY_NEWS_LIMIT = 500
MAX_POOL_SIZE = 1500
AUTO_CLEANUP_THRESHOLD = 250
OLD_NEWS_HOURS = 6

# ==================== تشخیص تکراری ====================
SIMILARITY_THRESHOLD = 0.65
MIN_TITLE_LENGTH = 10
COMMON_WORDS_TO_IGNORE = [
    'از', 'به', 'در', 'با', 'را', 'که', 'و', 'این', 'آن',
    'است', 'بود', 'شد', 'می', 'خواهد', 'کرد', 'گفت',
    'the', 'a', 'an', 'is', 'are', 'was', 'in', 'of', 'to'
]

# ==================== فیلتر استان‌ها ====================
EXCLUDED_PROVINCES = [
    'آذربایجان شرقی', 'آذربایجان غربی', 'اردبیل', 'اصفهان', 'ایلام',
    'بوشهر', 'چهارمحال و بختیاری', 'خراسان جنوبی', 'خراسان رضوی',
    'خراسان شمالی', 'خوزستان', 'زنجان', 'سمنان', 'سیستان و بلوچستان',
    'فارس', 'قزوین', 'قم', 'کردستان', 'کرمان', 'کرمانشاه',
    'کهگیلویه و بویراحمد', 'گلستان', 'گیلان', 'لرستان', 'مازندران',
    'مرکزی', 'هرمزگان', 'همدان', 'یزد',
    'تبریز', 'مشهد', 'شیراز', 'اهواز', 'رشت', 'ارومیه', 'زاهدان',
    'سنندج', 'خرم آباد', 'سمنان', 'یاسوج', 'گرگان', 'ساری', 'اراک',
    'بیرجند', 'بجنورد', 'بندرعباس',
]

ALLOWED_REGIONS = [
    'تهران', 'البرز', 'کرج', 'شهریار', 'ری', 'اسلامشهر',
    'ورامین', 'پردیس', 'دماوند', 'فردیس', 'هشتگرد', 'نظرآباد',
    'ملارد', 'رباط کریم', 'پاکدشت', 'شهر جدید پرند', 'قرچک',
    'محمدشهر', 'کمالشهر', 'گلستان', 'اندیشه'
]

# ==================== 🚨 تشخیص خبر فوری (امتیازدهی دقیق) ====================
# منطق: عبارت‌های قطعی → فوری فوری؛ در غیر این صورت امتیاز وزنی:
#   کلیدواژه قوی در عنوان = ۳ | در خلاصه = ۲
#   کلیدواژه پشتیبان در عنوان = ۲ | در خلاصه = ۱
#   امتیاز ≥ آستانه → فوری | وجود عبارت تکذیب در عنوان → هرگز فوری نیست
BREAKING_INSTANT_PHRASES = [
    'حمله به ایران', 'حمله آمریکا به ایران', 'حمله اسرائیل به ایران',
    'بمباران ایران', 'حمله به تهران', 'موشک‌باران', 'موشک باران',
    'جنگ با ایران', 'ایران مورد حمله', 'حمله نظامی به ایران',
    'حمله موشکی', 'حمله پهپادی', 'اعلام جنگ', 'کودتا', 'ترور',
    'حکومت نظامی', 'زلزله شدید', 'زلزله مهیب', 'سقوط هواپیما',
    'انفجار مهیب', 'حمله تروریستی', 'گروگان‌گیری گسترده',
]
BREAKING_STRONG_KEYWORDS = [
    'بمباران', 'حمله هوایی', 'حمله سایبری گسترده', 'انفجار', 'زلزله',
    'سیل گسترده', 'تیراندازی', 'سقوط', 'آتش‌سوزی گسترده',
    'قطع سراسری', 'تخلیه اضطراری',
]
BREAKING_SUPPORT_KEYWORDS = [
    'فوری', 'عاجل', 'همین حالا', 'اضطراری', 'بحران',
    'هشدار قرمز', 'کشته', 'مجروح', 'زخمی',
    'وضعیت قرمز', 'تعطیلی سراسری',
]
BREAKING_NEGATION_KEYWORDS = [
    'تکذیب', 'شایعه', 'کذب', 'صحت ندارد', 'جعلی', 'رد شد', 'انکار', 'نادرست',
]
BREAKING_SCORE_THRESHOLD = 4
BREAKING_EARTHQUAKE_MIN_MAGNITUDE = 5.0   # زلزله ≥۵ ریشتر → فوری

# ==================== دسته‌بندی ====================
NEWS_CATEGORIES = {
    'سیاسی': {'emoji': '🏛', 'priority': 1, 'keywords': ['دولت', 'مجلس', 'سیاست', 'وزیر', 'رئیس جمهور', 'نماینده', 'کابینه', 'انتخابات', 'پارلمان', 'دیپلماسی', 'سفیر', 'وزارت', 'حکومت', 'رهبر', 'شورای امنیت', 'سازمان ملل']},
    'اقتصادی': {'emoji': '💰', 'priority': 2, 'keywords': ['اقتصاد', 'بورس', 'ارز', 'دلار', 'طلا', 'بانک', 'تجارت', 'مالیات', 'قیمت', 'تورم', 'رشد اقتصادی', 'بودجه', 'سرمایه گذاری', 'صادرات', 'واردات', 'نفت', 'گاز', 'پتروشیمی', 'خصوصی سازی']},
    'بین‌الملل': {'emoji': '🌍', 'priority': 2, 'keywords': ['بین الملل', 'جهان', 'آمریکا', 'اروپا', 'چین', 'روسیه', 'غزه', 'اسرائیل', 'ناتو', 'تحریم', 'معاهده', 'اتحادیه اروپا', 'خاورمیانه']},
    'حوادث': {'emoji': '🚨', 'priority': 2, 'keywords': ['حادثه', 'آتش سوزی', 'زلزله', 'سیل', 'تصادف', 'انفجار', 'دستگیری', 'اورژانس', 'امداد', 'کشته', 'مجروح', 'نجات']},
    'ورزشی': {'emoji': '⚽', 'priority': 3, 'keywords': ['فوتبال', 'ورزش', 'لیگ', 'تیم', 'بازیکن', 'مربی', 'المپیک', 'جام', 'قهرمان', 'مسابقه', 'گل', 'پیروزی', 'شکست', 'فینال']},
    'بهداشت': {'emoji': '🏥', 'priority': 3, 'keywords': ['بهداشت', 'درمان', 'پزشکی', 'دارو', 'بیمارستان', 'واکسن', 'بیماری', 'سلامت', 'ویروس', 'اپیدمی', 'وزارت بهداشت', 'پزشک', 'درمانگاه']},
    'فناوری': {'emoji': '💻', 'priority': 4, 'keywords': ['فناوری', 'تکنولوژی', 'دیجیتال', 'هوش مصنوعی', 'موبایل', 'اینترنت', 'سایبر', 'نرم افزار', 'استارتاپ', 'ماهواره']},
    'علمی': {'emoji': '🔬', 'priority': 4, 'keywords': ['علم', 'علمی', 'تحقیق', 'پژوهش', 'کشف', 'فضا', 'نجوم', 'دانشمند', 'اختراع', 'نوبل']},
    'اجتماعی': {'emoji': '👥', 'priority': 4, 'keywords': ['اجتماعی', 'مردم', 'جامعه', 'خانواده', 'آموزش', 'مدرسه', 'دانشگاه', 'شهرداری', 'فقر', 'بیکاری', 'مهاجرت']},
    'فرهنگی': {'emoji': '🎭', 'priority': 5, 'keywords': ['فرهنگ', 'هنر', 'سینما', 'تئاتر', 'موسیقی', 'کتاب', 'جشنواره', 'نمایشگاه', 'فیلم']},
    'محیط زیست': {'emoji': '🌱', 'priority': 5, 'keywords': ['محیط زیست', 'آب و هوا', 'آلودگی', 'طبیعت', 'جنگل', 'خشکسالی', 'گرمایش زمین']},
}

DEFAULT_CATEGORY = {'name': 'عمومی', 'emoji': '📰', 'priority': 6}


# ==================== ✅ نگاشت نام منابع به کلید‌های واقعی ====================
# این mapping برای الگوریتم 2 استفاده می‌شود
SOURCE_NAME_MAPPING = {
    'ایرنا': 'ایرنا',
    'ایسنا': 'ایسنا',
    'مهر': 'مهر',
    'فارس': 'فارس',
    'خبرآنلاین': 'خبرآنلاین',
    'خبرگزاری جوان': 'خبرگزاری جوان',
}


# ==================== کلاینت API روبیکا ====================
class RubikaAPIError(Exception):
    """خطای API روبیکا"""


class RubikaBot:
    """کلاینت سبک و async برای API رسمی ربات روبیکا (Bot API v3)

    آدرس: https://botapi.rubika.ir/v3/{token}/{method}
    فقط متدهای موردنیاز این ربات پیاده‌سازی شده‌اند:
    getMe, getChat, sendMessage, requestSendFile, sendFile

    نکته: برخلاف تلگرام، API روبیکا لینک مستقیم رسانه قبول نمی‌کند؛
    رسانه ابتدا دانلود، سپس آپلود و در نهایت با sendFile ارسال می‌شود.
    """

    def __init__(self, token, api_base=RUBIKA_API_BASE):
        self.token = token
        self.api_base = api_base.rstrip('/')
        self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def _call(self, method, payload=None):
        url = f'{self.api_base}/{self.token}/{method}'
        session = await self._get_session()
        async with session.post(url, json=payload or {}) as resp:
            try:
                body = await resp.json(content_type=None)
            except Exception:
                body = {}
            if resp.status != 200 or body.get('status') != 'OK':
                detail = body.get('status_det') or body.get('status') or 'unknown error'
                raise RubikaAPIError(f'{method}: HTTP {resp.status} | {detail}')
            return body.get('data', {}) or {}

    async def get_me(self):
        """اطلاعات ربات - برای تست اتصال"""
        return await self._call('getMe')

    async def get_chat(self, chat_id):
        """اطلاعات کانال/گفتگو - برای بررسی دسترسی ربات به کانال"""
        data = await self._call('getChat', {'chat_id': chat_id})
        return data.get('chat', {}) or {}

    async def send_message(self, chat_id, text):
        """ارسال پیام متنی به کانال روبیکا"""
        text = (text or '').strip()
        if not text:
            raise RubikaAPIError('sendMessage: متن خالی است')
        if len(text) > RUBIKA_MAX_TEXT_LENGTH:
            text = text[:RUBIKA_MAX_TEXT_LENGTH - 1] + '…'
        return await self._call('sendMessage', {'chat_id': chat_id, 'text': text})

    async def _download_media(self, url):
        session = await self._get_session()
        async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
            if resp.status != 200:
                raise RubikaAPIError(f'دانلود رسانه ناموفق: HTTP {resp.status}')
            if resp.content_length and resp.content_length > RUBIKA_MAX_MEDIA_BYTES:
                raise RubikaAPIError('حجم رسانه بیش از حد مجاز است')
            data = bytearray()
            async for chunk in resp.content.iter_chunked(64 * 1024):
                data.extend(chunk)
                if len(data) > RUBIKA_MAX_MEDIA_BYTES:
                    raise RubikaAPIError('حجم رسانه بیش از حد مجاز است')
            if not data:
                raise RubikaAPIError('دانلود رسانه ناموفق: فایل خالی')
            return bytes(data)

    @staticmethod
    def _guess_filename(url, default_name):
        try:
            name = url.split('?')[0].rstrip('/').split('/')[-1]
            if name and '.' in name:
                return name
        except Exception:
            pass
        return default_name

    async def _upload_media(self, file_bytes, file_name, media_type):
        # مرحله 1: دریافت آدرس آپلود از روبیکا
        data = await self._call('requestSendFile', {'type': media_type})
        upload_url = data.get('upload_url')
        if not upload_url:
            raise RubikaAPIError('requestSendFile: آدرس آپلود دریافت نشد')
        # مرحله 2: آپلود فایل (multipart)
        session = await self._get_session()
        form = aiohttp.FormData()
        form.add_field('file', file_bytes, filename=file_name,
                       content_type='application/octet-stream')
        async with session.post(upload_url, data=form) as resp:
            try:
                body = await resp.json(content_type=None)
            except Exception:
                body = {}
            file_id = (body.get('data') or {}).get('file_id')
            if resp.status != 200 or not file_id:
                raise RubikaAPIError(f'آپلود رسانه ناموفق: HTTP {resp.status}')
        return file_id

    async def _send_media(self, chat_id, media_url, caption, media_type, default_name):
        """دانلود → آپلود → ارسال رسانه به کانال روبیکا"""
        file_bytes = await self._download_media(media_url)
        file_name = self._guess_filename(media_url, default_name)
        file_id = await self._upload_media(file_bytes, file_name, media_type)
        caption = (caption or '').strip()
        if len(caption) > RUBIKA_MAX_CAPTION_LENGTH:
            caption = caption[:RUBIKA_MAX_CAPTION_LENGTH - 1] + '…'
        return await self._call('sendFile', {
            'chat_id': chat_id, 'file_id': file_id, 'text': caption
        })

    async def send_photo(self, chat_id, photo, caption=None):
        """ارسال عکس (از لینک) با کپشن به کانال روبیکا"""
        return await self._send_media(chat_id, photo, caption, 'Image', 'news.jpg')

    async def send_video(self, chat_id, video, caption=None):
        """ارسال ویدیو (از لینک) با کپشن به کانال روبیکا"""
        return await self._send_media(chat_id, video, caption, 'Video', 'news.mp4')


# ==================== مخزن خبر ====================
class BalancedNewsPool:
    def __init__(self):
        self.domestic_news = {cat: [] for cat in NEWS_CATEGORIES}
        self.domestic_news['عمومی'] = []
        self.domestic_post_count = {cat: 0 for cat in NEWS_CATEGORIES}
        self.domestic_post_count['عمومی'] = 0
        self.breaking_queue = []
        self.viral_queue = []

        self.last_domestic_source = None
        self.recent_titles_by_source = {}
        self.max_pool_size = MAX_POOL_SIZE
        self.auto_cleanup_threshold = AUTO_CLEANUP_THRESHOLD
        self.last_cleanup_time = datetime.now()
        self.total_cleaned = 0
        self.log_callback = None

    def set_log_callback(self, callback):
        self.log_callback = callback

    def _log(self, msg):
        print(msg)
        if self.log_callback:
            try:
                self.log_callback(msg)
            except:
                pass

    def _viral_tokens(self, title):
        """نرمال‌سازی عنوان برای مقایسه وایرال (ی/ک عربی، نیم‌فاصله، کلمات اضافی)"""
        text = (title or '').lower().replace('ي', 'ی').replace('ك', 'ک')
        text = text.replace('\u200c', ' ')
        text = re.sub(r'[^\w\s]', ' ', text)
        return [w for w in text.split()
                if (len(w) > 1 or w.isdigit()) and w not in COMMON_WORDS_TO_IGNORE]

    def _viral_similarity(self, tokens_a, tokens_b):
        """شباهت دقیق: ترکیب SequenceMatcher و Jaccard + گارد اعداد متفاوت"""
        if not tokens_a or not tokens_b:
            return 0.0
        set_a, set_b = set(tokens_a), set(tokens_b)
        shared = set_a & set_b
        # گارد اعداد: اگر هر دو عنوان عدد دارند ولی هیچ عدد مشترکی ندارند،
        # رویدادها متفاوت‌اند (مثلاً زلزله ۳ ریشتری vs ۶ ریشتری)
        nums_a = {t for t in set_a if any(ch.isdigit() for ch in t)}
        nums_b = {t for t in set_b if any(ch.isdigit() for ch in t)}
        if nums_a and nums_b and not (nums_a & nums_b):
            return 0.0
        seq = SequenceMatcher(None, ' '.join(tokens_a), ' '.join(tokens_b)).ratio()
        jaccard = len(shared) / len(set_a | set_b)
        sim = (seq + jaccard) / 2
        if len(shared) >= VIRAL_MIN_SHARED_TOKENS:
            sim += VIRAL_SHARED_TOKEN_BONUS
        return min(sim, 1.0)

    def check_and_mark_viral(self, title, source):
        """🔥 وایرال = بازتاب همان رویداد در ≥۲ منبع دیگر در پنجره زمانی"""
        now = datetime.now()
        cutoff = now - timedelta(hours=VIRAL_TIME_WINDOW_HOURS)
        tokens = self._viral_tokens(title)
        if source not in self.recent_titles_by_source:
            self.recent_titles_by_source[source] = []
        # فقط عنوان‌های داخل پنجره زمانی نگه داشته می‌شوند
        entries = [e for e in self.recent_titles_by_source[source] if e[2] > cutoff]
        matched_sources = 0
        for other_source, other_entries in self.recent_titles_by_source.items():
            if other_source == source:
                continue
            for (_t, other_tokens, ts) in other_entries:
                if ts <= cutoff:
                    continue
                if self._viral_similarity(tokens, other_tokens) >= VIRAL_SIMILARITY_THRESHOLD:
                    matched_sources += 1
                    break
        # ثبت عنوان (بدون تکرار عنوان یکسان از همان منبع)
        if not any(e[0] == title for e in entries):
            entries.append((title, tokens, now))
        self.recent_titles_by_source[source] = entries[-VIRAL_MAX_TITLES_PER_SOURCE:]
        return matched_sources >= VIRAL_SOURCES_MIN

    def smart_cleanup(self, force=False):
        current_size = self.size()
        if not force and current_size < self.auto_cleanup_threshold:
            return
        self._log(f"🧹 Smart cleanup triggered! Pool size: {current_size}")
        size_before = current_size
        cutoff_time = datetime.now() - timedelta(hours=OLD_NEWS_HOURS)
        for category in list(self.domestic_news.keys()):
            self.domestic_news[category] = [
                item for item in self.domestic_news[category]
                if item.get('fetched_at', datetime.now()) > cutoff_time
            ]
        self.viral_queue = [
            item for item in self.viral_queue
            if item.get('fetched_at', datetime.now()) > cutoff_time
        ]
        if self.size() > self.max_pool_size:
            low_priority = ['عمومی', 'فرهنگی', 'محیط زیست', 'اجتماعی']
            for cat in low_priority:
                if cat in self.domestic_news and len(self.domestic_news[cat]) > 5:
                    keep = max(5, int(len(self.domestic_news[cat]) * 0.3))
                    self.domestic_news[cat] = self.domestic_news[cat][:keep]
        if len(self.viral_queue) > 50:
            self.viral_queue = self.viral_queue[:50]
        size_final = self.size()
        self.total_cleaned += (size_before - size_final)
        self.last_cleanup_time = datetime.now()

    def add_breaking(self, item):
        item['is_breaking'] = True
        self.breaking_queue.append(item)

    def has_breaking(self):
        return bool(self.breaking_queue)

    def get_next_breaking(self):
        return self.breaking_queue.pop(0) if self.breaking_queue else None

    def breaking_size(self):
        return len(self.breaking_queue)

    def add_viral(self, item):
        item['is_viral'] = True
        score = 50
        cat = item.get('category', 'عمومی')
        if cat in ['سیاسی', 'بین‌الملل']:
            score += 30
        if cat in ['اقتصادی', 'حوادث']:
            score += 15
        title_l = item.get('title', '').lower()
        if any(kw in title_l for kw in VIRAL_KEYWORDS_FA):
            score += 10
        item['viral_score'] = score
        self.viral_queue.append(item)
        self.viral_queue.sort(key=lambda x: x.get('viral_score', 0), reverse=True)

    def has_viral(self):
        return bool(self.viral_queue)

    def get_next_viral(self):
        return self.viral_queue.pop(0) if self.viral_queue else None

    def viral_size(self):
        return len(self.viral_queue)

    def add_domestic(self, item):
        self.smart_cleanup()
        cat = item.get('category', 'عمومی')
        if cat not in self.domestic_news:
            self.domestic_news[cat] = []
        self.domestic_news[cat].append(item)

    def domestic_size(self):
        return sum(len(v) for v in self.domestic_news.values())

    def size(self):
        return self.domestic_size() + self.breaking_size() + self.viral_size()

    def get_stats(self):
        stats = {cat: len(items) for cat, items in self.domestic_news.items()}
        stats['🚨 Breaking'] = self.breaking_size()
        stats['🔥 Viral'] = self.viral_size()
        return stats


# ==================== ربات اصلی ====================
class SmartNewsBot:
    def __init__(self, log_callback=None, bot_token=None, channel_id=None):
        token = (bot_token or RUBIKA_BOT_TOKEN or '').strip()
        channel = (channel_id or RUBIKA_CHANNEL_ID or '').strip()
        if not token:
            raise ValueError("توکن ربات روبیکا تنظیم نشده است! (بخش RUBIKA SETTINGS در رابط گرافیکی)")
        if not channel:
            raise ValueError("آیدی کانال روبیکا تنظیم نشده است! (بخش RUBIKA SETTINGS در رابط گرافیکی)")
        self.channel_id = channel
        self.bot = RubikaBot(token=token)
        self.rubika_connected = False
        self.sent_links = set()
        self.sent_titles = []
        self.sent_hashes = set()

        self.daily_posts = 0
        self.hourly_posts = 0
        self.hourly_reset_time = datetime.now()
        self.last_reset_date = datetime.now().date()
        self.total_fetched = 0
        self.total_duplicates = 0
        self.total_videos_posted = 0
        self.total_filtered_provinces = 0
        self.total_breaking_posted = 0
        self.source_stats = {}
        self.rss_health_check = {}
        self.cycle_count = 0
        self.next_fetch_time = None
        self.is_running = False
        self.log_callback = log_callback
        self.fetch_interval = FETCH_INTERVAL
        self.last_fetch_time = None
        self.last_post_time = None


        self.pending_news = []
        self.telegram_cursor = None
        self._retry_after = {}

        # ✅ بارگذاری وضعیت قبلی (برای جلوگیری از ارسال تکراری بعد از ری‌استارت)
        self._load_state()

    def log(self, msg):
        print(msg)
        if self.log_callback:
            try:
                self.log_callback(msg)
            except:
                pass

    def _should_filter_province(self, title, summary=''):
        text = (title + ' ' + summary).lower()
        for region in ALLOWED_REGIONS:
            if region.lower() in text:
                return False
        for province in EXCLUDED_PROVINCES:
            if province.lower() in text:
                self.total_filtered_provinces += 1
                return True
        return False

    def _normalize_for_match(self, text):
        """نرمال‌سازی متن برای تطبیق کلیدواژه (ی/ک عربی + نیم‌فاصله)"""
        text = (text or '').lower().replace('ي', 'ی').replace('ك', 'ک')
        text = text.replace('\u200c', ' ')
        return re.sub(r'\s+', ' ', text).strip()

    def _breaking_score(self, title, summary=''):
        """🚨 امتیاز فوریت: عبارت قطعی → ۱۰ | زلزله ≥۵ ریشتر → ۱۰۰ | وگرنه امتیاز وزنی"""
        t = self._normalize_for_match(title)
        s = self._normalize_for_match(summary)
        # گارد تکذیب: خبر تکذیب‌شده/شایعه هرگز فوری نیست
        if any(neg in t for neg in BREAKING_NEGATION_KEYWORDS):
            return 0
        # عبارت‌های قطعی در عنوان → فوری فوری
        for phrase in BREAKING_INSTANT_PHRASES:
            if self._normalize_for_match(phrase) in t:
                return 100
        # زلزله با بزرگی ≥۵ ریشتر (در عنوان یا خلاصه) → فوری
        m = re.search(r'([0-9۰-۹٠-٩]+(?:[.,٫][0-9۰-۹٠-٩]+)?)\s*ریشتر', t + ' ' + s)
        if m:
            try:
                magnitude = float(m.group(1).translate(_DIGITS_TO_EN).replace('٫', '.').replace(',', '.'))
                if magnitude >= BREAKING_EARTHQUAKE_MIN_MAGNITUDE:
                    return 100
            except ValueError:
                pass
        score = 0
        for kw in BREAKING_STRONG_KEYWORDS:
            k = self._normalize_for_match(kw)
            if k in t:
                score += 3
            elif k in s:
                score += 2
        for kw in BREAKING_SUPPORT_KEYWORDS:
            k = self._normalize_for_match(kw)
            if k in t:
                score += 2
            elif k in s:
                score += 1
        return score

    def _is_breaking_news(self, title, summary=''):
        """🚨 تشخیص خبر فوری با امتیازدهی دقیق (کاهش مثبت/منفی کاذب)"""
        return self._breaking_score(title, summary) >= BREAKING_SCORE_THRESHOLD

    def _normalize(self, text):
        text = re.sub(r'[?!.,،؛:\-_»«\"\'\{\}\[\]\(\)]', ' ', text)
        return re.sub(r'\s+', ' ', text).lower().strip()

    def _remove_common(self, text):
        return ' '.join(w for w in text.split() if w not in COMMON_WORDS_TO_IGNORE)

    def _title_hash(self, title):
        n = self._remove_common(self._normalize(title))
        return hashlib.md5(n.encode()).hexdigest()

    def _similarity(self, a, b):
        na = self._remove_common(self._normalize(a))
        nb = self._remove_common(self._normalize(b))
        return SequenceMatcher(None, na, nb).ratio()

    def _is_duplicate(self, title):
        if len(title) < MIN_TITLE_LENGTH:
            return True
        if self._title_hash(title) in self.sent_hashes:
            return True
        for t in self.sent_titles[-200:]:
            if self._similarity(title, t) >= SIMILARITY_THRESHOLD:
                return True
        return False

    def _mark_sent(self, title):
        self.sent_titles.append(self._normalize(title))
        self.sent_hashes.add(self._title_hash(title))
        if len(self.sent_titles) > 500:
            self.sent_titles = self.sent_titles[-500:]

    # ==================== ذخیره/بارگذاری وضعیت (اجرای ابری) ====================
    def _load_state(self):
        """بارگذاری وضعیت قبلی تا بعد از ری‌استارت، خبر تکراری ارسال نشود"""
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            return
        except Exception as e:
            self.log(f'⚠️ State load failed: {e}')
            return
        self.sent_links = set(data.get('sent_links', []))
        self.sent_titles = list(data.get('sent_titles', []))[-500:]
        self.sent_hashes = set(data.get('sent_hashes', []))
        self.daily_posts = int(data.get('daily_posts', 0))
        try:
            self.last_reset_date = datetime.fromisoformat(
                data.get('last_reset_date', '')).date()
        except Exception:
            pass
        for key in ('total_fetched', 'total_duplicates', 'total_videos_posted',
                    'total_filtered_provinces', 'total_breaking_posted'):
            setattr(self, key, int(data.get(key, 0)))
        try:
            self.last_post_time = datetime.fromisoformat(data['last_post_time'])
            if self.last_post_time.tzinfo is not None:
                self.last_post_time = None
        except (KeyError, TypeError, ValueError):
            pass
        self.pending_news = [item for item in data.get('pending_news', [])
                             if isinstance(item, dict) and item.get('link') and (item.get('title') or item.get('media'))]
        # Drop the old bulk backlog when switching to the real-time relay, but
        # finish any post whose media/text was already partially sent.
        if data.get('relay_mode') != 'realtime_v1':
            self.pending_news = [item for item in self.pending_news if item.get('delivery_started')]
        cursor = data.get('telegram_cursor')
        self.telegram_cursor = cursor if isinstance(cursor, int) and cursor > 0 else None
        self.source_stats = dict(data.get('source_stats', {}))
        self.log(f'📂 State loaded: {len(self.sent_links)} sent links (جلوگیری از ارسال تکراری)')

    def _save_state(self):
        """ذخیره وضعیت به صورت اتمیک (فایل موقت ← جایگزینی)"""
        try:
            state_dir = os.path.dirname(STATE_FILE)
            if state_dir:
                os.makedirs(state_dir, exist_ok=True)
            data = {
                'sent_links': list(self.sent_links)[-STATE_MAX_LINKS:],
                'sent_titles': self.sent_titles[-500:],
                'sent_hashes': list(self.sent_hashes)[-STATE_MAX_LINKS:],
                'daily_posts': self.daily_posts,
                'last_post_time': self.last_post_time.isoformat() if self.last_post_time else None,
                'pending_news': self.pending_news,
                'relay_mode': 'realtime_v1',
                'telegram_cursor': self.telegram_cursor,
                'last_reset_date': self.last_reset_date.isoformat(),
                'total_fetched': self.total_fetched,
                'total_duplicates': self.total_duplicates,
                'total_videos_posted': self.total_videos_posted,
                'total_filtered_provinces': self.total_filtered_provinces,
                'total_breaking_posted': self.total_breaking_posted,
                'source_stats': self.source_stats,
                'updated_at': datetime.now().isoformat(),
            }
            tmp_file = STATE_FILE + '.tmp'
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp_file, STATE_FILE)
        except Exception as e:
            self.log(f'⚠️ State save failed: {e}')

    def _detect_category(self, title, summary=''):
        text = (title + ' ' + summary).lower()
        scores = {}
        for cat, data in NEWS_CATEGORIES.items():
            score = sum(1 for kw in data['keywords'] if kw in text)
            if score:
                scores[cat] = score
        if scores:
            best = max(scores, key=scores.get)
            return best, NEWS_CATEGORIES[best]['emoji']
        return DEFAULT_CATEGORY['name'], DEFAULT_CATEGORY['emoji']

    # ==================== ✍️ سبک خبری (اعمال روی همه خبرها) ====================
    def _style_strip_links(self, text):
        """🔗 حذف کامل لینک از متن خبر - هیچ لینکی نباید در پست روبیکا منتشر شود"""
        # لینک کامل با پروتکل یا www
        text = re.sub(r'(?:https?://|ftp://|www\.)\S+', '', text, flags=re.IGNORECASE)
        # دامنه‌های بدون پروتکل + لینک کوتاه خبرگزاری‌ها (irna.ir/xjAB، t.me/… و ...)
        text = re.sub(
            r'\b(?:[a-zA-Z0-9-]+\.)+'
            r'[a-zA-Z]{2,}'
            r'(?:/\S*)?',
            '', text, flags=re.IGNORECASE)
        # برچسب‌های بی‌لینکِ باقی‌مانده در انتهای متن («مشروح خبر:»، «لینک خبر» و ...)
        text = re.sub(r'[^.؟!؛\n]*لینک[^.؟!؛\n]*[:：]\s*$', '', text)
        text = re.sub(r'(?:لینک|مشروح|جزئیات|متن کامل|ادامه)\s*(?:خبر|مطلب)?\s*[:：]\s*$', '', text)
        text = re.sub(r'لینک\s+(?:خبر|مطلب|مشروح خبر)\s*$', '', text)
        # کلمه انگلیسی «Link» همراه ایموجی مشت گره‌کرده در انتهای متن/خط
        text = re.sub(r'(?im)\blink\b[\s:：]*[' + FIST_EMOJIS + r']*\s*$', '', text)
        text = re.sub(r'(?im)^\s*[' + FIST_EMOJIS + r'\s]*\blink\b\s*$', '', text)
        # حرف اضافه بی‌مفعول در انتهای متن (بعد از حذف لینک)
        text = re.sub(r'\s+(?:در|از|به|با|برای)\s*$', '', text.strip())
        return text.strip()

    def _style_normalize_chars(self, text):
        """اعداد فارسی ۰-۹ + ی/ک فارسی + حذف کشیده + نیم‌فاصله استاندارد"""
        text = text.translate(_DIGITS_TO_FA)
        text = text.replace('ي', 'ی').replace('ك', 'ک')
        text = text.replace('ـ', '')  # کشیده (tatweel)
        text = re.sub(r'\b(می|نمی)\s+', r'\1' + '\u200c', text)          # می رود → می‌رود
        text = re.sub(r'(\w)\s+(ها|های|هایی)\b', '\\1\u200c\\2', text)     # کتاب ها → کتاب‌ها
        return text

    def _style_fix_punctuation(self, text):
        """نشانه‌گذاری فارسی: ، ؛ ؟ + فاصله‌گذاری صحیح"""
        text = text.replace(';', '؛').replace('?', '؟')
        text = re.sub(r'(?<=\d),(?=\d)', '٬', text)   # جداکننده هزارگان
        text = text.replace(',', '،')
        text = re.sub(r'[،؛:]\s*([.؟!])', r'\1', text)              # حذف نشانه اضافی قبل نشانه پایانی
        text = re.sub(r'\s+([،؛؟!:.])', r'\1', text)               # حذف فاصله قبل نشانه
        text = re.sub(r'([،؛؟!:])(?=[^\s\d])', r'\1 ', text)       # یک فاصله بعد نشانه
        text = re.sub(r'\.(?=[^\s\d.])', '. ', text)              # فاصله بعد نقطه (نه اعشار/سه‌نقطه)
        text = re.sub(r'!{2,}', '!', text)
        text = re.sub(r'؟{2,}', '؟', text)
        text = re.sub(r'([؟!])\s*!+', r'\1', text)   # ؟! → ؟
        return text

    def _style_remove_extra_words(self, text):
        """حذف تکرار کلمات و فاصله‌های اضافی"""
        text = re.sub(r'(\S+)\s+\1(?=\s|$)', r'\1', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _style_title(self, title):
        """عنوان خبری: بدون نقطه/دونقطه پایانی، بدون فاصله اضافی"""
        title = title.strip().strip('«»"').strip()
        title = re.sub(r'\s+', ' ', title)
        return title.rstrip('.:،؛').rstrip()

    def _style_summary(self, text):
        """خلاصه خبری: پایان با نقطه (بدون تغییر محتوا)"""
        text = text.strip().rstrip('،؛: ').rstrip()
        if text and text[-1] not in '.؟!…':
            text += '.'
        return text

    def _news_style(self, text, is_title=False):
        """✍️ اعمال سبک خبری روی متن - idempotent (اجرای چندباره بی‌اثر)"""
        if not text:
            return text
        result = self._style_strip_links(text)
        if not NEWS_STYLE_ENABLED:
            return result
        result = self._style_normalize_chars(result)
        result = self._style_fix_punctuation(result)
        result = self._style_remove_extra_words(result)
        return self._style_title(result) if is_title else self._style_summary(result)

    def _summarize(self, text, n=50):
        try:
            text = BeautifulSoup(text, 'html.parser').get_text()
        except:
            pass
        text = re.sub(r'\s+', ' ', text).strip()
        words = text.split()
        if len(words) <= n:
            return text
        s = ' '.join(words[:n])
        return s if s and s[-1] in '؟!?.' else s + '...'

    def _extract_image(self, entry):
        try:
            if getattr(entry, 'media_content', None):
                return entry.media_content[0]['url']
            if getattr(entry, 'enclosures', None):
                for e in entry.enclosures:
                    if 'image' in e.get('type', ''):
                        return e.get('href')
            content = entry.get('summary', '') + entry.get('description', '')
            img = BeautifulSoup(content, 'html.parser').find('img')
            if img and img.get('src'):
                return img['src']
        except:
            pass
        return None

    def _extract_video(self, entry):
        try:
            if getattr(entry, 'enclosures', None):
                for e in entry.enclosures:
                    if 'video' in e.get('type', '') or e.get('href', '').endswith(('.mp4', '.avi', '.mov')):
                        return e.get('href')
            content = entry.get('summary', '') + entry.get('description', '')
            soup = BeautifulSoup(content, 'html.parser')
            v = soup.find('video')
            if v and v.get('src'):
                return v['src']
        except:
            pass
        return None

    # ==================== جمع‌آوری ====================
    @staticmethod
    def _parse_telegram_page(html):
        """Read message IDs and text from Telegram's public web preview."""
        soup = BeautifulSoup(html, 'html.parser')
        posts = []
        for message in soup.select('.tgme_widget_message[data-post]'):
            post = message.get('data-post', '')
            match = re.fullmatch(r'akhbarefori/(\d+)', post, re.IGNORECASE)
            if not match:
                continue
            text_node = message.select_one('.tgme_widget_message_text')
            text = ''
            if text_node:
                for anchor in text_node.find_all('a', href=True):
                    if re.search(r'(?:t\.me|telegram\.me)/akhbarefori(?:/|$|[?#])', anchor['href'], re.IGNORECASE):
                        anchor.decompose()
                for br in text_node.find_all('br'):
                    br.replace_with('\n')
                text = text_node.get_text().strip()
            media = []
            for node in message.select('.tgme_widget_message_photo_wrap, .tgme_widget_message_video_player, video.tgme_widget_message_video'):
                # A video inside its player has already been processed.
                if node.name == 'video' and node.find_parent(class_='tgme_widget_message_video_player'):
                    continue
                classes = node.get('class', [])
                if 'tgme_widget_message_photo_wrap' in classes:
                    match_url = re.search(r"url\(\s*['\"]?([^'\")]+)", node.get('style', ''), re.I)
                    url = match_url.group(1).strip() if match_url else None
                    kind = 'photo'
                else:
                    video = node if node.name == 'video' else node.find('video')
                    source = video.find('source') if video else None
                    url = (video.get('src') if video else None) or (source.get('src') if source else None)
                    kind = 'video'
                if url:
                    url = urljoin(TELEGRAM_URL, url)
                    if urlparse(url).scheme not in ('http', 'https'):
                        url = None
                # Preserve unavailable media rather than silently posting the wrong image.
                media.append({'type': kind, 'url': url})
            timestamp = None
            time_node = message.select_one('time[datetime]')
            if time_node:
                try:
                    parsed = datetime.fromisoformat(time_node['datetime'].replace('Z', '+00:00'))
                    if parsed.tzinfo is not None:
                        timestamp = parsed.timestamp()
                except ValueError:
                    pass
            posts.append((int(match.group(1)), text, media, timestamp))
        return sorted(posts)

    def _telegram_item(self, post_id, text, media=None):
        # Remove channel handles, source/credit lines and URLs; the fixed footer is added at send time.
        lines = []
        for line in text.splitlines():
            line = self._strip_breaking_phrase(re.sub(r'@[A-Za-z0-9_]+', '', line))
            if re.match(r'^\s*(?:📌\s*)?(?:منبع|لینک خبر)\s*[:：]', line):
                continue
            line = self._style_strip_links(line).strip()
            if line and re.search(r'[\w]', line):
                lines.append(line)
        if not lines and not media:
            return None
        return {'title': lines[0] if lines else '', 'summary': '\n'.join(lines[1:]),
                'media': media or [],
                'link': f'https://t.me/{TELEGRAM_CHANNEL}/{post_id}',
                'source': '@akhbarefori', 'category': 'عمومی'}

    async def fetch_all_news(self, is_initial=False):
        """Poll the public preview; walk older pages to avoid gaps after downtime."""
        self.last_fetch_time = datetime.now()
        self.next_fetch_time = self.last_fetch_time + timedelta(seconds=self.fetch_interval)
        try:
            all_posts = {}
            before = None
            cursor = self.telegram_cursor
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                for _ in range(TELEGRAM_MAX_PAGES):
                    params = {'before': before} if before is not None else None
                    async with session.get(TELEGRAM_URL, params=params,
                                           headers={'User-Agent': 'Mozilla/5.0'}) as response:
                        response.raise_for_status()
                        posts = self._parse_telegram_page(await response.text())
                    if not posts:
                        if before is None:
                            raise ValueError('Telegram preview contains no posts')
                        break
                    for post_id, text, media, published_at in posts:
                        if cursor is None or post_id > cursor:
                            all_posts[post_id] = (text, media, published_at)
                    oldest = posts[0][0]
                    if cursor is None or oldest <= cursor:
                        break
                    if before is not None and oldest >= before:
                        raise ValueError('Telegram pagination did not advance')
                    before = oldest
                else:
                    raise ValueError('Telegram history exceeds pagination limit; no cursor advanced')
            queued = {item['link'] for item in self.pending_news}
            count = 0
            for post_id, (text, media, published_at) in sorted(all_posts.items()):
                # On first startup, do not replay historical posts. Recent posts
                # still within their two-minute delay remain eligible.
                if cursor is None and (published_at is None or published_at < time.time() - POST_DELAY):
                    continue
                item = self._telegram_item(post_id, text, media)
                if item:
                    # If Telegram omits a date, wait two minutes from discovery;
                    # never guess that an undated post is already old enough.
                    item['published_at'] = published_at if published_at is not None else time.time()
                if item and item['link'] not in self.sent_links and item['link'] not in queued:
                    self.pending_news.append(item)
                    queued.add(item['link'])
                    count += 1
            if all_posts:
                self.telegram_cursor = max(all_posts)
            self.total_fetched += count
            self.rss_health_check['@akhbarefori'] = 'online'
            self._save_state()
            self.log(f'✅ Telegram @akhbarefori: {count} new posts, {len(self.pending_news)} queued')
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            self.rss_health_check['@akhbarefori'] = 'offline'
            self.log(f'❌ Telegram @akhbarefori fetch failed: {e}')

    def _reset_hourly(self):
        now = datetime.now()
        if (now - self.hourly_reset_time).total_seconds() >= 3600:
            self.hourly_posts = 0
            self.hourly_reset_time = now

    # ==================== قالب پیام (متن ساده برای روبیکا) ====================
    @staticmethod
    def _strip_breaking_phrase(text):
        # Normalize Arabic/Persian variants and ignore spaces, ZWNJ and diacritics.
        text = (text or '').replace('ي', 'ی').replace('ك', 'ک')
        text = re.sub(r'خبر[\s\u200c\u200d\u064b-\u065f]*فور[یي]', '', text)
        return re.sub(r'[ \t]{2,}', ' ', text).strip()

    def _format_full_text(self, news):
        """Legacy formatting, retained to finish deliveries started before an upgrade."""
        title = self._news_style(self._strip_breaking_phrase(news.get('title', '')), is_title=True)
        summary = news.get('summary', '') or ''
        source = news.get('source', '') or ''
        if source:
            summary = re.sub(r'^\s*به گزارش\s+(?:خبرگزاری\s+)?' +
                             re.escape(source) + r'\s*[,،:]\s*', '', summary)
        summary = self._news_style(self._strip_breaking_phrase(summary))
        return '\n\n'.join(part for part in (title, summary) if part)

    def _brief_sentences(self, text):
        """Extract complete sentences/lines; never invent facts or cut decimals."""
        text = self._strip_breaking_phrase(text or '')
        text = self._style_strip_links(text)
        text = re.sub(r'@[A-Za-z0-9_]+', '', text)
        parts = re.split(r'(?<=[؟!?])\s+|(?<!\d)\.(?=\s|$)\s*|(?<=\d)\.(?=\s|$)\s*|\n+', text)
        return [part.strip(' \t\r🔹🔸▪️•-:：') for part in parts
                if re.search(r'[\w]', part)]

    def _format_text(self, news):
        # Extraction, not generative rewriting: retain the headline and at most
        # one non-redundant sentence from the original post.
        title_parts = self._brief_sentences(news.get('title', ''))
        title = self._news_style(title_parts[0], is_title=True) if title_parts else ''
        summary = news.get('summary', '') or ''
        source = news.get('source', '') or ''
        if source:
            summary = re.sub(r'^\s*به گزارش\s+(?:خبرگزاری\s+)?' +
                             re.escape(source) + r'\s*[,،:]\s*', '', summary)
        candidates = title_parts[1:] + self._brief_sentences(summary)
        title_key = re.sub(r'[^\w]', '', title).casefold()
        for sentence in candidates:
            styled = self._news_style(sentence)
            key = re.sub(r'[^\w]', '', styled).casefold()
            if key and key != title_key:
                return '\n\n'.join(part for part in (title, styled) if part)
        return title

    async def _format(self, news):
        return self._format_text(news)

    def _format_viral(self, news):
        return self._format_text(news)

    # ==================== 🏁 فوتر ثابت پایین همه پست‌ها ====================
    def _rubika_channel_address(self):
        """آدرس عمومی کانال روبیکا (مثلاً https://rubika.ir/news360_24)"""
        channel = (self.channel_id or RUBIKA_CHANNEL_ID or '').strip().lstrip('@')
        return f'https://rubika.ir/{channel}' if channel else ''

    def _post_footer(self):
        """فوتر ثابت پایین هر پست: آدرس کانال روبיקה + پرچم ایران"""
        address = self._rubika_channel_address()
        return '\n'.join(part for part in (address, IRAN_FLAG_EMOJI) if part)

    def _with_footer(self, text):
        """افزودن فوتر ثابت به انتهای متن پست (روی همه پست‌ها اعمال می‌شود)"""
        footer = self._post_footer()
        if not footer:
            return text
        text = (text or '').strip()
        return f'{text}\n\n{footer}' if text else footer

    def _post_wait_seconds(self, news=None):
        """Seconds until this post has reached its own Telegram +2 min deadline."""
        if news is None:
            if not self.pending_news:
                return 0
            return min(self._post_wait_seconds(item) for item in self.pending_news)
        if news.get('delivery_started'):
            return 0
        published = news.get('published_at')
        if not isinstance(published, (int, float)):
            # Older partially transferred posts can resume; other legacy items
            # are conservatively treated as discovered now.
            published = time.time()
            news['published_at'] = published
        return max(0, published + POST_DELAY - time.time())

    def _reset_counters(self):
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_posts = 0
            self.last_reset_date = today
            self.source_stats = {}
        self._reset_hourly()

    async def _send_breaking(self, news):
        try:
            if news['link'] in self.sent_links:
                return False
            msg = self._with_footer(await self._format(news))
            await self.bot.send_message(chat_id=self.channel_id, text=msg)
            self.sent_links.add(news['link'])
            self._mark_sent(news['title'])
            self.daily_posts += 1
            self.hourly_posts += 1
            self.last_post_time = datetime.now()
            self.total_breaking_posted += 1
            self._save_state()
            self.log(f'🚨 BREAKING SENT: {news["title"][:60]}...')
            return True
        except Exception as e:
            self.log(f'❌ Breaking send: {e}')
            return False

    async def _send_viral(self, news):
        self._reset_counters()
        if self.daily_posts >= DAILY_NEWS_LIMIT:
            return False
        try:
            news['emoji'] = '🔥'
            news['is_viral'] = True
            msg = self._with_footer(self._format_viral(news))

            await self.bot.send_message(chat_id=self.channel_id, text=msg)
            self.sent_links.add(news.get('link', ''))
            self._mark_sent(news.get('title', ''))
            self.daily_posts += 1
            self.hourly_posts += 1
            self.last_post_time = datetime.now()
            self._save_state()
            self.log(f'🔥 VIRAL SENT: {news.get("title", "")[:50]}...')
            return True
        except Exception as e:
            self.log(f'❌ خطای ارسال وایرال: {e}')
            return False

    async def _refresh_telegram_media(self, news):
        """Refresh expiring preview URLs without replacing a different post's media."""
        match = re.fullmatch(r'https://t\.me/akhbarefori/(\d+)', news['link'])
        if not match:
            return False
        post_id = int(match.group(1))
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.get(TELEGRAM_URL, params={'before': post_id + 1},
                                       headers={'User-Agent': 'Mozilla/5.0'}) as response:
                    response.raise_for_status()
                    posts = self._parse_telegram_page(await response.text())
            updated = next((media for ident, _, media, _ in posts if ident == post_id), None)
            previous = news.get('media')
            if updated is None or (previous is not None and
                                   [m['type'] for m in updated] != [m['type'] for m in previous]):
                return False
            news['media'] = updated
            news['media_needs_refresh'] = False
            self._save_state()
            return True
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            self.log(f'❌ Telegram media refresh: {e}')
            return False

    def _record_delivery_progress(self, news):
        news['delivery_started'] = True
        self.last_post_time = datetime.now()
        self._save_state()

    async def _send_domestic_direct(self, news):
        self._reset_counters()
        try:
            if news['link'] in self.sent_links:
                return False
            # Freeze the text for retries: offsets and previously sent captions
            # must not change if the summarizer is upgraded during delivery.
            msg = news.get('rendered_text')
            if msg is None:
                msg = (self._format_full_text(news) if news.get('delivery_started')
                       else await self._format(news))
                news['rendered_text'] = msg
                self._save_state()
            msg = self._with_footer(msg)
            # Queues saved by older versions did not record media. Look up the
            # original Telegram post before publishing so attachments are not lost.
            if ('media' not in news and re.fullmatch(r'https://t\.me/akhbarefori/\d+', news['link'])
                    and not await self._refresh_telegram_media(news)):
                raise RubikaAPIError('بازیابی رسانه پست قدیمی تلگرام ناموفق بود')
            media = news.get('media', [])
            # Also handle legacy callers and queued items carrying media URLs.
            if not media:
                media = ([{'type': 'photo', 'url': news['image_url']}] if news.get('image_url') else
                         [{'type': 'video', 'url': news['video_url']}] if news.get('video_url') else [])
                if media:
                    news['media'] = media
            if media and (news.get('media_needs_refresh') or any(not m.get('url') for m in media)):
                if not await self._refresh_telegram_media(news):
                    raise RubikaAPIError('رسانه اصلی تلگرام در صفحه عمومی در دسترس نیست')
                media = news['media']
            caption = msg[:RUBIKA_MAX_CAPTION_LENGTH] if media else ''
            while news.get('media_index', 0) < len(media):
                index = news.get('media_index', 0)
                entry = media[index]
                if not entry.get('url'):
                    raise RubikaAPIError('آدرس رسانه تلگرام موجود نیست')
                try:
                    if entry['type'] == 'photo':
                        await self.bot.send_photo(self.channel_id, entry['url'], caption=caption if index == 0 else '')
                    elif entry['type'] == 'video':
                        await self.bot.send_video(self.channel_id, entry['url'], caption=caption if index == 0 else '')
                        self.total_videos_posted += 1
                    else:
                        raise RubikaAPIError('نوع رسانه پشتیبانی نمی‌شود')
                except Exception:
                    news['media_needs_refresh'] = True
                    self._save_state()
                    raise
                news['media_index'] = index + 1
                self._record_delivery_progress(news)

            # Preserve text longer than the caption limit in adjacent messages.
            remainder = msg[len(caption):] if media else msg
            offset = news.get('text_offset', 0)
            while offset < len(remainder):
                chunk = remainder[offset:offset + RUBIKA_MAX_TEXT_LENGTH]
                await self.bot.send_message(chat_id=self.channel_id, text=chunk)
                offset += len(chunk)
                news['text_offset'] = offset
                self._record_delivery_progress(news)
            self.sent_links.add(news['link'])
            self._mark_sent(news.get('title', ''))
            self.daily_posts += 1
            self.hourly_posts += 1
            self._save_state()
            self.log(f'✅ [{news.get("category", "عمومی")}] {news.get("title", "")[:50]}...')
            return True
        except Exception as e:
            self.log(f'❌ post: {e}')
            return False

    async def poll_telegram(self):
        """Keep checking Telegram even while an upload is slow or retrying."""
        while self.is_running:
            now = datetime.now()
            if self.last_fetch_time is None or (now - self.last_fetch_time).total_seconds() >= self.fetch_interval:
                self.cycle_count += 1
                await self.fetch_all_news(is_initial=self.telegram_cursor is None)
            await asyncio.sleep(1)

    async def publish_loop(self):
        """Send each discovered post once its own Telegram timestamp is 2 minutes old."""
        while self.is_running:
            now = time.time()
            news = next((item for item in self.pending_news
                         if self._post_wait_seconds(item) <= 0
                         and self._retry_after.get(item['link'], 0) <= now), None)
            if news is not None:
                link = news['link']
                if link in self.sent_links or await self._send_domestic_direct(news):
                    self.pending_news.remove(news)
                    self._retry_after.pop(link, None)
                    self._save_state()
                    continue
                # One unavailable video must not block other due news.
                self._retry_after[link] = time.time() + RETRY_DELAY
            await asyncio.sleep(1)

    def _secs_to_fetch(self):
        if not self.next_fetch_time:
            return 0
        return max(0, int((self.next_fetch_time - datetime.now()).total_seconds()))

    # ==================== ✅ اجرای اصلی ====================
    async def run(self):
        self.log('=' * 70)
        self.log('🤖 Telegram @akhbarefori → Rubika')
        self.log('=' * 70)
        try:
            info = await self.bot.get_me()
            self.rubika_connected = True
            bot_username = info.get('username') or info.get('bot_title') or 'unknown'
            self.log(f'✅ Rubika Bot: @{bot_username}')
            self.log(f'📢 Rubika Channel: {self.channel_id}')
            try:
                chat = await self.bot.get_chat(self.channel_id)
                if chat:
                    chat_title = chat.get('title') or self.channel_id
                    self.log(f'✅ Channel: {chat_title} ({chat.get("chat_type", "Channel")})')
            except Exception as e:
                self.log(f'⚠️ بررسی کانال ناموفق: {e}')
                self.log('⚠️ مطمئن شوید ربات در کانال روبیکا عضو و ادمین باشد')
            self.log(f'⏱️ Telegram check interval: {self.fetch_interval}s')
            self.log(f'⏸️ Delay after Telegram post: {POST_DELAY}s')
            self.log(f'✍️ News Style: Active (سبک خبری روی همه خبرها)')
            self.log(f'📤 مقصد انتشار: فقط کانال روبیکا')
            self.log('📥 Source: Telegram @akhbarefori | media and text, no links')
            self.log('=' * 70 + '\n')
        except Exception as e:
            self.rubika_connected = False
            self.log(f'❌ Rubika connection failed: {e}')
            self.log('❌ توکن ربات و دسترسی اینترنت را بررسی کنید')
            await self.bot.close()
            return False
        
        self.is_running = True
        poll_task = asyncio.create_task(self.poll_telegram())
        try:
            await self.publish_loop()
        except Exception as e:
            self.log(f'❌ Fatal: {e}')
            import traceback
            traceback.print_exc()
        finally:
            poll_task.cancel()
            try:
                await poll_task
            except asyncio.CancelledError:
                pass
            self.rubika_connected = False
            self._save_state()
            await self.bot.close()
        
        self.log('🛑 Bot stopped')
        return True

    def stop(self):
        self.is_running = False
        self.log('🛑 Stop signal')


if __name__ == '__main__':
    try:
        bot = SmartNewsBot()
    except ValueError as e:
        print(f'❌ {e}')
        print('راهنما: توکن و آیدی کانال را در rubika_config.json یا متغیرهای محیطی تنظیم کنید')
        raise SystemExit(1)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print('\nGoodbye!')