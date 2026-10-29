
import logging
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy import select

from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME
from app.database import SessionLocal
from app.models import User, Report
from app.telegram_link import connect_telegram, TelegramLink
from app.gemini_chat import ask_gemini


logger = logging.getLogger(__name__)

dp = Dispatcher()

CHANNEL_USERNAME = "@ai_yaratamiza"
CHANNEL_URL = "https://t.me/ai_yaratamiza"


def subscription_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Kanalga obuna bo‘lish",
                    url=CHANNEL_URL,
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Obunani tekshirish",
                    callback_data="check_subscription",
                )
            ],
        ]
    )


def welcome_text():
    username = (
        f"@{TELEGRAM_BOT_USERNAME}"
        if TELEGRAM_BOT_USERNAME
        else "TUMAN AI CONTROL"
    )

    return (
        "🤖 TUMAN AI CONTROL\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Maktablar uchun AI boshqaruv yordamchisi.\n\n"
        f"Bot: {username}\n\n"
        "Buyruqlar:\n"
        "/start — boshlash\n"
        "/help — yordam\n"
        "/link KOD — akkauntni bog‘lash\n"
        "/hisobotlar — o‘z hisobotlaringiz\n\n"
        "💬 Guruhda AI bilan suhbatlashish uchun "
        "botni @username orqali chaqiring yoki "
        "uning xabariga javob yozing.\n\n"
        "🔐 Shaxsiy ma’lumotlar uchun avval "
        "platformadagi akkauntingizni bog‘lang."
    )


async def is_subscribed(bot: Bot, telegram_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=telegram_id,
        )

        if member.status in ("creator", "administrator", "member"):
            return True

        if member.status == "restricted":
            return bool(member.is_member)

        return False

    except Exception:
        logger.exception(
            "Kanal obunasini tekshirishda xatolik: telegram_id=%s",
            telegram_id,
        )
        return False


async def require_subscription(message: Message) -> bool:
    if not message.from_user:
        return False

    if await is_subscribed(message.bot, message.from_user.id):
        return True

    await message.answer(
        "🔒 Botdan foydalanish uchun avval kanalimizga obuna bo‘ling.\n\n"
        "1. Kanalga obuna bo‘ling.\n"
        "2. «Obunani tekshirish» tugmasini bosing.",
        reply_markup=subscription_keyboard(),
    )
    return False


@dp.callback_query(F.data == "check_subscription")
async def check_subscription_handler(callback: CallbackQuery):
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    subscribed = await is_subscribed(
        callback.bot,
        callback.from_user.id,
    )

    if not subscribed:
        await callback.answer(
            "Avval @ai_yaratamiza kanaliga obuna bo‘ling.",
            show_alert=True,
        )
        return

    await callback.answer("Obuna tasdiqlandi!")

    try:
        await callback.message.edit_text(
            "✅ Obuna tasdiqlandi!\n\n"
            "Endi MAKTAB AI CONTROL botidan foydalanishingiz mumkin.\n\n"
            "Boshlash uchun /start buyrug‘ini yuboring."
        )
    except Exception:
        logger.exception("Obuna tasdiqlangan xabarni yangilashda xatolik")


@dp.message(Command("start"))
async def start_handler(message: Message):
    if not await require_subscription(message):
        return

    await message.answer(welcome_text())


@dp.message(Command("help"))
async def help_handler(message: Message):
    if not await require_subscription(message):
        return

    await message.answer(
        "📘 YORDAM\n\n"
        "1. TUMAN AI CONTROL saytiga kiring.\n"
        "2. Akkauntni bog‘lash kodini oling.\n"
        "3. Botga /link KOD yuboring.\n"
        "4. /hisobotlar orqali hisobotlaringizni ko‘ring.\n\n"
        "Guruhda botni @username orqali chaqiring "
        "yoki uning xabariga javob yozing.\n\n"
        "Kod 10 daqiqada eskiradi va bir marta ishlatiladi."
    )


@dp.message(Command("link"))
async def link_handler(message: Message, command: CommandObject):
    if not await require_subscription(message):
        return

    if not message.from_user:
        await message.answer(
            "Telegram foydalanuvchisini aniqlab bo‘lmadi."
        )
        return

    code = (command.args or "").strip()

    if not code:
        await message.answer(
            "🔗 Akkauntni bog‘lash uchun:\n"
            "/link KOD\n\n"
            "KOD o‘rniga saytdan olgan kodingizni yozing."
        )
        return

    if len(code) > 32:
        await message.answer("❌ Kod formati noto‘g‘ri.")
        return

    db = SessionLocal()

    try:
        user_id = connect_telegram(
            db=db,
            telegram_id=message.from_user.id,
            code=code,
        )

        user = db.get(User, user_id)

        if user is None or not user.is_active:
            await message.answer(
                "❌ Akkaunt faol emas. "
                "Platforma administratoriga murojaat qiling."
            )
            return

        await message.answer(
            "✅ Telegram akkauntingiz muvaffaqiyatli bog‘landi!\n\n"
            f"👤 Foydalanuvchi: {user.full_name}\n"
            f"🛡 Rol: {user.role}\n\n"
            "Endi /hisobotlar buyrug‘idan foydalanishingiz mumkin."
        )

    except ValueError as exc:
        db.rollback()
        await message.answer(f"❌ {exc}")

    except Exception:
        db.rollback()
        logger.exception("Telegram akkauntini bog‘lashda xatolik")
        await message.answer(
            "⚠️ Xatolik yuz berdi. Birozdan keyin qayta urinib ko‘ring."
        )

    finally:
        db.close()


