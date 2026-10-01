import math
import random

import pytest

from routing.optimizer import Candidate, InfeasibleRoute, plan_refuelling


def oracle(cands, total, range_miles, mpg=10.0, start=None):
    tank = range_miles / mpg
    start = tank if start is None else start
    unit = 10
    cap = int(round(tank * unit))
    nodes = sorted(cands, key=lambda c: c.mile) + [Candidate(-1, total, 0.0)]
    inf = 1e18
    dp = [inf] * (cap + 1)
    dp[int(round(start * unit))] = 0.0
    previous = 0.0
    for node in nodes:
        used = math.ceil((node.mile - previous) / mpg * unit - 1e-9)
        next_dp = [inf] * (cap + 1)
        for fuel in range(cap + 1):
            if dp[fuel] < inf and fuel - used >= 0:
                next_dp[fuel - used] = min(next_dp[fuel - used], dp[fuel])
        dp = next_dp
        for fuel in range(1, cap + 1):
            if dp[fuel - 1] < inf:
                dp[fuel] = min(dp[fuel], dp[fuel - 1] + node.price / unit)
        previous = node.mile
    return min(dp)


@pytest.mark.parametrize("range_miles", [500.0, 1000.0])
def test_greedy_matches_dp_oracle(range_miles):
    random.seed(7)
    feasible = infeasible = 0
    for _index in range(600):
        total = random.choice([300, 700, 1200, 2000, 2800])
        count = random.randint(1, 45)
        candidates = [
            Candidate(
                i, round(random.uniform(0, total) / 10) * 10, round(random.uniform(2.7, 4.5), 3)
            )
            for i in range(count)
        ]
        start = random.choice([None, 0.0, 20.0])
        expected = oracle(candidates, total, range_miles, start=start)
        try:
            plan = plan_refuelling(candidates, total, range_miles=range_miles, start_gallons=start)
        except InfeasibleRoute:
            assert expected >= 1e17
            infeasible += 1
            continue
        assert abs(plan.total_cost - expected) <= 0.08
        start_gallons = range_miles / 10 if start is None else start
        assert start_gallons + plan.gallons_purchased == pytest.approx(
            plan.gallons_consumed + plan.ending_gallons
        )
        feasible += 1
    assert feasible + infeasible == 600
