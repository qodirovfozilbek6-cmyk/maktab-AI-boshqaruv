"""AI markazi mantiqi testlari (bazasiz, tez).

Ishga tushirish:  py -3.11 -m pytest tests/test_ai_center_logic.py -v
"""

from datetime import datetime, timedelta, timezone

from app.ai_center import build_overview, build_period_report

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
DIRS = [
    {"code": "education", "name": "Ta'lim"},
    {"code": "sport", "name": "Sport"},
    {"code": "media", "name": "Media"},
]


def ago(days):
    return NOW - timedelta(days=days)


def test_empty_data_gives_clear_message():
    ov = build_overview(DIRS, [], [], [], now=NOW)
    assert ov["ai_mode"] == "local"
    assert "API kalit talab qilinmaydi" in ov["note"]
    assert ov["totals"]["reports_total"] == 0
    assert "yetarli ma'lumot" in ov["findings"][0]
    assert len(ov["directions"]) == 3


def test_counts_recent_and_total_reports():
    reports = [
        {"direction": "sport", "status": "reviewed", "created_at": ago(2)},
        {"direction": "sport", "status": "reviewed", "created_at": ago(60)},
        {"direction": "media", "status": "reviewed", "created_at": ago(5)},
    ]
    ov = build_overview(DIRS, reports, [], [], now=NOW, window_days=30)
    by = {b["code"]: b for b in ov["directions"]}
    assert by["sport"]["reports_total"] == 2
    assert by["sport"]["reports_recent"] == 1
    assert by["education"]["reports_total"] == 0


def test_silent_direction_is_flagged():
    reports = [{"direction": "sport", "status": "reviewed", "created_at": ago(1)}]
    ov = build_overview(DIRS, reports, [], [], now=NOW)
    text = " ".join(ov["findings"])
    assert "Ta'lim" in text and "Media" in text
    assert "Sport" not in text.split("yo'nalishlar:")[1]


def test_overdue_detection_handles_naive_and_aware_datetimes():
    naive_past = (NOW - timedelta(days=3)).replace(tzinfo=None)
    tasks = [
        {"id": 1, "title": "A", "direction": "sport", "status": "pending",
         "deadline": naive_past},
        {"id": 2, "title": "B", "direction": "sport", "status": "completed",
         "deadline": ago(10)},                       # bajarilgan: o'tmagan
        {"id": 3, "title": "C", "direction": "sport", "status": "cancelled",
         "deadline": ago(10)},                       # bekor: o'tmagan
        {"id": 4, "title": "D", "direction": "sport", "status": "in_progress",
         "deadline": NOW + timedelta(days=2)},       # muddati hali kelmagan
        {"id": 5, "title": "E", "direction": "media", "status": "in_progress",
         "deadline": ago(8)},
        {"id": 6, "title": "F", "direction": "media", "status": "pending",
         "deadline": None},                          # muddatsiz
    ]
    ov = build_overview(DIRS, [], [], tasks, now=NOW)
    assert ov["totals"]["tasks_overdue"] == 2
    ids = [row["id"] for row in ov["overdue_tasks"]]
    assert ids == [5, 1]                             # eng kechikkani birinchi
    assert ov["overdue_tasks"][0]["days_overdue"] == 8
    assert any("Muddati o'tgan" in f for f in ov["findings"])


def test_completion_rate_ignores_cancelled_and_marks_small_samples():
    tasks = (
        [{"id": i, "title": "t", "direction": "sport",
          "status": "completed", "deadline": None} for i in range(3)]
        + [{"id": 10, "title": "t", "direction": "sport",
            "status": "cancelled", "deadline": None}]
        + [{"id": 11, "title": "t", "direction": "media",
            "status": "completed", "deadline": None}]
    )
    ov = build_overview(DIRS, [], [], tasks, now=NOW)
    by = {b["code"]: b for b in ov["directions"]}
    assert by["sport"]["completion_rate"] == 100       # bekor qilingani sanalmaydi
    assert by["sport"]["completion_rate_reliable"] is True
    assert by["media"]["completion_rate_reliable"] is False   # namuna kichik
    assert by["education"]["completion_rate"] is None


def test_direction_comparison_needs_reliable_samples_and_gap():
    def mk(code, done, total):
        rows = []
        for i in range(total):
            rows.append({"id": hash((code, i)) % 10_000, "title": "t",
                         "direction": code,
                         "status": "completed" if i < done else "pending",
                         "deadline": None})
        return rows

    tasks = mk("sport", 4, 4) + mk("media", 1, 4)       # 100% va 25%
    ov = build_overview(DIRS, [], [], tasks, now=NOW)
    joined = " ".join(ov["findings"])
    assert "«Sport» (100%)" in joined and "«Media» (25%)" in joined

    close = mk("sport", 4, 4) + mk("media", 5, 6)       # 100% va 83%: farq 20 dan kam
    ov2 = build_overview(DIRS, [], [], close, now=NOW)
    assert "farq bor" not in " ".join(ov2["findings"])


def test_revision_and_stale_review_are_reported():
    reports = [
        {"direction": "sport", "status": "needs_revision", "created_at": ago(1)},
        {"direction": "sport", "status": "submitted", "created_at": ago(9)},
        {"direction": "sport", "status": "submitted", "created_at": ago(2)},
    ]
    ov = build_overview(DIRS, reports, [], [], now=NOW)
    t = ov["totals"]
    assert t["reports_needs_revision"] == 1
    assert t["reports_awaiting_review"] == 2
    assert t["reports_stale_review"] == 1


def test_direction_less_items_go_to_general_bucket_last():
    reports = [{"direction": None, "status": "reviewed", "created_at": ago(1)}]
    ov = build_overview(DIRS, reports, [], [], now=NOW)
    assert ov["directions"][-1]["code"] is None
    assert ov["directions"][-1]["name"] == "Yo'nalishsiz (umumiy)"
    assert ov["totals"]["reports_total"] == 1


def test_no_general_bucket_when_empty_and_scope_has_no_directions():
    ov = build_overview([], [], [], [], now=NOW)
    assert ov["directions"] == []


def test_normal_state_gives_positive_finding():
    reports = [
        {"direction": d["code"], "status": "reviewed", "created_at": ago(1)}
        for d in DIRS
    ]
    ov = build_overview(DIRS, reports, [], [], now=NOW)
    assert "muhim chetlanish aniqlanmadi" in ov["findings"][0]


def test_period_report_text_and_safety_notes():
    reports = [{"direction": "sport", "status": "reviewed", "created_at": ago(1)}]
    ov = build_overview(DIRS, reports, [], [], now=NOW, window_days=7)
    week = build_period_report(ov, "week")
    month = build_period_report(ov, "month")
    assert week["title"] == "Haftalik hisobot"
    assert month["title"] == "Oylik hisobot"
    assert "so'nggi 7 kun" in week["text"]
    assert "Sport: hisobot 1" in week["text"]
    assert "intizomiy qaror uchun asos bo'lmaydi" in week["text"]
    assert week["ai_mode"] == "local"
