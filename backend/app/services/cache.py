import time
from collections import OrderedDict
from threading import Lock
from typing import Any


class TranslationCache:
    """Thread-safe in-memory LRU cache for translations and detections."""

    def __init__(self, max_size: int = 2000, ttl_seconds: float = 3600.0) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = Lock()

    @staticmethod
    def make_translation_key(
        text: str,
        source: str,
        target: str,
        style: str = "general",
        mode: str = "auto",
    ) -> str:
        s = source.strip().lower()
        t = target.strip().lower()
        st = style.strip().lower()
        m = mode.strip().lower()
        return f"{s}:{t}:{st}:{m}:{text.strip()}"

    @staticmethod
    def make_detection_key(text: str) -> str:
        return text.strip()[:300]

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            ts, val = entry
            if time.time() - ts > self.ttl_seconds:
                try:
                    del self._cache[key]
                except KeyError:
                    pass
                return None
            self._cache.move_to_end(key)
            return val

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (time.time(), value)
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


# Global singletons
translation_cache = TranslationCache(max_size=3000, ttl_seconds=3600.0)
detection_cache = TranslationCache(max_size=1000, ttl_seconds=3600.0)
word_cache = TranslationCache(max_size=5000, ttl_seconds=7200.0)
