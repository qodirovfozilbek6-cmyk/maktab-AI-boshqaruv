import re

# O'zbekcha matnlar uchun loyiha bo'ylab yagona milliy yozuv.
_ROOTS = (
    "o'","bo'","so'","to'","yo'","ko'","qo'","do'","mo'","g'",
    "yaxsh","yasha","ishla","ishonch","qish","kich","uch","kech",
    "mashq","mashina","tashkil","tashqi","boshqa","shart","shaxs",
    "shunday","shunch","ko'pchilik",
    "tosh", "farg", "qumqo", "samarqand", "buxoro", "nukus", "termiz", "surxon", "andij", "namang", "jizz", "qarshi", "urganch",
    "o'zbek", "o'zbekiston", "shahar", "shamol", "sharoit", "shakl", "shuning",
    "tanla", "havo", "sifat", "ob-havo", "asos", "model", "baho", "ko'r",
    "katalog", "yozuv", "mavjud", "ro'yxat", "rasmiy", "tasnif", "yakun",
    "solisht", "bosqich", "hudud", "ma'lumot", "olish", "tahlil", "boshl",
    "yukla", "prognoz", "hafta", "tarix", "iqlim", "ekolog", "tabiat",
    "kelajak", "asra", "resurs", "suv", "issiq", "gaz", "foydalanuvchi",
    "bosh", "kutubxona", "o'quv", "o'qit", "ta'lim", "qo'sh", "o'zg",
    "o'ch", "saqla", "tahrir", "qidir", "yordam", "sozlama", "hisobot",
    "topshiriq", "mavzu", "dars", "maktab", "kir", "chiq", "bajar",
    "yubor", "yakun", "natija", "bahola", "oila", "ota-ona", "loyiha",
    "yangi", "nom", "tavsif", "tasdiq", "rad", "moder", "hisob", "parol",
    "ism", "sessiya", "tizim", "faol", "manba", "vaqt", "o'lchov",
    "birlik", "ko'rsat", "joriy", "harorat", "namlik", "yog'in", "kun",
    "tanlang", "qaytish", "barcha", "modul", "tekshir", "xarita", "nuqta",
    "belgi", "koordinata", "hisoblan", "taxmin", "shaxsiy", "ovqat",
    "transport", "elektr", "aralash", "kamida", "muvaffaq", "moderatsiya",
    "navbat", "ruxsat", "talab", "ogohlantirish", "shaharlari", "yo'nalish",
    "farqi", "muddat", "statistik", "energiya", "tejamkor", "sug'or",
    "rejalashtirish", "muhim", "vosita", "ochiq", "ishonch", "yangilanish",
    "litsenziya", "hisobingiz", "kiring", "yarat", "etish", "aniq",
    "tushuntir", "savol", "javob", "misol", "yechim", "formula", "qonun",
    "reaksiya", "atom", "molekula", "hujayra", "organizm", "tarixiy",
    "sabab", "oqibat", "xulosa", "tavsiya", "ehtiyot", "cheklash",
    "foydalan", "kerak", "mumkin", "emas", "uchun", "bilan", "orqali",
    "haqida", "qanday", "nima", "nega", "qaysi", "birinchi", "ikkinchi",
    "keyingi", "oldingi", "yuqori", "past", "o'rtacha", "ko'proq",
    "kamroq", "bajarilgan", "bajarilmagan", "tekshiril", "aniqlan",
)

def _normalize(value: str) -> str:
    return value.casefold().replace("ʻ", "'").replace("ʼ", "'").replace("’", "'").replace("‘", "'").replace("`", "'")

def _convert_word(word: str) -> str:
    normalized = _normalize(word)
    if not any(normalized.startswith(root) for root in _ROOTS):
        return word
    return (word.replace("o'", "ö").replace("O'", "Ö")
                .replace("o’", "ö").replace("O’", "Ö")
                .replace("o‘", "ö").replace("O‘", "Ö")
                .replace("oʻ", "ö").replace("Oʻ", "Ö")
                .replace("g'", "ğ").replace("G'", "Ğ")
                .replace("g’", "ğ").replace("G’", "Ğ")
                .replace("g‘", "ğ").replace("G‘", "Ğ")
                .replace("gʻ", "ğ").replace("Gʻ", "Ğ")
                .replace("sh", "ş").replace("Sh", "Ş").replace("SH", "Ş")
                .replace("ch", "ç").replace("Ch", "Ç").replace("CH", "Ç"))

def to_national_uzbek(value: str) -> str:
    """Convert recognized Uzbek words while leaving other languages untouched."""
    if not isinstance(value, str) or not value:
        return value
    return re.sub(r"[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳʻʼ’‘'\u2018\u2019\u02BB\u02BC`-]+", lambda match: _convert_word(match.group(0)), value)
def to_national_data(value):
    """Recursively normalize user-facing text in API payloads."""
    if isinstance(value, str):
        return to_national_uzbek(value)
    if isinstance(value, list):
        return [to_national_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(to_national_data(item) for item in value)
    if isinstance(value, dict):
        return {key: to_national_data(item) for key, item in value.items()}
    return value
