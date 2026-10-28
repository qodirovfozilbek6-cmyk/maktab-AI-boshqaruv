
import re

from app.schemas import AIAnalysisResponse


POSITIVE_TERMS = (
    "amalga oshirildi",
    "muvaffaqiyat",
    "natija",
    "yaratildi",
    "joriy etildi",
    "o'rgatildi",
    "o'tkazildi",
    "qatnashdi",
    "ishlab chiqildi",
    "yaxshilandi",
)

RISK_TERMS = (
    "muammo",
    "bajarilmadi",
    "kechikdi",
    "yetishmaydi",
    "mavjud emas",
    "qiyinchilik",
    "nosoz",
    "reja bajarilmadi",
)

EVIDENCE_TERMS = (
    "https://",
    "http://",
    "foto",
    "rasm",
    "dalil",
    "ilova",
    "havola",
    "sertifikat",
    "bayonnoma",
)


def split_sentences(text: str) -> list[str]:
    """Matnni sodda usulda gaplarga ajratadi."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = text.casefold()
    return any(term.casefold() in normalized for term in terms)


def analyze_report(
    text: str,
    context: str = "report",
) -> AIAnalysisResponse:
    """
    Mahalliy, qoidaga asoslangan dastlabki tahlil.

    Bu funksiya til modeli emas. Natijalar avtomatik rasmiy baho
    yoki maktab reytingi sifatida ishlatilmasligi kerak.
    """
    clean_text = " ".join(text.split())
    sentences = split_sentences(text)

    strengths: list[str] = []
    risks: list[str] = []
    recommendations: list[str] = []
    limitations: list[str] = []

    if not clean_text:
        return AIAnalysisResponse(
            summary="Tahlil uchun matn kiritilmagan.",
            strengths=[],
            risks=["Tahlil qilinadigan ma'lumot mavjud emas."],
            recommendations=[
                "Hisobotning maqsadi, bajarilgan ishlar va natijalarni kiriting."
            ],
            limitations=["Bo'sh matn sababli tahlil bajarilmadi."],
        )

    positive_sentences = [
        sentence
        for sentence in sentences
        if contains_any(sentence, POSITIVE_TERMS)
    ]

    risk_sentences = [
        sentence
        for sentence in sentences
        if contains_any(sentence, RISK_TERMS)
    ]

    evidence_found = contains_any(clean_text, EVIDENCE_TERMS)

    if positive_sentences:
        strengths.extend(positive_sentences[:5])
    else:
        strengths.append(
            "Matnda aniq yutuqlarni avtomatik ajratish uchun "
            "yetarli kalit iboralar topilmadi."
        )
        recommendations.append(
            "Bajarilgan ishlarni aniq natijalar va raqamlar bilan yozing."
        )

    if risk_sentences:
        risks.extend(risk_sentences[:5])
    else:
        risks.append(
            "Qoidaga asoslangan tekshiruvda muammolarni bildiruvchi "
            "iboralar topilmadi. Bu muammo yo'q degani emas."
        )

    if not evidence_found:
        risks.append("Matnda dalil yoki tasdiqlovchi material aniq ko'rsatilmagan.")
        recommendations.append(
            "Hisobotga tekshiriladigan foto, hujjat yoki tegishli havolalarni qo'shing."
        )

    if len(clean_text) < 150:
        risks.append("Hisobot matni qisqa; xulosa uchun ma'lumot cheklangan.")
        recommendations.append(
            "Maqsad, bajarilgan ishlar, ishtirokchilar va natijalarni batafsil bayon qiling."
        )

    if not re.search(r"\d", clean_text):
        recommendations.append(
            "Imkon bo'lsa, o'lchanadigan ko'rsatkichlarni kiriting: "
            "ishtirokchilar soni, loyihalar, mashg'ulotlar yoki natijalar."
        )

    if not any(word in clean_text.casefold() for word in (
        "reja", "maqsad", "keyingi", "kelgusida"
    )):
        recommendations.append(
            "Keyingi davr uchun aniq maqsad va bajarish muddatini belgilang."
        )

    if context not in {"report", "project", "task"}:
        limitations.append(
            "Noma'lum tahlil konteksti berildi; umumiy tekshiruv qo'llanildi."
        )

    limitations.extend([
        "Bu dastlabki mahalliy tahlil bo'lib, haqiqiy til modelidan foydalanmaydi.",
        "Kalit so'zlar asosidagi aniqlash xato qilishi mumkin; natijalarni inson tekshirishi kerak.",
        "Rasmiy reyting yoki intizomiy qaror faqat shu tahlilga asoslanmasligi kerak.",
    ])

    if risk_sentences:
        summary = (
            f"Matnda {len(sentences)} ta gap ajratildi. "
            f"Muammoga oid {len(risk_sentences)} ta ibora topildi. "
            "Aniqlangan holatlarni dalillar bilan tekshirish tavsiya etiladi."
        )
    else:
        summary = (
            f"Matnda {len(sentences)} ta gap ajratildi. "
            "Dastlabki tekshiruv yakunlandi; natijalar inson tomonidan "
            "tasdiqlanishi kerak."
        )

    if not recommendations:
        recommendations.append(
            "Natijalarni tasdiqlovchi dalillarni tekshiring va keyingi ish rejasini belgilang."
        )

    return AIAnalysisResponse(
        summary=summary,
        strengths=strengths,
        risks=risks,
        recommendations=recommendations[:8],
        limitations=limitations,
    )
