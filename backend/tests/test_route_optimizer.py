import pytest

from app.services.route_optimizer import (
    Place, cluster_into_days, fit_budget, haversine_km, order_day, route_distance_km,
)

# Two well-separated "neighbourhoods" in a fictional city, ~15km apart, each tight internally.
NORTH = [Place("N{}".format(i), 10.00 + i * 0.002, 76.00 + i * 0.002) for i in range(4)]
SOUTH = [Place("S{}".format(i), 10.15 + i * 0.002, 76.15 + i * 0.002) for i in range(4)]


def test_haversine_known_distance():
    # London to Paris is ~344 km.
    london = Place("London", 51.5074, -0.1278)
    paris = Place("Paris", 48.8566, 2.3522)
    assert 330 < haversine_km(london, paris) < 360


def test_haversine_zero_for_same_point():
    p = Place("X", 12.3, 45.6)
    assert haversine_km(p, p) == 0


class TestClustering:
    def test_splits_two_neighbourhoods_cleanly(self):
        clusters = cluster_into_days(NORTH + SOUTH, days=2)
        assert len(clusters) == 2
        names = [{p.name for p in c} for c in clusters]
        assert {"N0", "N1", "N2", "N3"} in names and {"S0", "S1", "S2", "S3"} in names

    def test_every_place_assigned_exactly_once(self):
        places = NORTH + SOUTH
        clusters = cluster_into_days(places, days=3)
        flat = [p for c in clusters for p in c]
        assert sorted(p.name for p in flat) == sorted(p.name for p in places)

    def test_no_cluster_left_empty_when_feasible(self):
        clusters = cluster_into_days(NORTH + SOUTH, days=4)
        assert all(len(c) > 0 for c in clusters)

    def test_days_clamped_to_place_count(self):
        clusters = cluster_into_days(NORTH[:2], days=10)
        assert len(clusters) == 2
        assert all(len(c) == 1 for c in clusters)

    def test_single_day_returns_one_cluster_with_everything(self):
        clusters = cluster_into_days(NORTH, days=1)
        assert len(clusters) == 1 and len(clusters[0]) == 4

    def test_empty_input(self):
        assert cluster_into_days([], days=3) == [[], [], []]

    def test_deterministic(self):
        a = cluster_into_days(NORTH + SOUTH, days=2)
        b = cluster_into_days(NORTH + SOUTH, days=2)
        assert [sorted(p.name for p in c) for c in a] == [sorted(p.name for p in c) for c in b]


class TestOrdering:
    def test_order_day_beats_or_matches_the_input_order(self):
        import random
        rnd = random.Random(42)
        shuffled = NORTH[:]
        rnd.shuffle(shuffled)
        ordered = order_day(shuffled)
        assert route_distance_km(ordered) <= route_distance_km(shuffled) + 1e-9

    def test_order_day_visits_every_place_exactly_once(self):
        ordered = order_day(SOUTH)
        assert sorted(p.name for p in ordered) == sorted(p.name for p in SOUTH)

    def test_order_day_starts_from_given_start(self):
        hotel = Place("Hotel", 10.20, 76.20)
        ordered = order_day(SOUTH, start=hotel)
        assert ordered[0] != hotel  # start itself isn't repeated in the output
        assert sorted(p.name for p in ordered) == sorted(p.name for p in SOUTH)
        # nearest stop to the hotel should be visited first (hotel is past S3, closest is S3)
        assert ordered[0].name == "S3"

    def test_empty_and_single_place(self):
        assert order_day([]) == []
        assert order_day([NORTH[0]]) == [NORTH[0]]

    def test_two_opt_untangles_a_crossing_route(self):
        # A square where the naive nearest-neighbour-free "as-given" order crosses itself.
        a, b, c, d = Place("A", 0, 0), Place("B", 0, 1), Place("C", 1, 0), Place("D", 1, 1)
        crossed = [a, d, b, c]  # A->D->B->C crosses the square's diagonal twice
        fixed = order_day(crossed, start=None)
        assert route_distance_km(fixed) < route_distance_km(crossed)


class TestBudgetFit:
    def test_respects_the_budget_cap(self):
        candidates = [Place("A", 0, 0, cost=100), Place("B", 0, 0, cost=100), Place("C", 0, 0, cost=100)]
        chosen = fit_budget(candidates, day_budget=250)
        assert sum(p.cost for p in chosen) <= 250

    def test_picks_higher_value_combination_over_greedy_single_pick(self):
        # One expensive, two cheap-but-combined-more-valuable with matching preferences.
        expensive = Place("Museum", 0, 0, cost=200, tags=("culture",))
        cheap1 = Place("Market", 0, 0, cost=100, tags=("food",))
        cheap2 = Place("Temple", 0, 0, cost=100, tags=("culture",))
        chosen = fit_budget([expensive, cheap1, cheap2], day_budget=200, preferences=["food", "culture"])
        names = {p.name for p in chosen}
        assert names == {"Market", "Temple"}  # value 2+2=4 beats the single Museum's 2

    def test_must_keep_is_always_included(self):
        hotel = Place("Hotel", 0, 0, cost=800)
        extra = Place("Extra", 0, 0, cost=50)
        chosen = fit_budget([extra], day_budget=900, must_keep=[hotel])
        assert hotel in chosen and extra in chosen

    def test_must_keep_over_budget_raises(self):
        hotel = Place("Hotel", 0, 0, cost=5000)
        with pytest.raises(ValueError):
            fit_budget([], day_budget=1000, must_keep=[hotel])

    def test_zero_budget_after_must_keep_returns_only_must_keep(self):
        hotel = Place("Hotel", 0, 0, cost=1000)
        extra = Place("Extra", 0, 0, cost=1)
        chosen = fit_budget([extra], day_budget=1000, must_keep=[hotel])
        assert chosen == [hotel]

    def test_free_places_are_always_affordable(self):
        free_places = [Place("Park{}".format(i), 0, 0, cost=0) for i in range(5)]
        chosen = fit_budget(free_places, day_budget=0)
        assert len(chosen) == 5

    def test_preferences_increase_interest_score_but_dont_force_inclusion_over_budget(self):
        pricey_match = Place("Pricey", 0, 0, cost=1000, tags=("food",))
        chosen = fit_budget([pricey_match], day_budget=10, preferences=["food"])
        assert chosen == []
