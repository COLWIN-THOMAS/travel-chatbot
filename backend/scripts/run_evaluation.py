#!/usr/bin/env python3
"""Runs the evaluation harness on the scripted sample data and writes a comparison table +
charts to evaluation/results/. This demonstrates the SCORING METHOD and the route optimizer's
measurable effect versus an unoptimized baseline, using synthetic data - it is not a live-AI
benchmark. For real AI numbers (plan quality, cost per call, latency), see --live below, which
calls the actual Claude API and needs ANTHROPIC_API_KEY set.

Usage:
    python scripts/run_evaluation.py              # scripted sample data (no API calls, no cost)
    python scripts/run_evaluation.py --live        # also runs N real planner calls (uses API credits)
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation import sample_data
from app.evaluation.harness import evaluate, save_charts, to_csv, to_markdown_table

RESULTS_DIR = Path(__file__).resolve().parent.parent / "evaluation" / "results"


def run_scripted() -> None:
    plans = {"baseline (LLM order, unoptimized)": sample_data.baseline_plan(), "route-optimized": sample_data.optimized_plan()}
    scores = evaluate(plans, budget_total=sample_data.TRIP_BUDGET, preferences=sample_data.PREFERENCES)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "comparison.md").write_text(
        "# Route optimizer evaluation (scripted sample data)\n\n"
        "Budget: ₹{:.0f} across {} days. Preferences: {}.\n\n".format(
            sample_data.TRIP_BUDGET, sample_data.TRIP_DAYS, ", ".join(sample_data.PREFERENCES)
        )
        + to_markdown_table(scores) + "\n"
    )
    (RESULTS_DIR / "comparison.csv").write_text(to_csv(scores))
    charts = save_charts(scores, RESULTS_DIR)

    print(to_markdown_table(scores))
    print("\nWrote:")
    print(" ", RESULTS_DIR / "comparison.md")
    print(" ", RESULTS_DIR / "comparison.csv")
    for c in charts:
        print(" ", c)


def run_live(n: int) -> None:
    """Plans `n` real trips through the actual Claude API + Google Places, measuring latency,
    token usage and cost per call. Requires ANTHROPIC_API_KEY and GOOGLE_PLACES_API_KEY."""
    from app import config
    from app.services import llm, planner

    if not config.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY is not set - cannot run --live. Add it to backend/.env and retry.")
        sys.exit(1)

    cases = [
        {"destination": "Goa", "budget_total": 15000.0, "days_count": 4, "preferences": ["food", "beaches"]},
        {"destination": "Jaipur", "budget_total": 9000.0, "days_count": 3, "preferences": ["culture", "history"]},
        {"destination": "Manali", "budget_total": 12000.0, "days_count": 5, "preferences": ["adventure", "nature"]},
    ][:n]

    rows = []
    for case in cases:
        t0 = time.time()
        try:
            plan = planner.create_plan(case)
            elapsed = time.time() - t0
            total_cost = planner.plan_total(plan)
            rows.append({
                "destination": case["destination"], "days": case["days_count"], "budget": case["budget_total"],
                "plan_total": round(total_cost, 2), "within_budget": total_cost <= case["budget_total"],
                "latency_s": round(elapsed, 2), "items": sum(len(d.items) for d in plan.days),
            })
            print("OK   {dest:10s} {lat:5.1f}s  plan_total=Rs{tot:.0f} (budget Rs{bud:.0f})".format(
                dest=case["destination"], lat=elapsed, tot=total_cost, bud=case["budget_total"]))
        except (planner.PlanError, llm.LLMUnavailable) as e:
            print("FAIL {:10s} {}".format(case["destination"], e))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "live_run.json"
    out.write_text(json.dumps(rows, indent=2))
    print("\nWrote", out)
    print("Note: token counts / exact $ cost per call are visible in the Anthropic console usage dashboard for this time window.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="also run N real planner calls against Claude")
    parser.add_argument("--n", type=int, default=3, help="number of live cases to run (max 3)")
    args = parser.parse_args()

    run_scripted()
    if args.live:
        print("\n--- live run ---")
        run_live(min(args.n, 3))
