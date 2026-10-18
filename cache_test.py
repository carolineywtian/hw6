"""Problem 4: run the vendor desk agent on all 12 practice documents with and without prompt caching.

    source .venv/bin/activate
    python cache_test.py

Setups (see agent.py):
    cache    - instructions + handbook identical on every request, so the provider reuses them from cache.
               The batch gets its own fixed "cache group" label, so its first call starts cold (one cache
               write) and every later call can reuse it, the same 1-write-then-reads model as Problem 2.
    no_cache - a new random ID at the start of every request, so no request can reuse a cached prefix.

Note: the saved output/cache_test.json was measured in Problem 4, when the agent made 3 model calls per
document. Since Problem 6 the defended agent makes 2, so a rerun measures the current agent (lower costs).

Every model call from both setups is saved to output/cache_test.json with the setup, document, every
token count the API reported, Portkey's cache status, and the dollar cost from data/prices.json.
The runs are also appended to output/usage_log.json and output/audit_trail.json like any other run.

Proof checks (printed and saved):
    - every no_cache call reports 0 cached tokens (a no-cache run that shows cached tokens does not count)
    - every call was a real model call: Portkey cache status "REFRESH", never a replayed "HIT"
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from agent import MODEL_NAME, PRICES_PATH, run_agent_async
from tools import now_iso

HERE = Path(__file__).resolve().parent
PRACTICE_DIR = HERE / "data" / "practice_docs"
KEY_PATH = HERE / "data" / "practice_key.json"
OUT_PATH = HERE / "output" / "cache_test.json"
FIELDS = ["vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision"]


async def run_setup(setup: str, key: list[dict], cache_group: str | None) -> tuple[list[dict], list[dict]]:
    """Run all documents one after another (sequential, so each can reuse what the last one cached)."""
    calls, runs = [], []
    for k in key:
        try:
            run = await run_agent_async(PRACTICE_DIR / k["file"], setup, cache_group)
        except Exception as exc:  # logged by run_agent_async; keep going so one failure doesn't stop the test
            print(f"  {setup:8} {k['file']:30} FAILED: {exc}")
            runs.append({"setup": setup, "document": k["file"], "error": str(exc)})
            continue
        u, out = run.usage, run.report.model_dump()
        wrong = [f for f in FIELDS if out[f] != k[f]]
        runs.append(
            {
                "setup": setup,
                "document": k["file"],
                "run_id": u["run_id"],
                "requests": u["requests"],
                "input_tokens": u["input_tokens"],
                "cached_input_tokens": u["cached_input_tokens"],
                "cache_write_tokens": u["cache_write_tokens"],
                "output_tokens": u["output_tokens"],
                "cost_usd": u["cost_usd"],
                "correct": not wrong,
                "wrong_fields": wrong,
                "trap_triggered": run.audit["trap_triggered"],
            }
        )
        for i, r in enumerate(u["per_request"], 1):
            calls.append(
                {
                    "setup": setup,
                    "document": k["file"],
                    "run_id": u["run_id"],
                    "call": i,
                    "time": u["time"],
                    "input_tokens": r["input_tokens"],
                    "cached_input_tokens": r["cached_input_tokens"],
                    "uncached_input_tokens": r["input_tokens"] - r["cached_input_tokens"] - r["cache_write_tokens"],
                    "cache_write_tokens": r["cache_write_tokens"],
                    "output_tokens": r["output_tokens"],
                    "reasoning_tokens": r["reasoning_tokens"],
                    "total_tokens": (r.get("api_usage") or {}).get("total_tokens"),
                    "cost_usd": r["cost_usd"],
                    "api_usage": r.get("api_usage"),
                    "served_model": r.get("served_model"),
                    "portkey_cache_status": r.get("portkey_cache_status"),
                    "portkey_trace_id": r.get("portkey_trace_id"),
                }
            )
        print(
            f"  {setup:8} {k['file']:30} {'OK ' if not wrong else 'BAD'} "
            f"in={u['input_tokens']:>6,} cached={u['cached_input_tokens']:>6,} write={u['cache_write_tokens']:>6,} "
            f"out={u['output_tokens']:>4} ${u['cost_usd']:.8f}"
        )
    return calls, runs


def summarize(setup: str, runs: list[dict], calls: list[dict]) -> dict:
    ok_runs = [r for r in runs if "error" not in r]
    total = sum(r["cost_usd"] for r in ok_runs)
    return {
        "documents": len(ok_runs),
        "failed_runs": len(runs) - len(ok_runs),
        "model_calls": len(calls),
        "correct": sum(r["correct"] for r in ok_runs),
        "traps_triggered": sum(r["trap_triggered"] for r in ok_runs),
        "input_tokens": sum(c["input_tokens"] for c in calls),
        "cached_input_tokens": sum(c["cached_input_tokens"] for c in calls),
        "cache_write_tokens": sum(c["cache_write_tokens"] for c in calls),
        "uncached_input_tokens": sum(c["uncached_input_tokens"] for c in calls),
        "output_tokens": sum(c["output_tokens"] for c in calls),
        "total_cost_usd": round(total, 8),
        "cost_per_document_usd": round(total / len(ok_runs), 8) if ok_runs else None,
    }


async def main() -> None:
    key = json.loads(KEY_PATH.read_text(encoding="utf-8"))
    group = f"p4-{uuid.uuid4().hex[:8]}"
    started = now_iso()

    print(f"With cache (cache group {group}):")
    cache_calls, cache_runs = await run_setup("cache", key, group)
    print("Without cache:")
    nocache_calls, nocache_runs = await run_setup("no_cache", key, None)

    calls = cache_calls + nocache_calls
    summary = {"cache": summarize("cache", cache_runs, cache_calls), "no_cache": summarize("no_cache", nocache_runs, nocache_calls)}
    c, n = summary["cache"]["total_cost_usd"], summary["no_cache"]["total_cost_usd"]
    summary["saved_usd"] = round(n - c, 8)
    summary["saved_percent"] = round((n - c) / n * 100, 2) if n else None

    checks = {
        "no_cache_calls_with_cached_tokens": [
            f"{x['document']} call {x['call']}" for x in nocache_calls if x["cached_input_tokens"] != 0
        ],
        "calls_not_refreshed_by_portkey": [
            f"{x['setup']} {x['document']} call {x['call']}: {x['portkey_cache_status']}"
            for x in calls if x["portkey_cache_status"] != "REFRESH"
        ],
        "served_models": sorted({x["served_model"] or "unknown" for x in calls}),
    }
    checks["no_cache_setup_valid"] = not checks["no_cache_calls_with_cached_tokens"]
    checks["all_calls_real"] = not checks["calls_not_refreshed_by_portkey"]

    OUT_PATH.write_text(
        json.dumps(
            {
                "started": started,
                "finished": now_iso(),
                "model": MODEL_NAME,
                "prices_per_1m": json.loads(PRICES_PATH.read_text(encoding="utf-8"))[MODEL_NAME],
                "cache_group": group,
                "summary": summary,
                "checks": checks,
                "runs": cache_runs + nocache_runs,
                "calls": calls,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"summary": summary, "checks": checks}, indent=2))
    print(f"Saved {len(calls)} model calls to {OUT_PATH.relative_to(HERE)}")


if __name__ == "__main__":
    asyncio.run(main())
