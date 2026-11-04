"""
Telegram News Bot - Dual Algorithm System
✅ Algorithm 1: Smart Priority (الگوریتم هوشمند اولویت‌دار)
✅ Algorithm 2: Source Rotation (الگوریتم چرخش منبع)
✅ Google Translate + News Style Post-Processing
✅ Viral Detection
✅ Source Diversity
"""
import asyncio
import feedparser
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher
import hashlib
import random
import aiohttp
import html
import time
import os
import requests
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor

# ==================== تنظیمات اصلی ====================
BOT_TOKEN = "8902034273:AAEn3wJ-_r7htq7Jm4kXnv39a6qyZ_0n9iM"
CHANNEL_USERNAME = "@news360_24"

if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    raise ValueError("توکن ربات تنظیم نشده!")
if not CHANNEL_USERNAME or CHANNEL_USERNAME == "@your_channel":
    raise ValueError("نام کانال تنظیم نشده!")

# ==================== ✅ نام الگوریتم‌ها ====================
ALGORITHM_SMART_PRIORITY = "smart_priority"      # الگوریتم 1
ALGORITHM_SOURCE_ROTATION = "source_rotation"    # الگوریتم 2

# ==================== منابع خبری ====================
NEWS_SOURCES = {
    'ایرنا': 'https://www.irna.ir/rss',
    'ایسنا': 'https://www.isna.ir/rss',
    'مهر': 'https://www.mehrnews.com/rss',
    'فارس': 'https://www.farsnews.ir/rss/allnews',
    'خبرآنلاین': 'https://www.khabaronline.ir/rss/allnews',
    'خبرگزاری جوان': 'https://www.yjc.ir/fa/rss/allnews',
}

INTERNATIONAL_SOURCES = {
    'BBC': 'http://feeds.bbci.co.uk/news/rss.xml',
    'Reuters': 'https://news.google.com/rss/search?q=iran&hl=en-US&gl=US&ceid=US:en',
    'CNN': 'http://rss.cnn.com/rss/edition_world.rss',
    'Al Jazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
}

# ==================== تنظیمات زمانی ====================
FETCH_INTERVAL = 30 * 60
MIN_POST_DELAY = 120
MAX_POST_DELAY = 200

# ==================== ✅ الگوریتم 2: چرخش منبع ====================
# ساختار بهینه: (نوع, منبع, بازه_انتظار)
# نوع: 'publish' = انتشار خبر | 'wait' = انتظار
SOURCE_ROTATION_CYCLE = [
    # مرحله 1-2
    ('publish', 'ایرنا', None),
    ('wait', None, (120, 160)),
    # مرحله 3-4
    ('publish', 'الجزیره', None),
    ('wait', None, (120, 140)),
    # مرحله 5-6
    ('publish', 'مهر', None),
    ('wait', None, (120, 160)),
    # مرحله 7-8
    ('publish', 'خبرگزاری جوان', None),
    ('wait', None, (120, 160)),
    # مرحله 9-10
    ('publish', 'CNN', None),
    ('wait', None, (45, 60)),
    # مرحله 11-12
    ('publish', 'ایرنا', None),
    ('wait', None, (45, 60)),
    # مرحله 13-14
    ('publish', 'ایسنا', None),
    ('wait', None, (120, 160)),
    # مرحله 15-16
    ('publish', 'Reuters', None),
    ('wait', None, (45, 60)),
    # مرحله 17-18
    ('publish', 'BBC', None),
    ('wait', None, (120, 160)),
    # مرحله 19-20
    ('publish', 'مهر', None),
    ('wait', None, (60, 75)),
]

# ==================== تنظیمات محتوا ====================
INCLUDE_IMAGES = True
INCLUDE_VIDEOS = True
SUMMARY_WORDS = 90
INTERNATIONAL_SUMMARY_WORDS = 60

# ==================== تنظیمات ترجمه ====================
USE_GOOGLE_TRANSLATE = True
TRANSLATION_TITLE_MAX_WORDS = 15
TRANSLATION_SUMMARY_MAX_WORDS = 60
TRANSLATION_RETRY_DELAY = 2
TRANSLATION_MAX_RETRIES = 2

# ==================== دیکشنری اصطلاحات خبری ====================
NEWS_TERMS_DICTIONARY = {
    "said": "اعلام کرد", "announced": "اعلام کرد", "stated": "بیان کرد",
    "reported": "گزارش داد", "revealed": "افشا کرد", "confirmed": "تأیید کرد",
    "denied": "رد کرد", "warned": "هشدار داد", "emphasized": "تأکید کرد",
    "highlighted": "اشاره کرد", "explained": "توضیح داد", "claimed": "ادعا کرد",
    "accused": "متهم کرد", "demanded": "خواستار شد", "urged": "فراخوان داد",
    "called for": "فراخوان داد", "threatened": "تهدید کرد", "promised": "قول داد",
    "agreed": "موافقت کرد", "rejected": "رد کرد", "approved": "تصویب کرد",
    "signed": "امضا کرد", "launched": "آغاز کرد", "initiated": "آغاز کرد",
    "completed": "کامل کرد", "achieved": "دست یافت", "received": "دریافت کرد",
    "provided": "ارائه داد", "offered": "پیشنهاد داد", "proposed": "پیشنهاد کرد",
    "suggested": "پیشنهاد داد", "recommended": "توصیه کرد", "requested": "درخواست کرد",
    "investigated": "بررسی کرد", "analyzed": "تحلیل کرد", "evaluated": "ارزیابی کرد",
    "monitored": "نظارت کرد", "discovered": "کشف کرد", "identified": "شناسایی کرد",
    "prevented": "جلوگیری کرد", "stopped": "متوقف کرد", "ended": "پایان داد",
    "began": "آغاز کرد", "started": "شروع کرد", "continued": "ادامه داد",
    "resumed": "از سر گرفت", "suspended": "تعلیق کرد", "postponed": "به تعویق انداخت",
    "canceled": "لغو کرد", "killed": "کشته شد", "injured": "مجروح شد",
    "arrested": "دستگیر شد", "released": "آزاد شد", "elected": "انتخاب شد",
    "appointed": "منصوب شد", "resigned": "استعفا داد", "dismissed": "برکنار شد",
    "president": "رئیس‌جمهور", "prime minister": "نخست‌وزیر", "minister": "وزیر",
    "parliament": "مجلس", "government": "دولت", "administration": "دولت",
    "official": "مقام", "spokesman": "سخنگو", "spokesperson": "سخنگو",
    "ambassador": "سفیر", "diplomat": "دیپلمات", "senator": "سناتور",
    "congressman": "نماینده کنگره", "lawmaker": "قانون‌گذار", "opposition": "اپوزیسیون",
    "coalition": "ائتلاف", "alliance": "اتحاد", "treaty": "معاهده",
    "agreement": "توافق", "sanctions": "تحریم‌ها", "embargo": "تحریم",
    "resolution": "قطعنامه", "summit": "نشست", "meeting": "جلسه",
    "conference": "کنفرانس", "negotiations": "مذاکرات", "dialogue": "گفت‌وگو",
    "economy": "اقتصاد", "market": "بازار", "stock": "بورس", "inflation": "تورم",
    "unemployment": "بیکاری", "growth": "رشد", "recession": "رکود",
    "investment": "سرمایه‌گذاری", "trade": "تجارت", "export": "صادرات",
    "import": "واردات", "currency": "ارز", "dollar": "دلار", "euro": "یورو",
    "oil": "نفت", "gas": "گاز", "energy": "انرژی", "budget": "بودجه",
    "deficit": "کسری", "surplus": "مازاد", "debt": "بدهی", "loan": "وام",
    "interest": "بهره", "tax": "مالیات", "revenue": "درآمد", "profit": "سود",
    "loss": "ضرر", "company": "شرکت", "corporation": "شرکت", "business": "کسب‌وکار",
    "industry": "صنعت", "sector": "بخش", "military": "نظامی", "army": "ارتش",
    "force": "نیرو", "troops": "نیروها", "soldier": "سرباز", "commander": "فرمانده",
    "general": "ژنرال", "attack": "حمله", "strike": "حمله", "bombing": "بمباران",
    "missile": "موشک", "weapon": "سلاح", "war": "جنگ", "conflict": "درگیری",
    "battle": "نبرد", "operation": "عملیات", "mission": "مأموریت", "security": "امنیت",
    "defense": "دفاع", "intelligence": "اطلاعات", "terrorist": "تروریست",
    "terrorism": "تروریسم", "protest": "اعتراض", "demonstration": "تظاهرات",
    "riot": "شورش", "strike": "اعتصاب", "worker": "کارگر", "union": "اتحادیه",
    "student": "دانشجو", "teacher": "معلم", "doctor": "پزشک", "hospital": "بیمارستان",
    "school": "مدرسه", "university": "دانشگاه", "education": "آموزش", "health": "بهداشت",
    "medical": "پزشکی", "disease": "بیماری", "virus": "ویروس", "pandemic": "همه‌گیری",
    "vaccine": "واکسن", "treatment": "درمان", "patient": "بیمار",
}

