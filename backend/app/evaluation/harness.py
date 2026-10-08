"""Runs a set of (label -> day-grouped plan) through the scoring metrics, producing a comparison
table and bar charts. Used both by tests (in-memory, no file I/O) and by scripts/run_evaluation.py
(writes results to evaluation/results/)."""
import csv
import io
from pathlib import Path
from typing import Dict, List, Sequence

from app.evaluation.metrics import PlanScore, score_plan
from app.services.route_optimizer import Place


def evaluate(plans: Dict[str, Sequence[Sequence[Place]]], budget_total: float, preferences: Sequence[str]) -> List[PlanScore]:
    return [score_plan(label, days, budget_total, preferences) for label, days in plans.items()]


def to_markdown_table(scores: Sequence[PlanScore]) -> str:
    rows = [s.as_row() for s in scores]
    if not rows:
        return "(no results)"
    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(lines)


def to_csv(scores: Sequence[PlanScore]) -> str:
    rows = [s.as_row() for s in scores]
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return buf.getvalue()


def save_charts(scores: Sequence[PlanScore], out_dir: Path) -> List[Path]:
    """One bar chart per metric, comparing plans side by side. Returns the files written.
    Imports matplotlib lazily so importing this module never requires a display backend."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    labels = [s.label for s in scores]
    metrics = [
        ("budget_used_pct", "Budget used (%)", "over_budget_by"),
        ("avg_km_per_day", "Avg travel distance per day (km)", None),
        ("interest_match_pct", "Places matching stated interests (%)", None),
    ]
    written = []
    for key, title, annotate_key in metrics:
        values = [getattr(s, "as_row")()[key] for s in scores]
        fig, ax = plt.subplots(figsize=(5, 3.5))
        bars = ax.bar(labels, values, color="#2f9e44")
        ax.set_title(title)
        ax.set_ylabel(title)
        for i, (bar, s) in enumerate(zip(bars, scores)):
            label = str(values[i])
            if annotate_key and s.as_row()[annotate_key]:
                label += "\n(over by {:.0f})".format(s.as_row()[annotate_key])
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), label, ha="center", va="bottom", fontsize=8)
        fig.tight_layout()
        path = out_dir / "{}.png".format(key)
        fig.savefig(path, dpi=120)
        plt.close(fig)
        written.append(path)
    return written
