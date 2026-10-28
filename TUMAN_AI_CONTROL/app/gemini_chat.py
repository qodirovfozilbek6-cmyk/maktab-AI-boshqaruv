
import asyncio
import logging
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from google import genai

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    force=True,
)

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# API mijozlari: kalitlar .env dan olinadi
groq_client = (
    AsyncOpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
        timeout=30.0,
        max_retries=0,
    )
    if GROQ_API_KEY
    else None
)

gemini_client = (
    genai.Client(api_key=GEMINI_API_KEY)
    if GEMINI_API_KEY
    else None
)

openrouter_client = (
    AsyncOpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        timeout=30.0,
        max_retries=0,
    )
    if OPENROUTER_API_KEY
    else None
)


async def ask_gemini(prompt: str) -> str:
    """Groq -> Gemini -> OpenRouter avtomatik fallback."""

    if not prompt or not prompt.strip():
        return "Savolingni yoz, jgar 🙂"

    prompt = prompt.strip()
    errors = []

    # 1. GROQ — asosiy va tezkor AI
    if groq_client:
        try:
            logger.info("🚀 GROQ so'rovi boshlandi")

            response = await groq_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Sen foydali, samimiy va aniq AI yordamchisan. "
                            "Foydalanuvchiga uning tilida javob ber."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1500,
            )

            answer = response.choices[0].message.content

            if answer and answer.strip():
                logger.info("✅ GROQ javob berdi")
                return answer.strip()

            raise RuntimeError("Groq bo'sh javob qaytardi")

        except Exception as exc:
            errors.append(f"Groq: {exc}")
            logger.exception("⚠️ GROQ ishlamadi, Gemini sinab ko'riladi")

    else:
        logger.warning("⏭️ GROQ_API_KEY yo'q — Groq o'tkazib yuborildi")

    # 2. GEMINI — birinchi zaxira
    if gemini_client:
        try:
            logger.info("🔀 FALLBACK: GEMINI")

            response = await asyncio.wait_for(
                gemini_client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                ),
                timeout=30.0,
            )

            answer = response.text

            if answer and answer.strip():
                logger.info("✅ GEMINI javob berdi")
                return answer.strip()

            raise RuntimeError("Gemini bo'sh javob qaytardi")

        except Exception as exc:
            errors.append(f"Gemini: {exc}")
            logger.exception(
                "⚠️ GEMINI ishlamadi, OpenRouter sinab ko'riladi"
            )

    else:
        logger.warning("⏭️ GEMINI_API_KEY yo'q — Gemini o'tkazib yuborildi")

    # 3. OPENROUTER — ikkinchi zaxira, bepul model marshrutizatori
    if openrouter_client:
        try:
            logger.info("🔀 FALLBACK: OPENROUTER")

            response = await openrouter_client.chat.completions.create(
                model="openrouter/free",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Sen foydali, samimiy va aniq AI yordamchisan. "
                            "Foydalanuvchiga uning tilida javob ber."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1500,
            )

            answer = response.choices[0].message.content

            if answer and answer.strip():
                logger.info(
                    "✅ OPENROUTER javob berdi. Model: %s",
                    response.model,
                )
                return answer.strip()

            raise RuntimeError("OpenRouter bo'sh javob qaytardi")

        except Exception as exc:
            errors.append(f"OpenRouter: {exc}")
            logger.exception("❌ OPENROUTER ham ishlamadi")

    else:
        logger.warning(
            "⏭️ OPENROUTER_API_KEY yo'q — OpenRouter o'tkazib yuborildi"
        )

    logger.error("❌ Barcha AI servislaridan javob olinmadi")

    # Haqiqiy xatolar CMD logida qoladi; guruhda esa qisqa xabar chiqadi.
    raise RuntimeError(
        "Barcha AI servislarida xatolik. "
        + " | ".join(errors)
    )
