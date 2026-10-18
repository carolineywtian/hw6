"""Problem 8: run the final DEFENDED agent on every exam document and save the results, untouched.

    source .venv/bin/activate
    python exam_test.py

Writes output/exam_results.json: one entry per file in data/exam_docs/, with exactly these fields:
    file, vendor, sku, unit_price, lead_time_days, min_order, decision, reason,
    trap_tool_called, input_tokens, cached_tokens, output_tokens, cost_usd

No hand edits: every value is copied straight from the agent's run (agent.run_agent_async) and the token
counts and cost the API reported. To make any later edit detectable, it also writes
output/exam_results_provenance.json with:
    - the SHA-256 fingerprint of exam_results.json as written
    - the run_id of each entry, so every value can be checked against usage_log.json / audit_trail.json
    - any dangerous-tool attempts the defended agent blocked (they never ran)
and makes exam_results.json read-only. `python exam_test.py --verify` re-checks all of it.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import stat
import sys
from pathlib import Path

import agent as A
from tools import AUDIT_TRAIL_PATH, TRAP_CALLS_PATH, USAGE_LOG_PATH, ensure_log_files, now_iso

HERE = Path(__file__).resolve().parent
EXAM_DIR = HERE / "data" / "exam_docs"
OUT_PATH = HERE / "output" / "exam_results.json"
PROVENANCE_PATH = HERE / "output" / "exam_results_provenance.json"
FIELDS = ["file", "vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision", "reason",
          "trap_tool_called", "input_tokens", "cached_tokens", "output_tokens", "cost_usd"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entry_from_run(path: Path, run: A.AgentRun) -> dict:
    report, usage = run.report, run.usage
    traps = [t for t in json.loads(TRAP_CALLS_PATH.read_text(encoding="utf-8")) if t["run_id"] == usage["run_id"]]
    return {
        "file": path.name,
        "vendor": report.vendor,
        "sku": report.sku,
        "unit_price": report.unit_price,
        "lead_time_days": report.lead_time_days,
        "min_order": report.min_order,
        "decision": report.decision,
        "reason": report.reason,
        # true only if send_email / approve_payment actually ran for this run
        "trap_tool_called": bool(traps) or run.audit["trap_triggered"],
        "input_tokens": usage["input_tokens"],
        "cached_tokens": usage["cached_input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cost_usd": usage["cost_usd"],
    }


async def main() -> None:
    ensure_log_files()
    if OUT_PATH.exists():  # an earlier run's file is read-only; replace it only with a fresh full run
        OUT_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    docs = sorted(p for p in EXAM_DIR.iterdir() if p.suffix.lower() in (".html", ".htm", ".pdf", ".eml"))
    results, provenance = [], []
    for path in docs:
        run = await A.run_agent_async(path)  # the final defended agent: all three layers, default settings
        assert run.usage["defenses"] == "on", "Problem 8 must use the defended agent"
        entry = entry_from_run(path, run)
        results.append(entry)
        provenance.append({
            "file": path.name,
            "run_id": run.usage["run_id"],
            "time": run.usage["time"],
            "document_sha256": sha256(path),
            "portkey_cache_status": [r.get("portkey_cache_status") for r in run.usage["per_request"]],
            "blocked_dangerous_tool_attempts": run.audit["blocked_dangerous_tool_attempts"],
            "hidden_text_removed_by_code": run.audit["document_report"]["hidden_text_removed"],
            "visible_text_flagged_by_code": run.audit["document_report"]["visible_text_flagged"],
        })
        print(f"{path.name:16} {entry['decision']:17} trap={entry['trap_tool_called']!s:5} "
              f"in={entry['input_tokens']:,} cached={entry['cached_tokens']:,} out={entry['output_tokens']} ${entry['cost_usd']:.8f}")

    OUT_PATH.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    OUT_PATH.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # read-only
    PROVENANCE_PATH.write_text(json.dumps({
        "generated": now_iso(),
        "generated_by": "exam_test.py (no hand edits)",
        "model": A.MODEL_NAME,
        "agent": "defended (code + design + prompt layers)",
        "exam_results_sha256": sha256(OUT_PATH),
        "runs": provenance,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {OUT_PATH.relative_to(HERE)} ({len(results)} entries, read-only) and {PROVENANCE_PATH.relative_to(HERE)}")
    verify()


def verify() -> bool:
    """Check exam_results.json is exactly what the logged runs produced, and has not been edited."""
    results = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    prov = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    usage = {e["run_id"]: e for e in json.loads(USAGE_LOG_PATH.read_text(encoding="utf-8"))}
    audit = {e["run_id"]: e for e in json.loads(AUDIT_TRAIL_PATH.read_text(encoding="utf-8"))}
    problems = []
    if sha256(OUT_PATH) != prov["exam_results_sha256"]:
        problems.append("exam_results.json fingerprint changed since it was written (edited?)")
    if [r["file"] for r in results] != [p["file"] for p in prov["runs"]]:
        problems.append("file list does not match the provenance record")
    for r, p in zip(results, prov["runs"]):
        if list(r) != FIELDS:
            problems.append(f"{r['file']}: fields are not exactly {FIELDS}")
        u, a = usage.get(p["run_id"]), audit.get(p["run_id"])
        if not u or not a:
            problems.append(f"{r['file']}: run {p['run_id']} missing from the logs")
            continue
        logged = {**{k: a["final_answer"][k] for k in ("vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision", "reason")},
                  "input_tokens": u["input_tokens"], "cached_tokens": u["cached_input_tokens"],
                  "output_tokens": u["output_tokens"], "cost_usd": u["cost_usd"], "trap_tool_called": a["trap_triggered"]}
        for k, v in logged.items():
            if r[k] != v:
                problems.append(f"{r['file']}: {k} is {r[k]!r} but the logged run says {v!r}")
        if u["document"] != r["file"] or u.get("defenses") != "on":
            problems.append(f"{r['file']}: logged run is not the defended agent on this file")
        if sha256(EXAM_DIR / r["file"]) != p["document_sha256"]:
            problems.append(f"{r['file']}: the exam document itself changed after the run")
    print("VERIFIED: every value matches the logged runs and the file is unedited." if not problems
          else "VERIFY FAILED:\n  " + "\n  ".join(problems))
    return not problems


if __name__ == "__main__":
    if "--verify" in sys.argv:
        sys.exit(0 if verify() else 1)
    asyncio.run(main())
