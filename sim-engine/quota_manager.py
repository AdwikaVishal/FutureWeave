import os
import json
from datetime import datetime, timedelta


class QuotaManager:
    def __init__(self, state_file="quota_state.json"):
        self.state_file = state_file
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                self.state = json.load(f)
        else:
            self.state = {
                "mode": "full",          # full, low, offline
                "calls_today": 0,
                "last_reset": datetime.now().isoformat(),
                "rate_limit_hits": 0
            }

    @property
    def mode(self) -> str:
        return self.state["mode"]

    def save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def check_and_update(self, success: bool = True):
        # Reset daily counter if needed
        last = datetime.fromisoformat(self.state["last_reset"])
        if datetime.now() - last > timedelta(days=1):
            self.state["calls_today"] = 0
            self.state["last_reset"] = datetime.now().isoformat()
            self.state["rate_limit_hits"] = 0
            # Auto-recover from low mode on daily reset
            if self.state["mode"] == "low":
                self.state["mode"] = "full"

        if not success:
            self.state["rate_limit_hits"] += 1
            if self.state["rate_limit_hits"] >= 3:
                self.state["mode"] = "offline"
                print("[Quota] Switching to offline mode after repeated rate limit errors")
        else:
            self.state["calls_today"] += 1
            # Recover from offline if we're succeeding again
            if self.state["mode"] == "offline":
                self.state["mode"] = "full"
                self.state["rate_limit_hits"] = 0
                print("[Quota] Recovered to full mode after successful call")

        # "low" mode is only a soft budget warning — never blocks synthesis
        # Only offline (actual rate-limit failures) blocks LLM calls
        if self.state["mode"] == "full" and self.state["calls_today"] > 80:
            self.state["mode"] = "low"
            print("[Quota] Switching to low mode (high call volume — synthesis still allowed)")

        self.save_state()
        return self.state["mode"]

    def should_use_llm(self, call_type: str = "any") -> bool:
        """
        Returns True if an LLM call of the given type should proceed.

        call_type values:
          "timeline_batch" — blocked only in offline mode
          "synthesis"      — blocked only in offline mode (NOT in low mode)
          "any"            — blocked only in offline mode
        """
        # Only hard-block on offline (real rate-limit failures)
        if self.state["mode"] == "offline":
            print(f"[Quota] BLOCKING call_type='{call_type}' — offline mode (rate limit hit)")
            return False
        return True

    def record_call(self) -> None:
        """Record a successful LLM call (alias for check_and_update(success=True))."""
        self.check_and_update(success=True)

    def record_error(self, is_rate_limit: bool = False) -> None:
        """Record a failed LLM call."""
        if is_rate_limit:
            self.check_and_update(success=False)

    def reset(self) -> None:
        """Force quota back to full mode and clear all counters."""
        self.state = {
            "mode": "full",
            "calls_today": 0,
            "last_reset": datetime.now().isoformat(),
            "rate_limit_hits": 0,
        }
        self.save_state()
        print("[Quota] State reset to full mode ✓")

    def stats(self) -> dict:
        return {
            "mode": self.state["mode"],
            "calls_today": self.state["calls_today"],
            "rate_limit_hits": self.state["rate_limit_hits"],
        }


# Module-level singleton — always loads fresh state from disk
_manager = QuotaManager()


def get_quota_manager() -> QuotaManager:
    return _manager


def reset_quota() -> None:
    """Reset quota to full mode. Call this from CLI or test scripts."""
    _manager.reset()