NEWS_PATTERNS = [
    (r'(\d+)\s+percent', r'\1 درصد'),
    (r'(\d+)\s+billion', r'\1 میلیارد'),
    (r'(\d+)\s+million', r'\1 میلیون'),
    (r'(\d+)\s+thousand', r'\1 هزار'),
    (r'(\d+)\s+trillion', r'\1 تریلیون'),
    (r'According to\s+(.+)', r'به گفته \1'),
    (r'As reported by\s+(.+)', r'به گزارش \1'),
    (r'Reuters reported', 'خبرگزاری رویترز گزارش داد'),
    (r'BBC reported', 'بی‌بی‌سی گزارش داد'),
    (r'CNN reported', 'سی‌ان‌ان گزارش داد'),
]

# ==================== تنظیمات وایرال ====================
VIRAL_SIMILARITY_THRESHOLD = 0.55
VIRAL_SOURCES_MIN = 2
VIRAL_KEYWORDS_FA = [
    'فوری', 'breaking', 'واکنش', 'جنجال', 'بحران', 'شوکه',
    'تکان‌دهنده', 'اعتراض', 'آشوب', 'شورش', 'استعفا', 'برکناری',
    'ترور', 'اعدام', 'درگیری', 'محاکمه', 'فساد',
]
VIRAL_KEYWORDS_EN = [
    'breaking', 'shocking', 'crisis', 'outrage', 'chaos', 'riot',
    'protest', 'resignation', 'assassination', 'scandal', 'controversy',
    'bombshell', 'exclusive', 'alert', 'urgent', 'just in',
]

# ==================== الگوریتم 1: Smart Priority ====================
PUBLISH_CYCLE_SLOTS = [
    {'type': 'breaking', 'weight': 2},
    {'type': 'breaking', 'weight': 2},
    {'type': 'viral', 'weight': 4},
    {'type': 'viral', 'weight': 4},
    {'type': 'viral', 'weight': 4},
    {'type': 'viral', 'weight': 4},
    {'type': 'domestic', 'category': 'سیاسی', 'weight': 4},
    {'type': 'domestic', 'category': 'اقتصادی', 'weight': 4},
    {'type': 'domestic', 'category': 'حوادث', 'weight': 4},
    {'type': 'domestic', 'category': 'بین‌الملل', 'weight': 4},
    {'type': 'international', 'category': 'سیاسی', 'weight': 4},
    {'type': 'international', 'category': 'اقتصادی', 'weight': 4},
    {'type': 'international', 'category': 'بین‌الملل', 'weight': 4},
    {'type': 'international', 'category': 'حوادث', 'weight': 4},
    {'type': 'domestic', 'category': 'ورزشی', 'weight': 4},
    {'type': 'domestic', 'category': 'بهداشت', 'weight': 4},
    {'type': 'domestic', 'category': 'فناوری', 'weight': 4},
    {'type': 'domestic', 'category': 'عمومی', 'weight': 4},
    {'type': 'international', 'category': 'ورزشی', 'weight': 2},
    {'type': 'international', 'category': 'عمومی', 'weight': 2},
]

# ==================== تنظیمات مخزن ====================
DAILY_NEWS_LIMIT = 500
DAILY_INTERNATIONAL_LIMIT = 25
MAX_POOL_SIZE = 1500
AUTO_CLEANUP_THRESHOLD = 250
OLD_NEWS_HOURS = 6
INTERNATIONAL_MAX_KEEP = 30

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

# ==================== Breaking News ====================
BREAKING_KEYWORDS_FA = [
    'حمله به ایران', 'حمله آمریکا به ایران', 'حمله اسرائیل به ایران',
    'بمباران ایران', 'موشک به ایران', 'جنگ با ایران', 'حمله به تهران',
    'حمله هوایی به ایران', 'ضربه به ایران', 'اسرائیل ایران را بمباران',
    'آمریکا ایران را بمباران', 'آمریکا به ایران حمله', 'اسرائیل به ایران حمله',
    'ایران مورد حمله', 'حمله نظامی به ایران',
]

BREAKING_KEYWORDS_EN = [
    'attack on iran', 'us attacks iran', 'israel attacks iran',
    'iran attacked', 'iran bombed', 'bombing iran', 'missile strike iran',
    'airstrike iran', 'airstrike on iran', 'war with iran', 'strike on iran',
    'us strikes iran', 'israel strikes iran', 'iran under attack', 'military strike iran',
]

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
    'BBC': 'BBC',
    'Reuters': 'Reuters',
    'CNN': 'CNN',
    'Al Jazeera': 'Al Jazeera',
    'الجزیره': 'Al Jazeera',
    'رویترز': 'Reuters',
}


