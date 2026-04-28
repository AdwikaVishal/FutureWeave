import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Any, Optional

_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".llm_cache")
_DEFAULT_TTL_DAYS = int(os.environ.get("LLM_CACHE_TTL_DAYS", "7"))


class LLMCache:
    """Two-tier cache: in-memory (fast) → file-based (persistent)."""

    def __init__(self, cache_dir: str = _CACHE_DIR, ttl_days: int = _DEFAULT_TTL_DAYS):
        self.cache_dir = cache_dir
        self.ttl = timedelta(days=ttl_days)
        os.makedirs(cache_dir, exist_ok=True)
        self.mem_cache: dict[str, dict] = {}

    def _key(self, prompt: str, model: str) -> str:
        content = f"{model}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def make_key(self, *parts: str) -> str:
        """Build a cache key from arbitrary string parts (for external use)."""
        return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()

    def get(self, prompt: str, model: str) -> Optional[Any]:
        k = self._key(prompt, model)
        # 1. Memory first
        if k in self.mem_cache:
            entry = self.mem_cache[k]
            if datetime.now() - datetime.fromisoformat(entry["timestamp"]) < self.ttl:
                return entry["response"]
            del self.mem_cache[k]
        # 2. Then disk
        path = os.path.join(self.cache_dir, f"{k}.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    entry = json.load(f)
                if datetime.now() - datetime.fromisoformat(entry["timestamp"]) < self.ttl:
                    self.mem_cache[k] = entry  # restore to memory
                    return entry["response"]
            except Exception:
                pass
        return None

    def set(self, prompt: str, model: str, response: Any) -> None:
        k = self._key(prompt, model)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "response": response,
        }
        self.mem_cache[k] = entry
        path = os.path.join(self.cache_dir, f"{k}.json")
        try:
            with open(path, "w") as f:
                json.dump(entry, f)
        except Exception as exc:
            print(f"[Cache] Disk write failed: {exc}")

    def invalidate(self, prompt: str, model: str) -> None:
        k = self._key(prompt, model)
        self.mem_cache.pop(k, None)
        path = os.path.join(self.cache_dir, f"{k}.json")
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


# Module-level singleton
_cache = LLMCache()


def get_cache() -> LLMCache:
    return _cache
