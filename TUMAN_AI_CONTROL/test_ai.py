
import asyncio
from app.gemini_chat import ask_gemini


async def main():
    print("AI test boshlandi...\n")

    try:
        answer = await ask_gemini(
            "O'zbek tilida qisqa salom ber va qaysi AI ekaningni ayt."
        )
        print("\n✅ TEST MUVAFFAQIYATLI!")
        print("AI javobi:", answer)

    except Exception as exc:
        print("\n❌ TESTDA XATOLIK!")
        print("Xato turi:", type(exc).__name__)
        print("Xabar:", exc)


if __name__ == "__main__":
    asyncio.run(main())
