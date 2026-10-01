import pytest

from routing.optimizer import Candidate, InfeasibleRoute, plan_refuelling


def test_short_trip_needs_no_purchase():
    plan = plan_refuelling([], 300)
    assert plan.purchases == [] and plan.total_cost == 0


def test_one_stop_buys_only_enough_for_destination():
    plan = plan_refuelling([Candidate(1, 400, 3.0)], 700)
    assert len(plan.purchases) == 1
    assert plan.purchases[0].gallons == pytest.approx(20)


def test_cheaper_ahead_buys_only_enough_to_reach_it():
    plan = plan_refuelling([Candidate(1, 400, 4), Candidate(2, 600, 3)], 900)
    assert plan.purchases[0].station_id == 1
    assert plan.purchases[0].gallons == pytest.approx(10)


def test_cheapest_first_fills_tank():
    plan = plan_refuelling([Candidate(1, 400, 3), Candidate(2, 600, 4)], 900)
    assert plan.purchases[0].gallons == pytest.approx(40)


def test_equal_price_uses_tie_rule_without_needless_fill():
    plan = plan_refuelling([Candidate(1, 400, 3), Candidate(2, 600, 3)], 900)
    assert plan.purchases[0].gallons == pytest.approx(10)


def test_infeasible_gap_reports_nodes():
    with pytest.raises(InfeasibleRoute) as error:
        plan_refuelling([Candidate(1, 100, 3), Candidate(2, 700, 3)], 800)
    assert error.value.gap_start_mile == pytest.approx(100)
    assert error.value.gap_end_mile == pytest.approx(700)


def test_origin_gap_is_infeasible():
    with pytest.raises(InfeasibleRoute):
        plan_refuelling([Candidate(1, 600, 3)], 700)
    with pytest.raises(InfeasibleRoute):
        plan_refuelling([Candidate(1, 10, 3)], 700, start_gallons=0)


def test_conservation_and_capacity():
    start = 50
    plan = plan_refuelling([Candidate(1, 100, 4), Candidate(2, 300, 3)], 700)
    assert start + plan.gallons_purchased - plan.gallons_consumed == pytest.approx(plan.ending_gallons)
    assert all(stop.arrival_gallons + stop.gallons <= 50 + 1e-6 for stop in plan.purchases)


def test_candidates_outside_route_are_ignored():
    plan = plan_refuelling([Candidate(1, -10, 1), Candidate(2, 700, 1)], 300)
    assert plan.purchases == []


def test_larger_range_makes_a_long_gap_feasible():
    plan = plan_refuelling([Candidate(1, 877, 3)], 900, range_miles=1000)
    assert plan.ending_gallons >= 0

def test_reason_strings_are_clear():
    from routing.optimizer import Candidate, plan_refuelling
    assert plan_refuelling([Candidate(1,100,3),Candidate(2,300,4)],700).purchases[0].reason == 'lowest price within range ahead: top up to full'
    assert any(p.reason == 'buy just enough to reach a cheaper stop ahead' for p in plan_refuelling([Candidate(1,100,4),Candidate(2,300,3)],700,start_gallons=20).purchases)
    assert plan_refuelling([Candidate(1,400,3)],700).purchases[0].reason == 'buy just enough to reach destination'


