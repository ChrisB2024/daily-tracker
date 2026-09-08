#!/usr/bin/env python3
"""
Read-only smoke test. Hits every GET endpoint and checks the response shapes the
frontend actually reads.

    python scripts/smoke.py                       # http://127.0.0.1:8001
    python scripts/smoke.py --url https://...     # production
    python scripts/smoke.py --include-debrief     # also GET /debrief

Exits non-zero if anything fails.

Safe against production: every request is a GET, and nothing is written. The one
exception is /debrief, which is opt-in because generating one calls Anthropic and
ElevenLabs and costs money.

This exists because Unit 06 silently deleted a function and every /summary
request 500ed; only booting the server and calling it by hand found that. There
is no test suite, so this is the cheapest thing that would have caught it.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((PASS if ok else FAIL, name, detail))
    return ok


def get(base: str, path: str, timeout: int = 30):
    """Returns (status, parsed_body_or_None)."""
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as r:
            body = r.read()
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # connection refused, timeout, DNS
        return 0, str(e)


def has_keys(obj, *keys) -> bool:
    return isinstance(obj, dict) and all(k in obj for k in keys)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8001")
    ap.add_argument("--include-debrief", action="store_true",
                    help="also GET /debrief (calls Anthropic + ElevenLabs, costs money)")
    args = ap.parse_args()
    base = args.url.rstrip("/")
    print(f"smoke: {base}\n")

    # --- liveness -----------------------------------------------------------
    status, body = get(base, "/healthz")
    if not check("GET /healthz", status == 200 and has_keys(body, "status"), f"status={status}"):
        print("\nserver is not reachable — nothing else can run")
        report()
        return 1

    # --- goals --------------------------------------------------------------
    status, goals = get(base, "/goals")
    check("GET /goals", status == 200 and isinstance(goals, list), f"status={status}")
    goal_id = goals[0]["id"] if goals else None
    if goals:
        check("  goal shape", has_keys(goals[0], "id", "title", "status", "created_at"))

    if goal_id:
        status, g = get(base, f"/goals/{goal_id}")
        check("GET /goals/{id}", status == 200 and has_keys(g, "id", "title"), f"status={status}")

        status, rts = get(base, f"/goals/{goal_id}/rep-types")
        check("GET /goals/{id}/rep-types", status == 200 and isinstance(rts, list), f"status={status}")
        if isinstance(rts, list):
            # Unit "archive fix": archived rep types must not appear by default.
            archived = [r for r in rts if r.get("status") == "archived"]
            check("  archived excluded by default", not archived,
                  f"{len(archived)} archived leaked")
            if rts:
                check("  rep type shape",
                      has_keys(rts[0], "id", "goal_id", "name", "criterion",
                               "duration_minutes", "is_first_rep", "status"))

        status, rts_all = get(base, f"/goals/{goal_id}/rep-types?include_archived=true")
        check("GET /goals/{id}/rep-types?include_archived=true",
              status == 200 and isinstance(rts_all, list)
              and len(rts_all) >= len(rts or []), f"status={status}")

    # --- reps ---------------------------------------------------------------
    status, reps = get(base, "/reps")
    check("GET /reps", status == 200 and isinstance(reps, list), f"status={status}")
    if isinstance(reps, list) and reps:
        check("  rep shape",
              has_keys(reps[0], "id", "goal_id", "rep_type_id", "scheduled_date",
                       "scheduled_time", "status", "calendar_event_id"))
        # Product invariant 1: no orphan reps, no untyped reps.
        orphans = [r for r in reps if not r.get("goal_id") or not r.get("rep_type_id")]
        check("  every rep tagged to a goal and rep type", not orphans,
              f"{len(orphans)} orphaned")
        bad = [r for r in reps if r.get("status") not in ("pending", "completed", "missed")]
        check("  rep status is tri-state", not bad, f"{len(bad)} unexpected")
        status, one = get(base, f"/reps/{reps[0]['id']}")
        check("GET /reps/{id}", status == 200 and has_keys(one, "id"), f"status={status}")

    # --- summary: the payload the dashboard renders --------------------------
    status, s = get(base, "/summary")
    ok = status == 200 and has_keys(
        s, "today_date", "daily_score", "week_total", "weekly_pr",
        "first_rep_rates", "chains", "goals_with_reps", "rhythm_30day",
        "goal_progressions")
    check("GET /summary", ok, f"status={status}")
    if ok:
        check("  first_rep_rates is a list (per goal, Unit 06)",
              isinstance(s["first_rep_rates"], list))
        for r in s["first_rep_rates"]:
            if not check("  first-rep entry shape",
                         has_keys(r, "goal_id", "goal_title", "rate",
                                  "days_hit", "days_scheduled")):
                break
        for c in s["chains"]:
            if not check("  chain entry shape",
                         has_keys(c, "rep_type_id", "rep_type_name", "goal_id",
                                  "goal_title", "current_chain",
                                  "last_completed_date", "history")):
                break
        neg = [c for c in s["chains"] if c["current_chain"] < 0]
        check("  no negative chain", not neg, f"{len(neg)} negative")

    status, _ = get(base, "/summary?date=2026-01-01")
    check("GET /summary?date=", status == 200, f"status={status}")

    status, a = get(base, "/summary/analytics")
    check("GET /summary/analytics", status == 200 and isinstance(a, list), f"status={status}")
    if isinstance(a, list) and a:
        check("  analytics shape",
              has_keys(a[0], "rep_type_id", "rep_type_name", "total_reps",
                       "completed_count", "missed_count", "completion_pct"))

    status, w = get(base, "/summary/week")
    check("GET /summary/week",
          status == 200 and has_keys(w, "week_start", "week_end", "days"),
          f"status={status}")
    if has_keys(w, "days"):
        check("  week has 7 days", len(w["days"]) == 7, f"got {len(w['days'])}")

    status, h = get(base, "/history")
    check("GET /history", status == 200 and isinstance(h, list), f"status={status}")

    status, dh = get(base, "/history/debriefs")
    check("GET /history/debriefs", status == 200 and isinstance(dh, list), f"status={status}")
    if isinstance(dh, list) and dh:
        check("  stored summary shape",
              has_keys(dh[0], "week_start_date", "rep_data", "patterns",
                       "delivered_at", "created_at"))
        # Prose is deliberately not persisted — S2 permits an open API only
        # because the database holds rep metadata.
        blob = json.dumps(dh[0])
        check("  no debrief prose stored",
              "text_summary" not in blob and "summary" not in dh[0]["rep_data"])

    if args.include_debrief:
        status, d = get(base, "/debrief", timeout=120)
        check("GET /debrief", status == 200 and has_keys(d, "summary", "stats"),
              f"status={status}")

    return report()


def report() -> int:
    width = max(len(n) for _, n, _ in results)
    for state, name, detail in results:
        line = f"  {state}  {name.ljust(width)}"
        if detail and state == FAIL:
            line += f"  {detail}"
        print(line)
    failed = sum(1 for s, _, _ in results if s == FAIL)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
