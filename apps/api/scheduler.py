from __future__ import annotations

from typing import Callable, Any
import threading

from apscheduler.schedulers.background import BackgroundScheduler


class SchedulerWrapper:
    def __init__(self):
        self._scheduler = BackgroundScheduler()
        self._started = False
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if not self._started:
                self._scheduler.start()
                self._started = True

    def add_interval_job(self, func: Callable[..., Any], minutes: int, id: str):
        self._scheduler.add_job(func, "interval", minutes=minutes, id=id, replace_existing=True)

    def shutdown(self):
        with self._lock:
            if self._started:
                self._scheduler.shutdown(wait=False)
                self._started = False

