import secrets
# config.py
BOT_TOKEN = "8570392401:AAFfowtqYzjxz-PCC-0IVJPx1xl5V03LCXk"
ADMIN_ID = 8479289622
# Данные для генерации ссылки Reality (VLESS)
SERVER_IP = "31.130.131.214"
SERVER_PORT = 2053
PBK = "P2Q_Uq49DV8iEiwiRxNe0UYKCXL--sp-nU0pihntn30"
FP = "chrome"
SNI = "www.bing.com,bing.com"
SID = "9864"  # Если в панели настроен другой ShortID, замените
# Настройки доступа к 3X-UI
PANEL_URL = "https://31.130.131.214:55694"
PANEL_PATH = "xqAY0T10JV0Nut7YIp"
PANEL_USER = "magam"  # Введите ваш логин от панели
PANEL_PASS = "maga2192242"  # Введите ваш пароль от панели
INBOUND_ID = 6  # ID вашего Reality-подключения в списке Inbounds
SUB_PORT = 2096
SUB_PATH = "/sub/"   # обязательно с / в конце
SUB_BASE_URL = "https://31.130.131.214:2096"
# Реквизиты
PAY_PHONE = "79283376737"
PAY_BANK = "Озон"
PRICES = {
    'week':   {'name': '1 неделя',   'price': 50,   'days': 7},      # 50₽ — дешёвый вход для новых
    'month':  {'name': '1 месяц',    'price': 150,  'days': 30},     # 150₽ — основной тариф
    '3month': {'name': '3 месяца',   'price': 350,  'days': 90},     # ≈116₽/мес — скидка ~23%
    '6month': {'name': '6 месяцев',  'price': 600,  'days': 180},    # 100₽/мес — скидка 33%
    'year':   {'name': '12 месяцев', 'price': 1000, 'days': 365}     # ≈83₽/мес — скидка 45%, супервыгода
}

# Emoji для оформления - ОБНОВЛЕННЫЙ СЛОВАРЬ
EMOJI = {
    "home": "🏠",
    "back": "↩️",
    "key": "🔑",
    "buy": "💳",
    "support": "🆘",
    "time": "⏰",
    "link": "🔗",
    "copy": "📋",
    "check": "✅",
    "cross": "❌",
    "info": "ℹ️",
    "rocket": "🚀",
    "crown": "👑",
    "shield": "🛡️",
    "wifi": "📡",
    "lock": "🔒",
    "unlock": "🔓",
    "star": "⭐",
    "fire": "🔥",
    "money": "💰",
    "card": "💎",
    "phone": "📱",
    "bank": "🏦",
    "download": "📥",
    "upload": "📤",
    "speed": "⚡",
    "global": "🌐",
    "settings": "⚙️",
    "friends": "👥",
    "gift": "🎁",
    "invite": "📨",
    "stats": "📊",
    "trophy": "🏆",
    "medal": "🏅",
    "party": "🎉",
    "diamond": "💎",
    "traffic": "📈",
    "chart": "📉",
    "battery": "🔋",
    # ДОБАВЛЕНЫ ПРОПУЩЕННЫЕ ЭМОДЗИ:
    "calendar": "📅",  # ДОБАВЛЕНО
    "pro": "🚀",
    "vip": "👑",
    "flash": "⚡",
    "earth": "🌍",
    "cloud": "☁️",
    "security": "🛡️",
    "qrcode": "📱",
    "refresh": "🔄",
    "alert": "🚨"
}


HAPP_NAME = "MAGAMIX VPN 🇳🇱"
HAPP_LOGO = "https://cdn-icons-png.flaticon.com/512/3067/3067256.png"
SERVER_LOCATION = "Нидерланды 🇳🇱"
RENDER_URL = "https://magamix.onrender.com"
