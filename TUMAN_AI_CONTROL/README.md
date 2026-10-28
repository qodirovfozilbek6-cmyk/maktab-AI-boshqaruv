# MAKTAB AI CONTROL

Maktabdagi **Kelajak o'quvchilar kengashi** faoliyatini bitta platformada boshqarish tizimi
(Tuman AI Control loyihasi asosida). FastAPI + SQLAlchemy + Neon PostgreSQL, Python 3.11.

> **Holat:** loyiha tayyor deb e'lon qilinmaydi. "Test holati" va "Tugallanmagan ishlar" bo'limlarini o'qing.

---

## 1. Rollar va ruxsatlar

| Rol | Nima qila oladi |
|---|---|
| `admin` | Foydalanuvchi, rol, yo'nalish, audit, hamma ma'lumotni ko'rish va tekshirish |
| `director` | Hamma ma'lumotni ko'radi, hisobotlarni tekshiradi, topshiriq beradi |
| `kelajak_leader` | Yetti yo'nalishni muvofiqlashtiradi, hisobot tekshiradi, topshiriq beradi (faqat **bitta** faol lider bo'ladi) |
| `coordinator` | Faqat **o'z yo'nalishi** (`direction`): hisobot, loyiha, topshiriq yaratadi va ko'radi |
| `school_advisor` | Faqat **o'zi yaratgan** hisobot, loyiha va topshiriqlarni ko'radi |
| `district_coordinator`, `school_coordinator` | Eski (Tuman AI Control) rollari: mavjud foydalanuvchilar buzilmasligi uchun saqlangan |

**Maktab ID so'ralmaydi.** Tizim bitta maktab bilan ishlaydi: foydalanuvchi, hisobot, loyiha va topshiriq yaratishda maktab tanlanmaydi,
server birinchi faol maktabni avtomatik biriktiradi (maktab yozuvi umuman bo'lmasa, "Maktab" nomli bitta yozuv yaratiladi).
Bazadagi `school_id` ustuni mavjud ma'lumotlar va bog'lanishlar buzilmasligi uchun saqlangan, lekin panelda ko'rinmaydi.
(API `school_id` ni ixtiyoriy qabul qilishda davom etadi: eski integratsiyalar uchun.)

Qoidalar serverda tekshiriladi (`scope_query` va `role_guard`), faqat interfeysda emas:
- koordinator boshqa yo'nalish yoki boshqa maktab ma'lumotini ko'rmaydi (ko'rinmas topshiriq uchun 404 qaytadi);
- umumiy (yo'nalishsiz) topshiriq holatini faqat rahbariyat o'zgartiradi;
- admin API orqali yaratilmaydi va admin rolini PATCH orqali o'zgartirib bo'lmaydi;
- faqat admin foydalanuvchi yaratadi/tahrirlaydi.

**Yetti dastlabki yo'nalish** (kod: nom): `education` Ta'lim, `media` Media, `culture` Madaniyat,
`ecology` Ekologiya, `sport` Sport, `it_ai` IT va sun'iy intellekt, `social` Ijtimoiy tashabbuslar.
Nomlarini admin panelidan o'zgartirish mumkin (kodlar o'zgarmaydi).

## 2. Windows CMD: o'rnatish va ishga tushirish

```
cd /d D:\TUMAN_AI_CONTROL
py -3.11 -m pip install -r requirements.txt
```

