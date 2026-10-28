"""Login urinishlarini cheklash (brute-force himoyasi).

Xotirada ishlaydi: server qayta ishga tushsa hisoblagich tozalanadi. Bitta
jarayonli joylashtirish (masalan, Render'ning bitta xizmati) uchun yetarli.
Bir nechta jarayon yoki server bo'lsa, umumiy saqlash (Redis kabi) kerak bo'ladi.

Modul FastAPI'ga bog'lanmagan, shuning uchun osongina sinab ko'riladi.
"""

from __future__ import annotations

import threading
import time

# Kalitlar soni chegarasi: xotira cheksiz o'smasligi uchun.
MAX_TRACKED_KEYS = 10_000


class LoginLimiter:
    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: int = 300,
        lockout_seconds: int = 300,
    ):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str, now: float | None = None) -> int:
        """Bloklangan bo'lsa, necha soniyadan keyin urinish mumkinligini
        qaytaradi; bloklanmagan bo'lsa 0."""
        now = time.monotonic() if now is None else now

        with self._lock:
            until = self._locked_until.get(key)

            if until is None:
                return 0

            if until <= now:
                self._locked_until.pop(key, None)
                self._failures.pop(key, None)
                return 0

            return int(until - now) + 1

    def register_failure(self, key: str, now: float | None = None) -> bool:
        """Muvaffaqiyatsiz urinishni qayd etadi. Blok boshlansa True."""
        now = time.monotonic() if now is None else now

        with self._lock:
            self._purge(now)

            recent = [
                t
                for t in self._failures.get(key, [])
                if now - t < self.window_seconds
            ]
            recent.append(now)
            self._failures[key] = recent

            if len(recent) >= self.max_failures:
                self._locked_until[key] = now + self.lockout_seconds
                return True

            return False

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

    def _purge(self, now: float) -> None:
        if len(self._failures) < MAX_TRACKED_KEYS:
            return

        for key in list(self._failures):
            fresh = [
                t for t in self._failures[key]
                if now - t < self.window_seconds
            ]

            if fresh or self._locked_until.get(key, 0) > now:
                self._failures[key] = fresh
            else:
                self._failures.pop(key, None)
                self._locked_until.pop(key, None)

        # Hali ham to'la bo'lsa, eng eskilarini tashlab yuboramiz.
        if len(self._failures) >= MAX_TRACKED_KEYS:
            for key in list(self._failures)[: MAX_TRACKED_KEYS // 2]:
                self._failures.pop(key, None)
                self._locked_until.pop(key, None)
