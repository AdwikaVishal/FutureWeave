"""
Production-grade quota manager with auto-recovery, structured logging, and metrics.
"""
import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class QuotaManager:
    def __init__(self, state_file: str = "quota_state.json"):
        self.state_file = state_file
        self._metrics: dict = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "fallback_count": 0,
            "total_latency_ms": 0.0,
        }
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                self.state = json.load(f)
        else:
            self.state = self._fresh_state()

    def _fresh_state(self) -> dict:
        return {
            "mode": os.environ.get("QUOTA_MODE", "deterministic"),
            "calls_today": 0,
            "last_reset": datetime.now().isoformat(),
            "rate_limit_hits": 0,
        }

    @property
    def mode(self) -> str:
        return self.state.get("mode", "full")

    def save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def check_and_update(self, success: bool = True) -> str:
        self._metrics["total_requests"] += 1
        self._auto_reset_if_stale()

        if success:
            self._metrics["successful_requests"] += 1
            self.state["calls_today"] += 1
            self._recover_from_offline()
        else:
            self._metrics["failed_requests"] += 1
            self.state["rate_limit_hits"] += 1
            self._escalate_on_rate_limits()

        if self.mode == "full" and self.state["calls_today"] > 80:
            self.state["mode"] = "low"
            logger.info("[Quota] Switched to low mode (high call volume)")

        self.save_state()
        return self.mode

    def _auto_reset_if_stale(self):
        last = datetime.fromisoformat(self.state.get("last_reset", datetime.now().isoformat()))
        now = datetime.now()
        stale_threshold = timedelta(hours=1) if self.mode == "offline" else timedelta(days=1)
        if now - last > stale_threshold:
            logger.info("[Quota] Auto-reset — was mode=%s, rate_limit_hits=%d", self.mode, self.state.get("rate_limit_hits", 0))
            self.state["calls_today"] = 0
            self.state["last_reset"] = now.isoformat()
            self.state["rate_limit_hits"] = 0
            if self.mode in ("low", "offline"):
                self.state["mode"] = "full"
                logger.info("[Quota] Auto-recovered from %s → full", self.mode)

    def _recover_from_offline(self):
        if self.mode == "offline":
            self.state["mode"] = "full"
            self.state["rate_limit_hits"] = 0
            logger.info("[Quota] RECOVERED from offline → full after successful call")

    def _escalate_on_rate_limits(self):
        if self.state["rate_limit_hits"] >= 20:
            self.state["mode"] = "offline"
            logger.warning("[Quota] Escalated to offline mode (%d rate limit hits)", self.state["rate_limit_hits"])

    def should_use_llm(self, call_type: str = "any") -> bool:
        if call_type == "synthesis":
            return True
        if self.mode == "offline":
            logger.warning("[Quota] BLOCKING call_type='%s' — offline mode", call_type)
            return False
        return True

    def record_call(self, latency_ms: float = 0.0) -> None:
        self._metrics["total_latency_ms"] += latency_ms
        self.check_and_update(success=True)

    def record_error(self, is_rate_limit: bool = False) -> None:
        if is_rate_limit:
            self.check_and_update(success=False)

    def record_fallback(self) -> None:
        self._metrics["fallback_count"] += 1

    def reset(self) -> None:
        self.state = self._fresh_state()
        self._metrics = {k: 0 for k in self._metrics}
        self.save_state()
        logger.info("[Quota] State reset to full mode")

    def stats(self) -> dict:
        return {
            "mode": self.mode,
            "calls_today": self.state.get("calls_today", 0),
            "rate_limit_hits": self.state.get("rate_limit_hits", 0),
            "metrics": dict(self._metrics),
        }


_manager: Optional[QuotaManager] = None


def get_quota_manager() -> QuotaManager:
    global _manager
    if _manager is None:
        _manager = QuotaManager()
    return _manager


def reset_quota() -> None:
    get_quota_manager().reset()
