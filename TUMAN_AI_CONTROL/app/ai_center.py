"""AI markazi: yo'nalishlar bo'yicha mahalliy statistik tahlil.

Bu modul tashqi AI xizmatiga ulanmaydi va API kalit talab qilmaydi.
U faqat tizimdagi hisobot, loyiha va topshiriq ma'lumotlarini sanaydi hamda
qoidalar asosida tavsiyalar tayyorlaydi.

Muhim tamoyillar:
  * natijalar tavsiya xarakterida; inson tekshirishi kerak;
  * alohida odamlar haqida xulosa chiqarilmaydi (faqat yo'nalish darajasi);
  * intizomiy qaror qabul qilinmaydi.

Modul ataylab FastAPI va bazaga bog'lanmagan: u oddiy lug'atlar bilan ishlaydi,
shuning uchun osongina sinab ko'riladi.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

AI_MODE = "local"

AI_NOTE = (
    "Tashqi sun'iy intellekt ulanmagan, API kalit talab qilinmaydi. "
    "Tahlil tizimdagi ma'lumotlar asosidagi statistik hisob-kitoblarga "
    "tayanadi."
)

LIMITATIONS = [
    "Bu tahlil faqat tizimga kiritilgan ma'lumotlarga asoslangan statistik "
    "hisob-kitob va tavsiya xarakterida.",
    "Natijalarni inson tekshirishi kerak; ular alohida shaxslar haqida "
    "xulosa yoki intizomiy qaror uchun asos bo'lmaydi.",
    "Topshiriqlar holati joriy vaziyatni ko'rsatadi, tanlangan davrga "
    "bog'lanmagan.",
]

GENERAL_NAME = "Yo'nalishsiz (umumiy)"

# Bajarilish foizi ishonchli deb hisoblanishi uchun kamida shuncha topshiriq.
MIN_SAMPLE = 3

# Tekshirilmagan hisobot "kutilmoqda" deb sanalishi uchun kunlar soni.
REVIEW_WAIT_DAYS = 7

OPEN_EXCLUDED = ("completed", "cancelled")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _percent(part: int, total: int) -> int | None:
    if total <= 0:
        return None
    return round(part * 100 / total)


def _empty_bucket(code: str | None, name: str) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "reports_total": 0,
        "reports_recent": 0,
        "reports_awaiting_review": 0,
        "reports_stale_review": 0,
        "reports_needs_revision": 0,
        "projects_total": 0,
        "projects_recent": 0,
        "projects_in_progress": 0,
        "tasks_total": 0,
        "tasks_completed": 0,
        "tasks_cancelled": 0,
        "tasks_open": 0,
        "tasks_overdue": 0,
        "completion_rate": None,
        "completion_rate_reliable": False,
    }


def build_overview(
    directions: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    now: datetime | None = None,
    window_days: int = 30,
) -> dict[str, Any]:
    """Yo'nalishlar kesimida umumiy tahlil.

    directions: [{"code", "name"}]  (tahlilga kiradigan yo'nalishlar)
    reports:    [{"direction", "status", "created_at"}]
    projects:   [{"direction", "status", "created_at"}]
    tasks:      [{"id", "title", "direction", "status", "deadline"}]
    """
    now = _aware(now) or datetime.now(timezone.utc)
    since = now - timedelta(days=window_days)
    stale_before = now - timedelta(days=REVIEW_WAIT_DAYS)

    names: dict[str | None, str] = {
        d["code"]: d["name"] for d in directions
    }
    focus_codes = [d["code"] for d in directions]

    buckets: dict[str | None, dict[str, Any]] = {
        code: _empty_bucket(code, names[code]) for code in focus_codes
    }

    def bucket(code: str | None) -> dict[str, Any]:
        if code not in buckets:
            name = GENERAL_NAME if code is None else str(code)
            buckets[code] = _empty_bucket(code, name)
        return buckets[code]

    for item in reports:
        b = bucket(item.get("direction"))
        created = _aware(item.get("created_at"))
        status = item.get("status")

        b["reports_total"] += 1

        if created and created >= since:
            b["reports_recent"] += 1

        if status == "submitted":
            b["reports_awaiting_review"] += 1
            if created and created < stale_before:
                b["reports_stale_review"] += 1
        elif status == "needs_revision":
            b["reports_needs_revision"] += 1

    for item in projects:
        b = bucket(item.get("direction"))
        created = _aware(item.get("created_at"))

        b["projects_total"] += 1

        if created and created >= since:
            b["projects_recent"] += 1

        if item.get("status") == "in_progress":
            b["projects_in_progress"] += 1

    overdue_list: list[dict[str, Any]] = []

    for item in tasks:
        b = bucket(item.get("direction"))
        status = item.get("status")
        deadline = _aware(item.get("deadline"))

        b["tasks_total"] += 1

        if status == "completed":
            b["tasks_completed"] += 1
        elif status == "cancelled":
            b["tasks_cancelled"] += 1
        else:
            b["tasks_open"] += 1

            if deadline and deadline < now:
                b["tasks_overdue"] += 1
                overdue_list.append(
                    {
                        "id": item.get("id"),
                        "title": item.get("title", ""),
                        "direction": item.get("direction"),
                        "direction_name": b["name"],
                        "deadline": deadline.isoformat(),
                        "days_overdue": (now - deadline).days,
                    }
                )

    for b in buckets.values():
        counted = b["tasks_total"] - b["tasks_cancelled"]
        b["completion_rate"] = _percent(b["tasks_completed"], counted)
        b["completion_rate_reliable"] = counted >= MIN_SAMPLE

    # Tartib: berilgan yo'nalishlar, keyin boshqa kodlar, oxirida umumiy.
    ordered: list[dict[str, Any]] = [buckets[c] for c in focus_codes]
    extra_codes = sorted(
        str(c) for c in buckets if c is not None and c not in focus_codes
    )
    ordered.extend(buckets[c] for c in extra_codes)

    general = buckets.get(None)
    if general is not None and (
        None not in focus_codes
        and (
            general["reports_total"]
            or general["projects_total"]
            or general["tasks_total"]
        )
    ):
        ordered.append(general)

    overdue_list.sort(key=lambda row: row["days_overdue"], reverse=True)

    totals = {
        key: sum(b[key] for b in ordered)
        for key in (
            "reports_total",
            "reports_recent",
            "reports_awaiting_review",
            "reports_stale_review",
            "reports_needs_revision",
            "projects_total",
            "projects_recent",
            "projects_in_progress",
            "tasks_total",
            "tasks_completed",
            "tasks_cancelled",
            "tasks_open",
            "tasks_overdue",
        )
    }
    totals["completion_rate"] = _percent(
        totals["tasks_completed"],
        totals["tasks_total"] - totals["tasks_cancelled"],
    )

    findings, recommendations = _analyze(
        ordered, focus_codes, totals, window_days
    )

    return {
        "generated_at": now.isoformat(),
        "window_days": window_days,
        "ai_mode": AI_MODE,
        "note": AI_NOTE,
        "totals": totals,
        "directions": ordered,
        "overdue_tasks": overdue_list[:20],
        "findings": findings,
        "recommendations": recommendations,
        "limitations": list(LIMITATIONS),
    }


def _analyze(
    ordered: list[dict[str, Any]],
    focus_codes: list[str | None],
    totals: dict[str, Any],
    window_days: int,
) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    recommendations: list[str] = []

    has_data = (
        totals["reports_total"]
        or totals["projects_total"]
        or totals["tasks_total"]
    )

    if not has_data:
        return (
            ["Tizimda tahlil qilish uchun yetarli ma'lumot hali yo'q."],
            [
                "Hisobot, loyiha va topshiriqlar tizimga kiritila "
                "boshlangach, tahlil to'liqroq bo'ladi."
            ],
        )

    # 1) So'nggi davrda hisobot yubormagan yo'nalishlar.
    silent = [
        b["name"]
        for b in ordered
        if b["code"] in focus_codes and b["reports_recent"] == 0
    ]
    if silent:
        findings.append(
            f"So'nggi {window_days} kun ichida hisobot kiritilmagan "
            f"yo'nalishlar: {', '.join(silent)}."
        )
        recommendations.append(
            "Hisobot kiritilmagan yo'nalishlarda hisobot muddati va "
            "shaklini aniqlashtirish tavsiya etiladi."
        )

    # 2) Muddati o'tgan topshiriqlar.
    if totals["tasks_overdue"]:
        parts = [
            f"{b['name']}: {b['tasks_overdue']}"
            for b in ordered
            if b["tasks_overdue"]
        ]
        findings.append(
            f"Muddati o'tgan ochiq topshiriqlar: {totals['tasks_overdue']} ta "
            f"({'; '.join(parts)})."
        )
        recommendations.append(
            "Muddati o'tgan topshiriqlarning sababini (muddat realligi, "
            "resurs yetarliligi) aniqlash va zarur bo'lsa muddatni qayta "
            "belgilash tavsiya etiladi."
        )

    # 3) Qayta ko'rib chiqish talab qilingan hisobotlar.
    if totals["reports_needs_revision"]:
        findings.append(
            f"Qayta ko'rib chiqish talab qilingan hisobotlar: "
            f"{totals['reports_needs_revision']} ta."
        )
        recommendations.append(
            "Qayta ko'rib chiqish talab qilingan hisobotlarni to'ldirish "
            "uchun aniq izoh va muddat berish tavsiya etiladi."
        )

    # 4) Uzoq vaqt tekshirilmagan hisobotlar.
    if totals["reports_stale_review"]:
        findings.append(
            f"{REVIEW_WAIT_DAYS} kundan beri tekshirilmagan hisobotlar: "
            f"{totals['reports_stale_review']} ta."
        )
        recommendations.append(
            "Tekshiruv navbatini ko'rib chiqib, kutayotgan hisobotlarga "
            "izoh berish tavsiya etiladi."
        )

    # 5) Yo'nalishlar bo'yicha bajarilish ko'rsatkichini solishtirish.
    reliable = [
        b
        for b in ordered
        if b["completion_rate"] is not None and b["completion_rate_reliable"]
    ]
    if len(reliable) >= 2:
        best = max(reliable, key=lambda b: b["completion_rate"])
        worst = min(reliable, key=lambda b: b["completion_rate"])

        if best["completion_rate"] - worst["completion_rate"] >= 20:
            findings.append(
                f"Topshiriqlar bajarilishida yo'nalishlar orasida farq bor: "
                f"eng yuqori «{best['name']}» ({best['completion_rate']}%), "
                f"eng past «{worst['name']}» ({worst['completion_rate']}%)."
            )
            recommendations.append(
                "Ko'rsatkichlar farqining sabablarini (topshiriqlar hajmi, "
                "murakkabligi, muddatlari) birgalikda muhokama qilish "
                "tavsiya etiladi."
            )

    if not findings:
        findings.append(
            "Tekshirilgan ko'rsatkichlar bo'yicha muhim chetlanish "
            "aniqlanmadi."
        )
        recommendations.append(
            "Joriy ish sur'atini saqlab, hisobotlarni muntazam "
            "kiritib borish tavsiya etiladi."
        )

    return findings, recommendations


def build_period_report(overview: dict[str, Any], period: str) -> dict[str, Any]:
    """Haftalik yoki oylik matnli hisobot (period: 'week' | 'month')."""
    title = "Haftalik hisobot" if period == "week" else "Oylik hisobot"
    generated = datetime.fromisoformat(overview["generated_at"])
    totals = overview["totals"]
    days = overview["window_days"]

    def rate(value: int | None) -> str:
        return "ma'lumot yo'q" if value is None else f"{value}%"

    lines: list[str] = [
        f"{title} — MAKTAB AI CONTROL",
        f"Sana: {generated.strftime('%Y-%m-%d')}",
        f"Davr: so'nggi {days} kun",
        "",
        "Umumiy ko'rsatkichlar",
        f"- Hisobotlar: jami {totals['reports_total']}, "
        f"davr ichida {totals['reports_recent']}",
        f"- Loyihalar: jami {totals['projects_total']}, "
        f"davr ichida {totals['projects_recent']}, "
        f"jarayonda {totals['projects_in_progress']}",
        f"- Topshiriqlar: jami {totals['tasks_total']}, "
        f"bajarilgan {totals['tasks_completed']}, "
        f"muddati o'tgan {totals['tasks_overdue']}",
        f"- Topshiriqlar bajarilishi: {rate(totals['completion_rate'])}",
        "",
        "Yo'nalishlar bo'yicha",
    ]

    for index, b in enumerate(overview["directions"], start=1):
        lines.append(
            f"{index}. {b['name']}: hisobot {b['reports_total']} "
            f"(davrda {b['reports_recent']}), loyiha {b['projects_total']}, "
            f"topshiriq {b['tasks_completed']}/{b['tasks_total']} "
            f"({rate(b['completion_rate'])}), "
            f"muddati o'tgan {b['tasks_overdue']}"
        )

    if not overview["directions"]:
        lines.append("- Ko'rsatish uchun ma'lumot yo'q.")

    lines += ["", "Aniqlangan holatlar"]
    lines += [f"- {text}" for text in overview["findings"]]

    lines += ["", "Tavsiyalar"]
    lines += [f"- {text}" for text in overview["recommendations"]]

    lines += ["", "Eslatma"]
    lines += [f"- {overview['note']}"]
    lines += [f"- {text}" for text in overview["limitations"]]

    return {
        "period": period,
        "title": title,
        "generated_at": overview["generated_at"],
        "ai_mode": overview["ai_mode"],
        "text": "\n".join(lines),
    }
