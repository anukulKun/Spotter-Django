import random

import pytest

from routing.optimizer import Candidate, InfeasibleRoute, plan_refuelling


def brute(candidates, total, rng, penalty):
    best = float("inf")
    for mask in range(1 << len(candidates)):
        subset = [c for i, c in enumerate(candidates) if mask >> i & 1]
        try:
            plan = plan_refuelling(subset, total, rng, 10, rng / 10, 0)
        except InfeasibleRoute:
            continue
        best = min(best, plan.total_cost + penalty * len(plan.purchases))
    return best


def test_penalty_breakpoint_dp_matches_bruteforce():
    random.seed(20261001)
    checked = 0
    for _ in range(150):
        total = random.choice([300, 500, 700, 900])
        positions = random.sample(range(10, total, 10), random.randint(1, 10))
        candidates = [
            Candidate(i, m, round(random.uniform(2.7, 4.5), 3)) for i, m in enumerate(positions)
        ]
        for rng in [500, 1000]:
            for penalty in [0, 2, 5, 15]:
                try:
                    actual = plan_refuelling(candidates, total, rng, 10, rng / 10, penalty)
                except InfeasibleRoute:
                    continue
                assert actual.total_cost + penalty * len(actual.purchases) == pytest.approx(
                    brute(candidates, total, rng, penalty), abs=0.01
                )
                checked += 1
    assert checked >= 1000
