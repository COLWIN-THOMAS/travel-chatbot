from app.evaluation.harness import evaluate, to_csv, to_markdown_table
from app.evaluation.metrics import budget_adherence, distance_metrics, interest_match, score_plan
from app.services.route_optimizer import Place


def day(*places):
    return list(places)


class TestBudgetAdherence:
    def test_within_budget(self):
        r = budget_adherence([day(Place("A", 0, 0, cost=100), Place("B", 0, 0, cost=50))], budget_total=200)
        assert r.total_cost == 150 and r.overshoot == 0 and r.within_budget and r.percent_used == 75.0

    def test_over_budget(self):
        r = budget_adherence([day(Place("A", 0, 0, cost=300))], budget_total=200)
        assert r.overshoot == 100 and not r.within_budget and r.percent_used == 150.0

    def test_zero_budget_no_division_error(self):
        r = budget_adherence([], budget_total=0)
        assert r.percent_used == 0.0


class TestDistanceMetrics:
    def test_known_square_route(self):
        a, b, c = Place("A", 0, 0), Place("B", 0, 1), Place("C", 1, 1)
        r = distance_metrics([[a, b, c]])
        # a->b ~111km (1 deg lon at equator), b->c ~111km (1 deg lat); allow generous tolerance
        assert 200 < r.total_km < 240
        assert r.per_day_km == [r.total_km]
        assert r.average_per_day_km == r.total_km

    def test_multi_day_average(self):
        a, b = Place("A", 0, 0), Place("B", 0, 1)
        r = distance_metrics([[a, b], [a]])  # second day has one stop = 0 km
        assert r.per_day_km[1] == 0.0
        assert r.average_per_day_km == round(r.total_km / 2, 2)

    def test_empty(self):
        r = distance_metrics([])
        assert r.total_km == 0 and r.average_per_day_km == 0.0 and r.max_day_km == 0.0


class TestInterestMatch:
    def test_full_match(self):
        places = [Place("A", 0, 0, tags=("food",)), Place("B", 0, 0, tags=("food", "culture"))]
        r = interest_match([places], preferences=["food"])
        assert r.matched_fraction == 1.0

    def test_no_match(self):
        places = [Place("A", 0, 0, tags=("nightlife",))]
        r = interest_match([places], preferences=["food"])
        assert r.matched_fraction == 0.0
        assert r.average_score == 1.0  # baseline score even with no tag overlap

    def test_empty_places(self):
        r = interest_match([], preferences=["food"])
        assert r.average_score == 0.0 and r.matched_fraction == 0.0


class TestHarness:
    def test_evaluate_and_render_table(self):
        plan_a = [day(Place("A", 0, 0, cost=100, tags=("food",)))]
        plan_b = [day(Place("A", 0, 0, cost=100, tags=("food",)), Place("B", 0, 0.01, cost=50))]
        scores = evaluate({"baseline": plan_a, "optimized": plan_b}, budget_total=500, preferences=["food"])
        assert [s.label for s in scores] == ["baseline", "optimized"]
        table = to_markdown_table(scores)
        assert "baseline" in table and "optimized" in table and "budget_used_pct" in table

    def test_csv_round_trips_values(self):
        scores = evaluate({"p": [day(Place("A", 0, 0, cost=10))]}, budget_total=100, preferences=[])
        csv_text = to_csv(scores)
        assert "plan,items,cost_total" in csv_text.splitlines()[0]
        assert "p,1,10" in csv_text

    def test_empty_plans_table(self):
        assert to_markdown_table([]) == "(no results)"


def test_save_charts_writes_expected_files(tmp_path):
    from app.evaluation.harness import save_charts
    scores = evaluate(
        {"baseline": [day(Place("A", 0, 0, cost=100, tags=("food",)))],
         "optimized": [day(Place("A", 0, 0, cost=100, tags=("food",)), Place("B", 0, 0.01, cost=50))]},
        budget_total=500, preferences=["food"],
    )
    paths = save_charts(scores, tmp_path)
    assert len(paths) == 3
    for p in paths:
        assert p.exists() and p.stat().st_size > 0