`.env` faylini `.env.example` asosida to'ldiring (**haqiqiy qiymatlar faqat `.env` ichida**, uni hech kimga yubormang):
```
copy .env.example .env
```
(`.env` allaqachon bo'lsa, ustidan yozmang.) Majburiy: `DATABASE_URL`, `JWT_SECRET_KEY` (kamida 64 belgi).

Birinchi administrator (faqat bazada admin bo'lmasa):
```
py -3.11 create_admin.py
```

Ishga tushirish:
```
py -3.11 -m uvicorn app.main:app --reload
```
Brauzerda: `http://127.0.0.1:8000/login`. Kirgach rolingizga mos panel (`/panel`) ochiladi.
API hujjatlari: `/docs`. Eski admin sahifasi: `/admin`.

Lokal sinov uchun SQLite ham mumkin: `DATABASE_URL=sqlite:///./maktab.db`.

## 3. Ma'lumotlar bazasini xavfsiz migratsiya qilish

Migratsiya **faqat qo'shadi**: jadval o'chirmaydi, ma'lumot o'zgartirmaydi.
U `users`, `reports`, `projects`, `tasks` jadvallariga `direction` ustunini qo'shadi, `directions`
jadvalini yaratadi va jadval bo'sh bo'lsa 7 ta yo'nalishni kiritadi. Bir necha marta ishga tushirish xavfsiz.

1. **Zaxira:** Neon konsolida bazangizdan *branch* (nusxa) yarating.
2. Migratsiya:
   ```
   cd /d D:\TUMAN_AI_CONTROL
   py -3.11 -m scripts.migrate_step1
   ```
3. Natija: `ustun qo'shildi` / `yo'nalishlar qo'shildi` yoki "allaqachon yangi".

Ilova ishga tushganda ham shu migratsiya avtomatik bajariladi.
**Orqaga qaytish:** muammo bo'lsa, Neon'dagi zaxira branch'ga o'ting. Yangi ustunlar bo'sh qolsa ham eski kodga zarar bermaydi.

## 4. Testlar

```
cd /d D:\TUMAN_AI_CONTROL
cls
py -3.11 -m pytest tests -v
```
Testlar xotiradagi/lokal **SQLite**'da ishlaydi va Neon'ga tegmaydi. Faylga ajratilishi:

| Fayl | Nimani tekshiradi |
|---|---|
| `test_step1_roles.py` | rollar, yo'nalishlar, bitta lider, admin himoyasi, migratsiya |
| `test_step2_scoping.py` | yo'nalish/maktab bo'yicha cheklov, topshiriq ruxsatlari, dashboard |
| `test_ai_center_logic.py` | AI tahlil mantiqi (bazasiz) |
| `test_step3_ai.py` | AI endpointlari va ruxsat doirasi |
| `test_ratelimit_logic.py` | login cheklovi mantiqi |
| `test_step4_security_ui.py` | sahifalar, xavfsizlik sarlavhalari, login bloki |
| `test_step5_single_school.py` | maktab ID avtomatik biriktirilishi |
| `ui/panel_smoke.js` (ixtiyoriy, Node.js kerak) | panel JS ni soxta DOM'da tekshiradi: `py -3.11 tests/ui/make_data.py`, so'ng `node tests/ui/panel_smoke.js` |

### Test holati (rost hisobot)
- **Foydalanuvchi mashinasida o'tgan:** 1- va 2-bosqich, jami 24 ta test (8 + 16).
- **Yaratuvchi muhitida ishga tushirilgan:** `test_ai_center_logic.py` (11 ta), `test_ratelimit_logic.py` (5 ta), `ui/panel_smoke.js` (104 tekshiruv, soxta DOM).
- **Hali hech kim ishga tushirmagan:** `test_step3_ai.py` (9 ta), `test_step4_security_ui.py` (5 ta), `test_step5_single_school.py` (5 ta) va panelning **haqiqiy brauzerdagi** ko'rinishi. Ularni o'zingiz ishga tushirib, natijani tekshiring.

## 5. Yo'nalishlarni sozlash va foydalanuvchilarni tayinlash

1. Admin sifatida `/login` orqali kiring, `/panel` ochiladi.
2. **Yo'nalishlar** bo'limi: rasmiy nomlarni kiriting, tartib raqami va faollikni belgilang.
   Faol koordinatori bor yo'nalishni o'chirib bo'lmaydi.
3. **Foydalanuvchilar → Yangi foydalanuvchi:**
   - Kelajak lideri: rol `Kelajak lideri` (yo'nalish kerak emas, faqat bitta faol);
   - Har bir koordinator: rol `Koordinator`, **yo'nalish** tanlanadi (7 ta yo'nalish uchun 7 ta foydalanuvchi, takroriy rol shart emas);
   - Maslahatchi: rol `Maktab maslahatchisi` (yo'nalish kerak emas);
   - Direktor: rol `Maktab direktori`.
   Parol kamida 12 belgi.
4. Maktab tanlash shart emas. Bazada bir nechta faol maktab bo'lsa, eng kichik ID'lisi ishlatiladi (qolganlarini eski `/admin` sahifasidan faolsizlantirish mumkin).
5. Foydalanuvchini faolsizlantirish yoki rolini almashtirish: **Tahrirlash** tugmasi.

## 6. AI markazi

Tashqi AI va API kalit **talab qilinmaydi**. Tahlil tizimdagi ma'lumotlar bo'yicha statistik hisob-kitob va qoidalarga asoslanadi.
- `GET /ai/overview?window_days=30`: yo'nalishlar kesimida hisobot/loyiha/topshiriq, kechikishlar, bajarilish foizi, topilmalar va tavsiyalar;
- `GET /ai/report?period=week|month`: haftalik yoki oylik matnli hisobot (audit logga yoziladi);
- `POST /ai/analyze`: kiritilgan matnni mahalliy tahlil qilish (eski funksiya saqlangan).

AI faqat **tavsiya** beradi: alohida odamlar haqida xulosa chiqarmaydi va intizomiy qaror qabul qilmaydi.
Har foydalanuvchi faqat o'z ruxsat doirasidagi ma'lumot bo'yicha tahlil oladi.

## 7. Render'ga joylashtirish

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health`
- **Python versiyasi:** repoda `.python-version` (`3.11`) bor. Render yangi xizmatlar uchun odatiy versiyani o'zi tanlaydi, shuning uchun uni aniq belgilash kerak
  (muqobil: `PYTHON_VERSION` muhit o'zgaruvchisiga to'liq versiya, masalan `3.11.9`).
- **Environment** (Render panelida, kodga yozmang): `DATABASE_URL` (Neon, `postgresql+psycopg://...`), `JWT_SECRET_KEY` (64+ belgi),
  `APP_ENV=production`, `JWT_EXPIRE_MINUTES`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`.
- `render.yaml` tayyor (Blueprint, ixtiyoriy). Maxfiy qiymatlar unda yo'q.
- Birinchi admin: bazangizda allaqachon bo'lsa, qo'shimcha amal kerak emas. Aks holda `create_admin.py` ni lokal kompyuterdan, `.env` Neon'ga qaratilgan holda ishga tushiring.

**Bepul tarif cheklovlari (joylashtirishdan oldin tekshiring, ular o'zgarishi mumkin):**
- Render Free: 15 daqiqa trafik bo'lmasa xizmat uxlaydi, qayta uyg'onishi taxminan 1 daqiqa; oyiga 750 bepul soat; fayl tizimi vaqtinchalik (SQLite Render'da saqlanmaydi, Neon ishlating).
- Telegram bot shu xizmat ichida ishlaydi, shuning uchun xizmat uxlaganda bot ham to'xtaydi. Doim ishlashi kerak bo'lsa, pulli tarif yoki alohida xizmat kerak.
- Neon Free: har loyihaga 0.5 GB xotira, oyiga 100 CU-soat hisoblash; 5 daqiqa faolsizlikdan keyin hisoblash to'xtaydi (birinchi so'rov biroz sekin bo'lishi mumkin).
- Rasmiy sahifalar: `render.com/docs/free`, `neon.com/pricing`.

## 8. O'zgartirilgan fayllar

| Fayl | Vazifasi |
|---|---|
| `app/permissions.py` | yangi rollar va rol guruhlari (`MANAGER_ROLES`, `SCHOOL_BOUND_ROLES`) |
| `app/models.py` | `Direction` jadvali, `direction` ustuni (users, reports, projects, tasks) |
| `app/schemas.py` | yangi rollar, `direction` maydonlari, `DirectionOut/Update` |
| `app/directions.py` (yangi) | 7 yo'nalish, xavfsiz qo'shuvchi migratsiya |
| `app/main.py` | rol va yo'nalish qoidalari, `scope_query`, yo'nalish endpointlari, AI endpointlari, login limiti, xavfsizlik sarlavhalari, `/panel` |
| `app/ai_center.py` (yangi) | mahalliy statistik AI tahlili va davriy hisobot |
| `app/ratelimit.py` (yangi) | login urinishlarini cheklash |
| `app/config.py`, `app/database.py` | SQLite qo'llab-quvvatlash, nom |
| `scripts/migrate_step1.py` (yangi) | migratsiya skripti |
| `app/static/panel.html`, `js/panel.js`, `css/maktab.css` (yangi) | rol bo'yicha panel va umumiy dizayn (qora-ko'k, oltin, neon ko'k) |
| `app/static/login.html` | yangi kirish sahifasi, barcha rollar uchun |
| `app/static/index.html`, `admin.html` | nom va matnlar yangilandi (`admin.html` mantig'i o'zgarmagan) |
| `tests/*` | yuqoridagi testlar |
| `.env.example`, `.python-version`, `render.yaml`, `.gitignore` | sozlamalar (maxfiy qiymatsiz) |

Mavjud API yo'llari saqlangan. Yangilari: `/directions`, `/admin/directions/{id}`, `/ai/overview`, `/ai/report`, `/panel`.
O'zgargan xatti-harakat: `PATCH /tasks/{id}` ko'rinmas topshiriq uchun endi 404 qaytaradi; hisobot, loyiha, topshiriq ro'yxatlari rol bo'yicha cheklanadi.

## 9. Xavfsizlik

**Bajarilgan:** server tomonida ruxsatlar; admin yaratish/oshirishni bloklash; bitta Kelajak lideri; Argon2 parol xeshi va 12 belgilik parol talabi (avvaldan bor); JWT kaliti 64+ belgi (avvaldan bor);
login urinishlari cheklovi (5 xato = 5 daqiqa blok, audit logga yoziladi); xavfsizlik sarlavhalari (`nosniff`, `X-Frame-Options`, `Referrer-Policy`);
frontendda `innerHTML` ishlatilmaydi; audit jurnali kengaytirildi; `.env` ZIPga kiritilmagan.

**Qolgan xavflar:**
- Token brauzerning `localStorage` ida saqlanadi: XSS bo'lsa o'g'irlanishi mumkin. Yaxshiroq yo'l: `HttpOnly` cookie.
- Content-Security-Policy yo'q (eski sahifalarda inline skriptlar bor).
- Login cheklovi xotirada: server qayta ishga tushsa nolga tushadi; bir nechta jarayonda umumiy emas; kimdir boshqaning loginini vaqtincha bloklab qo'yishi mumkin.
- Serverda tokenni bekor qilish (revoke) yo'q; 2 bosqichli tasdiqlash va parolni tiklash yo'q.
- Yuklangan ZIPdagi `.env` ichida haqiqiy kalitlar bor edi: fayl boshqalarga yuborilgan bo'lsa, JWT kaliti, bot tokeni va Neon parolini almashtiring.
- Zaxira nusxa avtomatik emas (Neon branch qo'lda).

## 10. Tugallanmagan ishlar

- Yangi panelda parolni almashtirish, topshiriq/loyiha/hisobotni tahrirlash va o'chirish yo'q.
- Hisobotga fayl yuklash yo'q (faqat havola).
- Ro'yxatlarda sahifalash (pagination) yo'q.
- Tashqi AI modeli ulanmagan (ixtiyoriy keyingi bosqich).
- Telegram bot kodi bu ishda o'zgartirilmagan va rollarga moslab tekshirilmagan.
- `app/services.py` ishlatilmayotgan ko'rinadi (o'chirilmagan).
- Panel faqat soxta DOM'da sinalgan; haqiqiy brauzer va telefonda ko'rib chiqish kerak.