@dp.message(Command("hisobotlar"))
async def reports_handler(message: Message):
    if not await require_subscription(message):
        return

    if not message.from_user:
        return

    db = SessionLocal()

    try:
        link = db.scalar(
            select(TelegramLink).where(
                TelegramLink.telegram_id == message.from_user.id
            )
        )

        if link is None:
            await message.answer(
                "🔐 Akkauntingiz hali bog‘lanmagan.\n"
                "Saytdan kod oling va /link KOD yuboring."
            )
            return

        user = db.get(User, link.user_id)

        if user is None or not user.is_active:
            await message.answer("❌ Akkauntingiz faol emas.")
            return

        query = select(Report).order_by(
            Report.created_at.desc()
        ).limit(10)

        # Maktab koordinatori faqat o‘z maktabi hisobotlarini ko‘radi.
        if user.role == "school_coordinator":
            if not user.school_id:
                await message.answer(
                    "⚠️ Akkauntingizga maktab biriktirilmagan."
                )
                return

            query = query.where(
                Report.school_id == user.school_id
            )

        reports = db.scalars(query).all()

        if not reports:
            await message.answer("📭 Hozircha hisobotlar topilmadi.")
            return

        lines = [
            "📊 SO‘NGGI HISOBOTLAR",
            "━━━━━━━━━━━━━━━━━━",
        ]

        for report in reports:
            title = report.title or "Nomsiz hisobot"
            period = report.period or "Davr ko‘rsatilmagan"
            status = report.status or "Noma’lum"

            lines.append(
                f"\n📄 {title}\n"
                f"📅 Davr: {period}\n"
                f"📌 Holat: {status}"
            )

        await message.answer("\n".join(lines)[:4000])

    except Exception:
        logger.exception("Hisobotlarni olishda xatolik")
        await message.answer(
            "⚠️ Hisobotlarni olishda xatolik yuz berdi."
        )

    finally:
        db.close()


@dp.message(F.text)
async def group_ai_handler(message: Message):
    # Faqat guruh va superguruhda ishlaydi.
    if message.chat.type not in ("group", "supergroup"):
        return

    if not message.from_user or message.from_user.is_bot:
        return

    text = (message.text or "").strip()

    # Buyruqlarni boshqa handlerlarga qoldiramiz.
    if text.startswith("/"):
        return

    bot_username = (TELEGRAM_BOT_USERNAME or "").lstrip("@")

    # Bot username'sini xabar matnidan aniqlash.
    mentioned = bool(
        bot_username
        and re.search(
            rf"(?<!\w)@{re.escape(bot_username)}(?!\w)",
            text,
            flags=re.IGNORECASE,
        )
    )

    # Telegramda botning xabariga javob berilganmi?
    replied_to_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == message.bot.id
    )

    if not mentioned and not replied_to_bot:
        return

    prompt = text

    if bot_username:
        prompt = re.sub(
            re.escape(f"@{bot_username}"),
            "",
            prompt,
            flags=re.IGNORECASE,
        ).strip()

    # Botning oldingi xabarini kontekst sifatida qo‘shamiz.
    if replied_to_bot and message.reply_to_message:
        original_text = (
            message.reply_to_message.text
            or message.reply_to_message.caption
            or ""
        ).strip()

        if original_text:
            prompt = (
                f"Botning oldingi xabari:\n{original_text}\n\n"
                f"Foydalanuvchining javobi:\n{prompt}"
            ).strip()

    if not prompt:
        await message.reply(
            "🤖 Savolingni yoz, men yordam beraman!"
        )
        return

    status_message = await message.reply("⏳")

    try:
        answer = await ask_gemini(prompt)
        await status_message.edit_text(answer[:4000])

    except Exception:
        logger.exception("Guruhdagi Gemini suhbatida xatolik")
        await status_message.edit_text(
            "⚠️ Hozir javob bera olmadim. "
            "API kaliti, model nomi va internet ulanishini tekshiring."
        )


async def start_telegram_bot():
    if not TELEGRAM_BOT_TOKEN:
        logger.warning(
            "TELEGRAM_BOT_TOKEN sozlanmagan. Bot ishga tushmaydi."
        )
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    try:
        logger.info("TUMAN AI CONTROL Telegram bot ishga tushmoqda.")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(start_telegram_bot())
