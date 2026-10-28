"""Login cheklovi mantiqi (bazasiz, tez).

Ishga tushirish:  py -3.11 -m pytest tests/test_ratelimit_logic.py -v
"""

from app.ratelimit import LoginLimiter


def test_blocks_after_max_failures_and_unblocks_after_lockout():
    lim = LoginLimiter(max_failures=3, window_seconds=60, lockout_seconds=100)
    key = "1.2.3.4|ali"

    assert lim.retry_after(key, now=0) == 0
    assert lim.register_failure(key, now=1) is False
    assert lim.register_failure(key, now=2) is False
    assert lim.register_failure(key, now=3) is True        # 3-urinishda blok

    assert lim.retry_after(key, now=10) > 0
    assert lim.retry_after(key, now=102) > 0                # hali blok (3+100=103)
    assert lim.retry_after(key, now=104) == 0               # blok tugadi
    assert lim.register_failure(key, now=105) is False      # hisob qaytadan


def test_failures_outside_window_do_not_count():
    lim = LoginLimiter(max_failures=3, window_seconds=60, lockout_seconds=100)
    key = "k"
    lim.register_failure(key, now=0)
    lim.register_failure(key, now=10)
    assert lim.register_failure(key, now=100) is False      # eskilari oynadan chiqdi
    assert lim.retry_after(key, now=101) == 0


def test_success_resets_counter():
    lim = LoginLimiter(max_failures=3, window_seconds=60, lockout_seconds=100)
    key = "k"
    lim.register_failure(key, now=0)
    lim.register_failure(key, now=1)
    lim.reset(key)
    assert lim.register_failure(key, now=2) is False
    assert lim.register_failure(key, now=3) is False


def test_keys_are_independent():
    lim = LoginLimiter(max_failures=2, window_seconds=60, lockout_seconds=100)
    lim.register_failure("a", now=0)
    assert lim.register_failure("a", now=1) is True
    assert lim.retry_after("b", now=2) == 0
    assert lim.register_failure("b", now=2) is False


def test_memory_is_bounded(monkeypatch=None):
    import app.ratelimit as rl

    old = rl.MAX_TRACKED_KEYS
    rl.MAX_TRACKED_KEYS = 50
    try:
        lim = LoginLimiter(max_failures=5, window_seconds=60, lockout_seconds=60)
        for i in range(500):
            lim.register_failure(f"k{i}", now=float(i) * 0.001)
        assert len(lim._failures) <= 60
    finally:
        rl.MAX_TRACKED_KEYS = old
