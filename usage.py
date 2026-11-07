"""Logs what each Claude call costs, to one file all of Bytronix's tools share, so the brief can show spend."""

from __future__ import annotations

import csv
import fcntl
from datetime import datetime
from pathlib import Path

LOG = Path.home() / "bytronix-outreach" / "api_usage.csv"
COLUMNS = ["time", "tool", "task", "model", "input_tokens", "output_tokens", "cost_usd"]
# Dollars per million tokens (input, output), first-party API rates.
PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.00, 20.00)}


def cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rate_in, rate_out = next((v for k, v in PRICES.items() if model.startswith(k)), PRICES["claude-sonnet-5-5"])
    return (input_tokens * rate_in + output_tokens * rate_out) / 1_000_000


def record(response, tool: str, task: str) -> None:
    """Append one call's usage. Never raises: a logging problem mustn't stop the work."""
    try:
        usage = response.usage
        tokens_in = (usage.input_tokens or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0)
        tokens_out = usage.output_tokens or 0
        LOG.parent.mkdir(parents=True, exist_ok=True)
        new = not LOG.exists()
        with open(LOG, "a", newline="", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)          # the tools can run at the same time
            w = csv.writer(f)
            if new:
                w.writerow(COLUMNS)
            w.writerow([datetime.now().isoformat(timespec="seconds"), tool, task, response.model, tokens_in, tokens_out,
                        f"{cost(response.model, tokens_in, tokens_out):.5f}"])
    except Exception:  # noqa: BLE001
        pass