# ==================== مخزن خبر ====================
class BalancedNewsPool:
    def __init__(self):
        self.domestic_news = {cat: [] for cat in NEWS_CATEGORIES}
        self.domestic_news['عمومی'] = []
        self.domestic_post_count = {cat: 0 for cat in NEWS_CATEGORIES}
        self.domestic_post_count['عمومی'] = 0
        self.international_news = []
        self.breaking_queue = []
        self.viral_queue = []

        self.last_domestic_source = None
        self.last_international_source = None
        self.last_domestic_category = None
        self.cycle_index = 0
        self.cycle_slots = PUBLISH_CYCLE_SLOTS
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

    def check_and_mark_viral(self, title, source, is_international=False):
        normalized = re.sub(r'[^\w\s]', '', title.lower().strip())
        normalized = re.sub(r'\s+', ' ', normalized)
        if source not in self.recent_titles_by_source:
            self.recent_titles_by_source[source] = []
        viral_count = 0
        for other_source, titles in self.recent_titles_by_source.items():
            if other_source == source:
                continue
            other_is_intl = other_source.startswith('🌍')
            if is_international != other_is_intl:
                continue
            for other_title in titles:
                other_norm = re.sub(r'[^\w\s]', '', other_title.lower().strip())
                other_norm = re.sub(r'\s+', ' ', other_norm)
                sim = SequenceMatcher(None, normalized, other_norm).ratio()
                if sim >= VIRAL_SIMILARITY_THRESHOLD:
                    viral_count += 1
                    break
        self.recent_titles_by_source[source].append(title)
        if len(self.recent_titles_by_source[source]) > 50:
            self.recent_titles_by_source[source] = self.recent_titles_by_source[source][-50:]
        return viral_count >= VIRAL_SOURCES_MIN

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
        self.international_news = [
            item for item in self.international_news
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
        if len(self.international_news) > INTERNATIONAL_MAX_KEEP:
            self.international_news = self.international_news[:INTERNATIONAL_MAX_KEEP]
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

    def get_next_domestic(self, preferred_category=None, avoid_source=None):
        if preferred_category:
            categories = [preferred_category] + [
                c for c in self.domestic_news.keys() if c != preferred_category
            ]
        else:
            categories = sorted(
                self.domestic_news.keys(),
                key=lambda c: (
                    NEWS_CATEGORIES.get(c, DEFAULT_CATEGORY)['priority'],
                    -len(self.domestic_news.get(c, []))
                )
            )
        for cat in categories:
            items = self.domestic_news.get(cat, [])
            if not items:
                continue
            for i, item in enumerate(items):
                if item.get('source') != avoid_source:
                    self.domestic_news[cat].pop(i)
                    self.domestic_post_count[cat] += 1
                    self.last_domestic_source = item.get('source')
                    self.last_domestic_category = cat
                    return item
            if items:
                item = items.pop(0)
                self.domestic_post_count[cat] += 1
                self.last_domestic_source = item.get('source')
                self.last_domestic_category = cat
                return item
        return None

    def domestic_size(self):
        return sum(len(v) for v in self.domestic_news.values())

    def add_international(self, item):
        self.smart_cleanup()
        self.international_news.append(item)

    def get_next_international(self, preferred_category=None, avoid_source=None):
        if not self.international_news:
            return None
        def priority_score(item):
            cat = item.get('category', 'عمومی')
            score = 0
            if cat == 'سیاسی':
                score = 100
            elif cat == 'بین‌الملل':
                score = 80
            elif cat == 'اقتصادی':
                score = 60
            elif cat == 'حوادث':
                score = 40
            else:
                score = 20
            if item.get('is_viral'):
                score += 50
            if preferred_category and cat == preferred_category:
                score += 30
            return score
        sorted_news = sorted(
            self.international_news,
            key=priority_score,
            reverse=True
        )
        for i, item in enumerate(sorted_news):
            if item.get('source') != avoid_source:
                for j, orig_item in enumerate(self.international_news):
                    if orig_item is item:
                        self.international_news.pop(j)
                        self.last_international_source = item.get('source')
                        return item
        if self.international_news:
            item = self.international_news.pop(0)
            self.last_international_source = item.get('source')
            return item
        return None

    def international_size(self):
        return len(self.international_news)

    # ==================== ✅ متد جدید برای الگوریتم 2 ====================
    def get_next_from_source(self, source_name):
        """✅ دریافت اولین خبر از منبع مشخص (برای الگوریتم چرخش منبع)
        
        Args:
            source_name: نام منبع (مثلاً 'ایرنا', 'BBC', 'CNN')
        
        Returns:
            tuple: (item, source_type) یا (None, None)
            source_type: 'domestic' یا 'international'
        """
        if not source_name:
            return None, None
        
        # ✅ جستجو در اخبار داخلی
        for cat in self.domestic_news.keys():
            items = self.domestic_news.get(cat, [])
            for i, item in enumerate(items):
                if item.get('source') == source_name:
                    self.domestic_news[cat].pop(i)
                    self.domestic_post_count[cat] += 1
                    self.last_domestic_source = source_name
                    return item, 'domestic'
        
        # ✅ جستجو در اخبار بین‌المللی (با پیشوند 🌍)
        intl_source = f'🌍 {source_name}'
        for i, item in enumerate(self.international_news):
            if item.get('source') == intl_source or item.get('source') == source_name:
                self.international_news.pop(i)
                self.last_international_source = source_name
                return item, 'international'
        
        return None, None

    # ==================== الگوریتم 1: Smart Priority ====================
    def get_next_slot(self):
        slot = self.cycle_slots[self.cycle_index % len(self.cycle_slots)]
        self.cycle_index += 1
        return slot

    def get_next_by_cycle(self):
        slot = self.get_next_slot()
        slot_type = slot.get('type')
        if self.has_breaking():
            return self.get_next_breaking(), 'breaking'
        if slot_type == 'viral' and self.has_viral():
            return self.get_next_viral(), 'viral'
        if slot_type == 'domestic':
            preferred_cat = slot.get('category')
            item = self.get_next_domestic(
                preferred_category=preferred_cat,
                avoid_source=self.last_domestic_source
            )
            if item:
                return item, 'domestic'
            item = self.get_next_domestic(avoid_source=self.last_domestic_source)
            if item:
                return item, 'domestic'
        if slot_type == 'international':
            preferred_cat = slot.get('category')
            item = self.get_next_international(
                preferred_category=preferred_cat,
                avoid_source=self.last_international_source
            )
            if item:
                return item, 'international'
            item = self.get_next_international(avoid_source=self.last_international_source)
            if item:
                return item, 'international'
        if self.has_viral():
            return self.get_next_viral(), 'viral'
        if self.domestic_size() > 0:
            item = self.get_next_domestic(avoid_source=self.last_domestic_source)
            if item:
                return item, 'domestic'
        if self.international_size() > 0:
            item = self.get_next_international(avoid_source=self.last_international_source)
            if item:
                return item, 'international'
        return None, None

    def size(self):
        return (self.domestic_size() + self.international_size() +
                self.breaking_size() + self.viral_size())

    def get_stats(self):
        stats = {cat: len(items) for cat, items in self.domestic_news.items()}
        stats['🚨 Breaking'] = self.breaking_size()
        stats['🔥 Viral'] = self.viral_size()
        stats['🌍 International'] = self.international_size()
        return stats


# ==================== ربات اصلی ====================
class SmartNewsBot:
    def __init__(self, log_callback=None):
        self.bot = Bot(token=BOT_TOKEN)
        self.news_pool = BalancedNewsPool()
        self.sent_links = set()
        self.sent_titles = []
        self.sent_hashes = set()

        self.daily_posts = 0
        self.hourly_posts = 0
        self.hourly_reset_time = datetime.now()
        self.daily_international_posts = 0
        self.last_reset_date = datetime.now().date()
        self.total_fetched = 0
        self.total_duplicates = 0
        self.total_videos_posted = 0
        self.total_international_fetched = 0
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
        self.news_pool.set_log_callback(log_callback)

        self.translation_stats = {'google': 0, 'failed': 0}
        self._translator_executor = ThreadPoolExecutor(max_workers=3)

        # ✅ ✅ ✅ تنظیمات الگوریتم‌ها
        self.current_algorithm = ALGORITHM_SMART_PRIORITY  # الگوریتم پیش‌فرض
        
        # ✅ متغیرهای الگوریتم 2: Source Rotation
        self.rotation_step = 0  # شمارنده مرحله فعلی
        self.rotation_cycle_length = len(SOURCE_ROTATION_CYCLE)

    def log(self, msg):
        print(msg)
        if self.log_callback:
            try:
                self.log_callback(msg)
            except:
                pass

    # ==================== ✅ مدیریت الگوریتم‌ها ====================
    def set_algorithm(self, algorithm_name):
        """تغییر الگوریتم انتشار"""
        if algorithm_name in [ALGORITHM_SMART_PRIORITY, ALGORITHM_SOURCE_ROTATION]:
            self.current_algorithm = algorithm_name
            if algorithm_name == ALGORITHM_SOURCE_ROTATION:
                self.rotation_step = 0
                self.log(f"🔄 الگوریتم تغییر کرد: Source Rotation")
            else:
                self.log(f"🔄 الگوریتم تغییر کرد: Smart Priority")
            return True
        return False

    def get_algorithm_name(self):
        """دریافت نام قابل نمایش الگوریتم فعلی"""
        if self.current_algorithm == ALGORITHM_SMART_PRIORITY:
            return "Smart Priority"
        elif self.current_algorithm == ALGORITHM_SOURCE_ROTATION:
            return "Source Rotation"
        return "Unknown"

    def get_current_step_info(self):
        """✅ دریافت اطلاعات مرحله فعلی (برای UI)"""
        if self.current_algorithm != ALGORITHM_SOURCE_ROTATION:
            return None
        
        step_type, source, wait_range = SOURCE_ROTATION_CYCLE[self.rotation_step]
        step_number = self.rotation_step + 1  # شماره مرحله (1-based)
        
        return {
            'step_number': step_number,
            'step_type': step_type,
            'source': source,
            'wait_range': wait_range,
            'total_steps': self.rotation_cycle_length,
        }

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

    def _is_breaking_news(self, title, summary=''):
        text = (title + ' ' + summary).lower()
        for kw in BREAKING_KEYWORDS_FA:
            if kw in text:
                return True
        for kw in BREAKING_KEYWORDS_EN:
            if kw in text:
                return True
        return False

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

    # ==================== ترجمه ====================
    def _translate_sync(self, text, src="en", tgt="fa"):
        try:
            translator = GoogleTranslator(source=src, target=tgt)
            result = translator.translate(text)
            return result
        except Exception as e:
            return None

    async def _smart_translate(self, text, max_words=40, src="en", tgt="fa", is_title=False):
        if not text or not text.strip():
            return None

        words = text.split()
        if len(words) > max_words * 2:
            text = " ".join(words[:max_words * 2])

        for attempt in range(TRANSLATION_MAX_RETRIES):
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self._translator_executor,
                    self._translate_sync,
                    text, src, tgt
                )

                if not result:
                    await asyncio.sleep(TRANSLATION_RETRY_DELAY)
                    continue

                result = self._apply_news_style(result, text, is_title=is_title)
                result = self._clean_translation(result)

                if result:
                    self.translation_stats['google'] += 1
                    preview = result[:60] + "..." if len(result) > 60 else result
                    self.log(f"✅ ترجمه: {preview}")
                    return result

            except Exception as e:
                self.log(f"⚠️ خطای ترجمه (تلاش {attempt+1}): {e}")
                await asyncio.sleep(TRANSLATION_RETRY_DELAY)

        self.translation_stats['failed'] += 1
        self.log(f"❌ ترجمه ناموفق: {text[:40]}...")
        return None

    def _apply_news_style(self, translated_text, original_text, is_title=False):
        result = translated_text
        for pattern, replacement in NEWS_PATTERNS:
            try:
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            except:
                pass
        result = self._convert_numbers_to_persian(result)
        result = self._fix_punctuation(result)
        result = self._remove_extra_words(result)
        if is_title:
            result = self._optimize_title(result)
        else:
            result = self._ensure_verb_ending(result)
        return result

    def _optimize_title(self, title):
        if not title:
            return title
        if title.startswith("که "):
            title = title[3:]
        if title.startswith("در "):
            title = title[3:]
        title = title.strip()
        if title and not title.endswith(('؟', '!', '.', '؛')):
            if len(title.split()) >= 3:
                verb_suffixes = ['کرد', 'شد', 'بود', 'گفت', 'داد', 'گرفت', 'آمد', 'رفت',
                                'داشت', 'خواست', 'توانست', 'گردید', 'یافت', 'کردند',
                                'شدند', 'بودند', 'گفتند', 'دادند', 'گرفتند']
                has_verb = any(title.endswith(v) or title.endswith(v + '.') for v in verb_suffixes)
                if not has_verb and not title.endswith(('.', '؟', '!')):
                    if any(w in title for w in ['اعلام', 'گفت', 'بیان']):
                        if not title.endswith('کرد'):
                            title += ' کرد'
                    elif any(w in title for w in ['شروع', 'آغاز']):
                        if not title.endswith('شد'):
                            title += ' شد'
        if title.endswith('.'):
            title = title[:-1].strip()
        words = title.split()
        if len(words) > TRANSLATION_TITLE_MAX_WORDS:
            title = ' '.join(words[:TRANSLATION_TITLE_MAX_WORDS])
        return title.strip()

    def _convert_numbers_to_persian(self, text):
        english_to_persian = {
            '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
            '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹',
        }
        for eng, per in english_to_persian.items():
            text = text.replace(eng, per)
        return text

    def _fix_punctuation(self, text):
        replacements = [
            (',', '،'), (';', '؛'), ('?', '؟'),
            ('"', '"'), ('"', '"'), ("'", '''), ("'", '''),
        ]
        for eng, fa in replacements:
            text = text.replace(eng, fa)
        text = re.sub(r'\s+([،؛؟!.])', r'\1', text)
        text = re.sub(r'([،؛؟!.])([^\s])', r'\1 \2', text)
        return text

    def _remove_extra_words(self, text):
        duplicates = [
            'که که', 'را را', 'از از', 'به به', 'در در',
            'این این', 'آن آن', 'با با', 'و و', 'بر بر',
        ]
        for duplicate in duplicates:
            word = duplicate.split()[0]
            text = text.replace(duplicate, word)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _ensure_verb_ending(self, text):
        if not text:
            return text
        text = text.strip()
        verb_endings = [
            'کرد', 'شد', 'بود', 'گفت', 'داد', 'گرفت', 'آمد', 'رفت',
            'داشت', 'خواست', 'توانست', 'گردید', 'یافت', 'کردند',
            'شدند', 'بودند', 'گفتند', 'دادند', 'گرفتند', 'آمدند',
            'رفتند', 'داشتند', 'خواستند', 'توانستند', 'گردیدند', 'یافتند',
        ]
        if text and not any(text.rstrip('.؟!').endswith(ending) for ending in verb_endings):
            if len(text.split()) > 3:
                if not text.endswith(('.', '؟', '!')):
                    if not text.endswith('کرد') and not text.endswith('شد'):
                        text += ' کرد'
        return text

    def _clean_translation(self, text):
        if not text:
            return ""
        prefixes_to_remove = [
            "Persian Translation:", "ترجمه:", "ترجمه فارسی:",
            "Translation:", "Output:", "خروجی:", "پاسخ:", "ترجمه به فارسی:",
        ]
        for prefix in prefixes_to_remove:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        text = text.strip('"').strip("'").strip('«').strip('»').strip()
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = ' '.join(lines)
        text = re.sub(r'\s+', ' ', text).strip()
        for marker in ["Note:", "توضیح:", "Note that", "توجه:", "ترجمه تحت‌اللفظی:"]:
            if marker in text:
                text = text.split(marker)[0].strip()
        return text

    # ==================== جمع‌آوری ====================
    async def fetch_all_news(self, is_initial=False):
        label = 'INITIAL' if is_initial else f'REFRESH #{self.cycle_count}'
        self.log(f'\n{"="*70}\n📥 FETCH - {label}\n{"="*70}')
        cycle_hashes = set()
        n_breaking = n_domestic = n_intl = n_dup = 0
        self.log('\n🇮🇷 Domestic sources...\n')
        for source, url in NEWS_SOURCES.items():
            try:
                start_time = time.time()
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers, timeout=10)
                feed = feedparser.parse(response.content)
                response_time = (time.time() - start_time) * 1000
                if not feed.entries:
                    self.rss_health_check[source] = 'offline'
                    continue
                self.rss_health_check[source] = 'slow' if response_time > 3000 else 'online'
                s_new = s_brk = 0
                for entry in feed.entries[:15]:
                    title = getattr(entry, 'title', '').strip()
                    link = entry.get('link', '')
                    if not title:
                        continue
                    th = self._title_hash(title)
                    if self._is_duplicate(title) or th in cycle_hashes or link in self.sent_links:
                        n_dup += 1
                        continue
                    cycle_hashes.add(th)
                    summary = self._summarize(entry.get('summary', entry.get('description', '')), SUMMARY_WORDS)
                    if self._should_filter_province(title, summary):
                        continue
                    cat, emoji = self._detect_category(title, summary)
                    item = {
                        'title': title, 'link': link, 'source': source, 'summary': summary,
                        'image_url': self._extract_image(entry) if INCLUDE_IMAGES else None,
                        'video_url': self._extract_video(entry) if INCLUDE_VIDEOS else None,
                        'category': cat, 'emoji': emoji, 'fetched_at': datetime.now(),
                    }
                    if self._is_breaking_news(title, summary):
                        item['emoji'] = '🚨'
                        self.news_pool.add_breaking(item)
                        s_brk += 1
                        n_breaking += 1
                    else:
                        self.news_pool.add_domestic(item)
                        s_new += 1
                        n_domestic += 1
                    self.source_stats[source] = self.source_stats.get(source, 0) + 1
                self.log(f'✅ {source}: {s_new} new ({response_time:.0f}ms)')
                await asyncio.sleep(0.3)
            except Exception as e:
                self.rss_health_check[source] = 'offline'
                self.log(f'❌ {source}: {e}')

        self.log('\n🌍 International sources...\n')
        for source, url in INTERNATIONAL_SOURCES.items():
            try:
                start_time = time.time()
                feed = feedparser.parse(url)
                response_time = (time.time() - start_time) * 1000
                if not feed.entries:
                    self.rss_health_check[source] = 'offline'
                    continue
                self.rss_health_check[source] = 'slow' if response_time > 3000 else 'online'
                s_new = 0
                for entry in feed.entries[:10]:
                    title_en = getattr(entry, 'title', '').strip()
                    link = entry.get('link', '')
                    if not title_en:
                        continue
                    th = self._title_hash(title_en)
                    if self._is_duplicate(title_en) or th in cycle_hashes or link in self.sent_links:
                        continue
                    cycle_hashes.add(th)
                    summary_en = self._summarize(entry.get('summary', entry.get('description', '')), INTERNATIONAL_SUMMARY_WORDS)
                    item = {
                        'title_en': title_en, 'summary_en': summary_en, 'link': link,
                        'source': f'🌍 {source}',
                        'image_url': self._extract_image(entry) if INCLUDE_IMAGES else None,
                        'video_url': self._extract_video(entry) if INCLUDE_VIDEOS else None,
                        'is_international': True,
                        'is_breaking': self._is_breaking_news(title_en, summary_en),
                        'fetched_at': datetime.now(),
                    }
                    self.news_pool.add_international(item)
                    s_new += 1
                    n_intl += 1
                    self.source_stats[source] = self.source_stats.get(source, 0) + 1
                self.log(f'✅ {source}: {s_new} new ({response_time:.0f}ms)')
                await asyncio.sleep(0.3)
            except Exception as e:
                self.rss_health_check[source] = 'offline'
                self.log(f'❌ {source}: {e}')

        self.log('\n🔥 Checking for viral news...')
        viral_detected = 0
        for cat in list(self.news_pool.domestic_news.keys()):
            items = self.news_pool.domestic_news[cat]
            keep_items = []
            for item in items:
                if self.news_pool.check_and_mark_viral(item['title'], item['source'], False):
                    viral_detected += 1
                    self.news_pool.add_viral(item)
                    self.log(f"🔥 VIRAL [FA]: {item['title'][:50]}...")
                else:
                    keep_items.append(item)
            self.news_pool.domestic_news[cat] = keep_items

        keep_intl = []
        for item in self.news_pool.international_news:
            if self.news_pool.check_and_mark_viral(item['title_en'], item['source'], True):
                viral_detected += 1
                item['category'], item['emoji'] = self._detect_category(item['title_en'], item.get('summary_en', ''))
                self.news_pool.add_viral(item)
                self.log(f"🔥 VIRAL [EN]: {item['title_en'][:50]}...")
            else:
                keep_intl.append(item)
        self.news_pool.international_news = keep_intl

        if viral_detected > 0:
            self.log(f"🔥 Total viral news detected: {viral_detected}")
        else:
            self.log("ℹ️ No viral news in this cycle")

        self.total_fetched += n_domestic
        self.total_duplicates += n_dup
        self.total_international_fetched += n_intl
        self.last_fetch_time = datetime.now()
        self.log(f'\n📊 FETCH DONE | 🚨{n_breaking} 📰{n_domestic} 🌍{n_intl} 🔄{n_dup} 📦pool={self.news_pool.size()}\n')

    def _reset_hourly(self):
        now = datetime.now()
        if (now - self.hourly_reset_time).total_seconds() >= 3600:
            self.hourly_posts = 0
            self.hourly_reset_time = now

    async def _format(self, news):
        source = html.escape(news.get('source', ''))
        title = html.escape(news.get('title', ''))
        summary = html.escape(news.get('summary', ''))
        link = news.get('link', '')
        emoji = news.get('emoji', '📰')
        header = '🔴 <b>🚨🚨🚨 خبر فوری</b>\n\n' if news.get('is_breaking') else ''
        return (
            f'{header}{emoji} <b>{title}</b>\n\n'
            f'{summary}\n\n'
            f'<i>📌 منبع: {source}</i>\n'
            f'<a href="{link}">🔗 مشاهده خبر</a>\n\n'
            f'{CHANNEL_USERNAME}'
        ).strip()

    async def _format_international_short(self, news):
        source = html.escape(news.get('source', ''))
        title = html.escape(news.get('title', ''))
        summary = html.escape(news.get('summary', ''))
        link = news.get('link', '')
        emoji = news.get('emoji', '🌍')
        short_summary = summary.split('.')[0] if summary else ''
        if len(short_summary) > 100:
            short_summary = short_summary[:97] + '...'
        header = '🔴 <b>🌐 خبر فوری بین‌الملل</b>\n\n' if news.get('is_breaking') else ''
        return (
            f'{header}{emoji} <b>{title}</b>\n\n'
            f'📰 {short_summary}\n\n'
            f'<i>🔗 منبع: {source}</i>\n'
            f'<a href="{link}">🔍 مشاهده جزئیات</a>\n\n'
            f'{CHANNEL_USERNAME}'
        ).strip()

    def _format_viral(self, news):
        source = html.escape(news.get('source', ''))
        title = html.escape(news.get('title', ''))
        summary = html.escape(news.get('summary', ''))
        link = news.get('link', '')
        emoji = news.get('emoji', '🔥')
        header = '🔴 <b>🔥🔥🔥 خبر وایرال - بازتاب گسترده</b>\n\n'
        return (
            f'{header}{emoji} <b>{title}</b>\n\n'
            f'{summary}\n\n'
            f'<i>📌 منبع: {source}</i>\n'
            f'<a href="{link}">🔗 مشاهده خبر</a>\n\n'
            f'{CHANNEL_USERNAME}'
        ).strip()

    def _reset_counters(self):
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_posts = 0
            self.daily_international_posts = 0
            self.last_reset_date = today
            self.source_stats = {}
        self._reset_hourly()

    async def _send_breaking(self, news):
        try:
            if news['link'] in self.sent_links:
                return False
            msg = await self._format(news)
            await self.bot.send_message(chat_id=CHANNEL_USERNAME, text=msg, parse_mode=ParseMode.HTML)
            self.sent_links.add(news['link'])
            self._mark_sent(news['title'])
            self.daily_posts += 1
            self.hourly_posts += 1
            self.total_breaking_posted += 1
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
            if news.get('is_international') or 'title_en' in news:
                self.log(f'🔥 ترجمه خبر وایرال خارجی...')
                t_title = await self._smart_translate(
                    news.get('title_en', news.get('title', '')),
                    max_words=TRANSLATION_TITLE_MAX_WORDS,
                    is_title=True
                )
                t_summary = await self._smart_translate(
                    news.get('summary_en', news.get('summary', '')),
                    max_words=TRANSLATION_SUMMARY_MAX_WORDS,
                    is_title=False
                )
                if not t_title:
                    return False
                if not t_summary:
                    t_summary = t_title
                is_brk = self._is_breaking_news(t_title, t_summary)
                cat, emoji = self._detect_category(t_title, t_summary)
                final_news = {
                    'title': t_title,
                    'summary': t_summary,
                    'link': news.get('link', ''),
                    'source': news.get('source', ''),
                    'image_url': news.get('image_url'),
                    'category': cat,
                    'emoji': '🔥' if not is_brk else '🚨',
                    'is_breaking': is_brk,
                    'is_viral': True,
                }
                if is_brk:
                    return await self._send_breaking(final_news)
                msg = self._format_viral(final_news)
            else:
                news['emoji'] = '🔥'
                news['is_viral'] = True
                msg = self._format_viral(news)

            if INCLUDE_IMAGES and news.get('image_url'):
                try:
                    await self.bot.send_photo(
                        chat_id=CHANNEL_USERNAME,
                        photo=news['image_url'],
                        caption=msg[:1024],
                        parse_mode=ParseMode.HTML
                    )
                except:
                    await self.bot.send_message(
                        chat_id=CHANNEL_USERNAME, text=msg, parse_mode=ParseMode.HTML
                    )
            else:
                await self.bot.send_message(
                    chat_id=CHANNEL_USERNAME, text=msg, parse_mode=ParseMode.HTML
                )
            self.sent_links.add(news.get('link', ''))
            self._mark_sent(news.get('title', news.get('title_en', '')))
            self.daily_posts += 1
            self.hourly_posts += 1
            self.log(f'🔥 VIRAL SENT: {news.get("title", news.get("title_en", ""))[:50]}...')
            return True
        except Exception as e:
            self.log(f'❌ خطای ارسال وایرال: {e}')
            return False

    async def _send_domestic_direct(self, news):
        self._reset_counters()
        if self.daily_posts >= DAILY_NEWS_LIMIT:
            return False
        try:
            if news['link'] in self.sent_links:
                return False
            msg = await self._format(news)
            if INCLUDE_IMAGES and news.get('image_url'):
                try:
                    await self.bot.send_photo(
                        chat_id=CHANNEL_USERNAME,
                        photo=news['image_url'],
                        caption=msg[:1024],
                        parse_mode=ParseMode.HTML
                    )
                except:
                    await self.bot.send_message(
                        chat_id=CHANNEL_USERNAME, text=msg, parse_mode=ParseMode.HTML
                    )
            elif INCLUDE_VIDEOS and news.get('video_url'):
                try:
                    await self.bot.send_video(
                        chat_id=CHANNEL_USERNAME,
                        video=news['video_url'],
                        caption=msg[:1024],
                        parse_mode=ParseMode.HTML
                    )
                    self.total_videos_posted += 1
                except:
                    await self.bot.send_message(
                        chat_id=CHANNEL_USERNAME, text=msg, parse_mode=ParseMode.HTML
                    )
            else:
                await self.bot.send_message(
                    chat_id=CHANNEL_USERNAME, text=msg, parse_mode=ParseMode.HTML
                )
            self.sent_links.add(news['link'])
            self._mark_sent(news['title'])
            self.daily_posts += 1
            self.hourly_posts += 1
            self.log(f'✅ [{news["category"]}] {news["title"][:50]}...')
            return True
        except Exception as e:
            self.log(f'❌ post: {e}')
            return False

    async def _send_international_direct(self, news):
        self._reset_counters()
        if self.daily_international_posts >= DAILY_INTERNATIONAL_LIMIT:
            return False
        try:
            if news['link'] in self.sent_links:
                return False
            self.log(f'🌍 ترجمه خبر بین‌المللی...')
            t_title = await self._smart_translate(
                news['title_en'],
                max_words=TRANSLATION_TITLE_MAX_WORDS,
                is_title=True
            )
            t_summary = await self._smart_translate(
                news['summary_en'],
                max_words=TRANSLATION_SUMMARY_MAX_WORDS,
                is_title=False
            )
            if not t_title:
                self.log('❌ ترجمه عنوان ناموفق')
                return False
            if not t_summary:
                t_summary = t_title
            is_brk = news.get('is_breaking') or self._is_breaking_news(t_title, t_summary)
            cat, emoji = self._detect_category(t_title, t_summary)
            final_news = {
                'title': t_title,
                'summary': t_summary,
                'link': news['link'],
                'source': news['source'],
                'image_url': news.get('image_url'),
                'category': cat,
                'emoji': '🚨' if is_brk else emoji,
                'is_breaking': is_brk,
            }
            if is_brk:
                return await self._send_breaking(final_news)
            msg = await self._format_international_short(final_news)
            if INCLUDE_IMAGES and final_news.get('image_url'):
                try:
                    await self.bot.send_photo(
                        chat_id=CHANNEL_USERNAME,
                        photo=final_news['image_url'],
                        caption=msg[:1024],
                        parse_mode=ParseMode.HTML
                    )
                except:
                    await self.bot.send_message(
                        chat_id=CHANNEL_USERNAME, text=msg, parse_mode=ParseMode.HTML
                    )
            else:
                await self.bot.send_message(
                    chat_id=CHANNEL_USERNAME, text=msg, parse_mode=ParseMode.HTML
                )
            self.sent_links.add(final_news['link'])
            self._mark_sent(final_news['title'])
            self.daily_international_posts += 1
            self.daily_posts += 1
            self.hourly_posts += 1
            self.log(f'✅ [🌍 {cat}] {t_title[:50]}...')
            return True
        except Exception as e:
            self.log(f'❌ خطای ارسال بین‌المللی: {e}')
            return False

    # ==================== ✅ الگوریتم 1: Smart Priority Loop ====================
    async def publish_loop_smart_priority(self):
        """✅ الگوریتم 1: Smart Priority (بدون تغییر)"""
        self.log('🔄 🧠 SMART PRIORITY LOOP STARTED\n')
        while self.is_running:
            # ✅ بررسی تغییر الگوریتم
            if self.current_algorithm != ALGORITHM_SMART_PRIORITY:
                self.log(f'🔄 Switching to: {self.get_algorithm_name()}')
                return

            if self.news_pool.has_breaking():
                brk = self.news_pool.get_next_breaking()
                self.log('\n🚨🚨🚨 BREAKING NEWS! 🚨🚨🚨')
                await self._send_breaking(brk)
                await asyncio.sleep(5)
                continue
            now = datetime.now()
            if self.last_fetch_time is None or \
               (now - self.last_fetch_time).total_seconds() >= self.fetch_interval:
                self.cycle_count += 1
                self.log(f'\n⏰ FETCH TIME! Cycle #{self.cycle_count}')
                await self.fetch_all_news()
                self.next_fetch_time = now + timedelta(seconds=self.fetch_interval)
            if self.news_pool.size() == 0:
                rem = self._secs_to_fetch()
                self.log(f'💤 Pool empty | next fetch: {rem//60}m {rem%60:02d}s')
                await asyncio.sleep(30)
                continue
            news, news_type = self.news_pool.get_next_by_cycle()
            if news is None:
                await asyncio.sleep(10)
                continue
            sent = False
            if news_type == 'breaking':
                sent = await self._send_breaking(news)
            elif news_type == 'viral':
                sent = await self._send_viral(news)
            elif news_type == 'domestic':
                sent = await self._send_domestic_direct(news)
            elif news_type == 'international':
                sent = await self._send_international_direct(news)
            if not sent:
                continue
            delay = random.randint(MIN_POST_DELAY, MAX_POST_DELAY)
            self.log(f'⏸️ Next post in {delay//60}m {delay%60}s...')
            for _ in range(delay):
                if not self.is_running:
                    return
                if self.current_algorithm != ALGORITHM_SMART_PRIORITY:
                    return
                if self.news_pool.has_breaking():
                    self.log('🚨 Breaking interrupts!')
                    break
                await asyncio.sleep(1)

    # ==================== ✅ الگوریتم 2: Source Rotation Loop ====================
    async def publish_loop_source_rotation(self):
        """✅ الگوریتم 2: Source Rotation (چرخش منبع)
        
        ساختار بهینه:
        - حلقه روی SOURCE_ROTATION_CYCLE
        - اگر خبری از منبع نبود: step += 2 (رد کردن مرحله انتظار)
        - اگر خبری بود: step += 1 (حرکت به مرحله انتظار)
        - در پایان چرخه: بازگشت به مرحله 0
        """
        self.log('🔄 🔁 SOURCE ROTATION LOOP STARTED\n')
        self.log(f'📋 Cycle length: {self.rotation_cycle_length} steps')
        
        while self.is_running:
            # ✅ بررسی تغییر الگوریتم
            if self.current_algorithm != ALGORITHM_SOURCE_ROTATION:
                self.log(f'🔄 Switching to: {self.get_algorithm_name()}')
                return

            # ✅ Breaking News همیشه اولویت دارد
            if self.news_pool.has_breaking():
                brk = self.news_pool.get_next_breaking()
                self.log('\n🚨🚨🚨 BREAKING NEWS! 🚨🚨🚨')
                await self._send_breaking(brk)
                await asyncio.sleep(5)
                continue

            # ✅ زمان Fetch
            now = datetime.now()
            if self.last_fetch_time is None or \
               (now - self.last_fetch_time).total_seconds() >= self.fetch_interval:
                self.cycle_count += 1
                self.log(f'\n⏰ FETCH TIME! Cycle #{self.cycle_count}')
                await self.fetch_all_news()
                self.next_fetch_time = now + timedelta(seconds=self.fetch_interval)

            # ✅ بررسی خالی بودن مخزن
            if self.news_pool.size() == 0:
                rem = self._secs_to_fetch()
                self.log(f'💤 Pool empty | next fetch: {rem//60}m {rem%60:02d}s')
                await asyncio.sleep(30)
                continue

            # ✅ ✅ ✅ منطق اصلی الگوریتم 2
            step_type, source_name, wait_range = SOURCE_ROTATION_CYCLE[self.rotation_step]
            step_number = self.rotation_step + 1  # شماره 1-based برای نمایش

            if step_type == 'publish':
                # ✅ مرحله انتشار خبر
                self.log(f'\n📍 Step {step_number}/{self.rotation_cycle_length}: Publishing from [{source_name}]')
                
                # ✅ دریافت خبر از منبع مشخص
                news, news_type = self.news_pool.get_next_from_source(source_name)
                
                if news is None:
                    # ❌ خبری از این منبع نیست → +2 (رد کردن انتظار)
                    self.log(f'⚠️ No news from [{source_name}] → Skip to step {step_number + 2}')
                    self.rotation_step = (self.rotation_step + 2) % self.rotation_cycle_length
                    await asyncio.sleep(1)
                    continue
                
                # ✅ بررسی تکراری نبودن (اضافه برای اطمینان)
                title_to_check = news.get('title') or news.get('title_en', '')
                if self._is_duplicate(title_to_check):
                    self.log(f'🔄 Duplicate news from [{source_name}] → Skip')
                    self.rotation_step = (self.rotation_step + 2) % self.rotation_cycle_length
                    await asyncio.sleep(1)
                    continue
                
                # ✅ ارسال خبر
                sent = False
                if news_type == 'domestic':
                    sent = await self._send_domestic_direct(news)
                elif news_type == 'international':
                    sent = await self._send_international_direct(news)
                
                if sent:
                    self.log(f'✅ Step {step_number}: Published from [{source_name}]')
                    # ✅ خبر با موفقیت ارسال شد → +1 (حرکت به مرحله انتظار)
                    self.rotation_step = (self.rotation_step + 1) % self.rotation_cycle_length
                else:
                    # ❌ ارسال ناموفق → +2 (رد کردن انتظار)
                    self.log(f'❌ Step {step_number}: Failed to send from [{source_name}] → Skip')
                    self.rotation_step = (self.rotation_step + 2) % self.rotation_cycle_length
                
                await asyncio.sleep(2)
                
            elif step_type == 'wait':
                # ✅ مرحله انتظار
                min_wait, max_wait = wait_range
                wait_seconds = random.randint(min_wait, max_wait)
                
                self.log(f'\n⏳ Step {step_number}/{self.rotation_cycle_length}: Waiting {wait_seconds}s ({wait_seconds//60}m {wait_seconds%60}s)')
                
                # ✅ انتظار با قابلیت قطع شدن
                for _ in range(wait_seconds):
                    if not self.is_running:
                        return
                    if self.current_algorithm != ALGORITHM_SOURCE_ROTATION:
                        return
                    if self.news_pool.has_breaking():
                        self.log('🚨 Breaking interrupts wait!')
                        break
                    await asyncio.sleep(1)
                
                # ✅ پس از انتظار → +1 (حرکت به مرحله انتشار بعدی)
                self.rotation_step = (self.rotation_step + 1) % self.rotation_cycle_length

    def _secs_to_fetch(self):
        if not self.next_fetch_time:
            return 0
        return max(0, int((self.next_fetch_time - datetime.now()).total_seconds()))

    # ==================== ✅ اجرای اصلی ====================
    async def run(self):
        self.log('=' * 70)
        self.log('🤖 Smart News Bot - Dual Algorithm System')
        self.log('=' * 70)
        try:
            info = await self.bot.get_me()
            self.log(f'✅ Bot: @{info.username}')
            self.log(f'📢 Channel: {CHANNEL_USERNAME}')
            self.log(f'⏱️ Interval: {self.fetch_interval//60}m')
            self.log(f'⏸️ Post delay: {MIN_POST_DELAY}-{MAX_POST_DELAY}s')
            self.log(f'🌍 Translation: Google Translate + News Style')
            self.log(f'🔥 Viral Detection: Active')
            self.log(f'🧠 Algorithm 1: Smart Priority (20-Stage)')
            self.log(f'🔁 Algorithm 2: Source Rotation ({self.rotation_cycle_length} steps)')
            self.log(f'🎯 Active Algorithm: {self.get_algorithm_name()}')
            self.log('=' * 70 + '\n')
        except Exception as e:
            self.log(f'❌ Connection failed: {e}')
            return
        
        self.is_running = True
        self.cycle_count += 1
        await self.fetch_all_news(is_initial=True)
        self.next_fetch_time = datetime.now() + timedelta(seconds=self.fetch_interval)
        
        try:
            # ✅ حلقه اصلی - بر اساس الگوریتم انتخابی
            while self.is_running:
                if self.current_algorithm == ALGORITHM_SMART_PRIORITY:
                    await self.publish_loop_smart_priority()
                elif self.current_algorithm == ALGORITHM_SOURCE_ROTATION:
                    await self.publish_loop_source_rotation()
                else:
                    self.log(f'❌ Unknown algorithm: {self.current_algorithm}')
                    break
        except Exception as e:
            self.log(f'❌ Fatal: {e}')
            import traceback
            traceback.print_exc()
        
        self.log('🛑 Bot stopped')

    def stop(self):
        self.is_running = False
        self.log('🛑 Stop signal')


if __name__ == '__main__':
    bot = SmartNewsBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print('\nGoodbye!')