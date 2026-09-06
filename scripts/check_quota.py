"""Report whether the Groq daily token quota can support a full evaluation run.

The per-minute window recovers in seconds, so a small test request succeeds long
before the daily budget can carry a 15-question study. This asks for a
ReAct-sized completion and reports the daily figures the error carries, so the
answer is about the workload rather than about a token-sized probe.

Exit 0 when a full run looks affordable, 1 when it does not.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from sage import config  # noqa: E402

# A 15-question study costs roughly this much, measured from the runs so far.
NEEDED = 25_000


def probe_daily_budget(key: str) -> int | None:
    """Run one real question through the loop.

    Returns ``None`` when the run completes (the budget is genuinely usable), or
    the number of daily tokens left when it is refused. A one-shot completion is
    not evidence: the daily allowance refills gradually, so a tiny request can
    succeed while a multi-step study cannot finish.
    """
    from scripts.run_evaluation import install_offline_data

    install_offline_data()  # keep the probe off the network for market data
    from sage.agent import create_engine

    result = create_engine("openai").run("Should I buy NVDA right now?")
    if not result.error:
        return None

    day = re.search(
        r"tokens per day \(TPD\): Limit (\d+), Used (\d+)", result.error
    )
    if day:
        return int(day.group(1)) - int(day.group(2))
    return 0  # refused for some other throughput reason; not ready either


def main() -> None:
    key = config.get_openai_compat_key()
    if not key:
        print("no API key is set (OPENAI_COMPAT_API_KEY or GROQ_API_KEY)")
        sys.exit(1)

    resp = requests.post(
        f"{config.OPENAI_COMPAT_URL}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": config.OPENAI_COMPAT_MODEL,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "max_tokens": config.OPENAI_COMPAT_MAX_TOKENS,
        },
        timeout=60,
    )

    if resp.status_code == 200:
        # A single small completion succeeding proves very little: the daily
        # budget refills in a trickle, so one request can pass while a
        # 15-question study still cannot start. Ask the loop itself.
        remaining = probe_daily_budget(key)
        if remaining is None:
            print("READY: a full ReAct run completed; the daily budget has room")
            sys.exit(0)
        print(f"WAITING: a full run still hits the daily cap "
              f"({remaining:,} tokens left, a study needs about {NEEDED:,})")
        sys.exit(1)

    message = ""
    try:
        message = (resp.json().get("error") or {}).get("message", "")
    except ValueError:
        pass

    day = re.search(r"tokens per day \(TPD\): Limit (\d+), Used (\d+)", message)
    if day:
        limit, used = int(day.group(1)), int(day.group(2))
        remaining = limit - used
        print(f"WAITING: daily budget {used:,}/{limit:,} used, {remaining:,} left "
              f"(a full study needs about {NEEDED:,})")
    else:
        print(f"WAITING: {message[:160] or resp.status_code}")

    again = re.search(r"try again in ([0-9hms.]+)", message)
    if again:
        print(f"  provider suggests retrying in {again.group(1)}")
    sys.exit(1)


if __name__ == "__main__":
    main()
