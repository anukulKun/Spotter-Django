"""Pure minimum-cost refuelling optimizer. This module does not import Django."""
from __future__ import annotations

from dataclasses import dataclass

EPS = 1e-6


class InfeasibleRoute(Exception):
    def __init__(self, gap_start_mile: float, gap_end_mile: float, range_miles: float):
        self.gap_start_mile = gap_start_mile
        self.gap_end_mile = gap_end_mile
        self.range_miles = range_miles
        super().__init__(
            f"No fuel station reachable between mile {gap_start_mile:.0f} and mile "
            f"{gap_end_mile:.0f} (gap {gap_end_mile - gap_start_mile:.0f} mi > range {range_miles:.0f} mi)"
        )


@dataclass(frozen=True)
class Candidate:
    station_id: int
    mile: float
    price: float


@dataclass(frozen=True)
class Purchase:
    station_id: int
    mile: float
    price: float
    gallons: float
    cost: float
    arrival_gallons: float
    reason: str


@dataclass(frozen=True)
class Plan:
    purchases: list
    gallons_purchased: float
    gallons_consumed: float
    ending_gallons: float
    total_cost: float


def plan_refuelling(candidates, total_miles, range_miles=500.0, mpg=10.0, start_gallons=None):
    tank = range_miles / mpg
    fuel = tank if start_gallons is None else min(float(start_gallons), tank)
    stops = sorted((c for c in candidates if -EPS <= c.mile <= total_miles + EPS), key=lambda c: c.mile)
    destination = Candidate(-1, total_miles, 0.0)
    nodes = stops + [destination]
    first_leg = nodes[0].mile
    if first_leg > fuel * mpg + EPS:
        raise InfeasibleRoute(0.0, first_leg, fuel * mpg)
    fuel -= first_leg / mpg
    purchases, cost_total, bought = [], 0.0, 0.0
    for i, node in enumerate(nodes[:-1]):
        nxt = nodes[i + 1]
        if nxt.mile - node.mile > range_miles + EPS:
            raise InfeasibleRoute(node.mile, nxt.mile, range_miles)
        arrival = fuel
        cheaper = None
        for ahead in nodes[i + 1:]:
            if ahead.mile - node.mile > range_miles + EPS:
                break
            if ahead.price <= node.price + EPS:
                cheaper = ahead
                break
        if cheaper is not None:
            need = (cheaper.mile - node.mile) / mpg
            buy = max(0.0, need - fuel)
            reason = "buy just enough to reach a cheaper stop ahead" if cheaper.station_id != -1 else "buy just enough to reach destination"
        else:
            buy = tank - fuel
            reason = "cheapest in range ahead: fill tank"
        buy = max(buy, (nxt.mile - node.mile) / mpg - fuel, 0.0)
        buy = min(buy, tank - fuel)
        if buy > EPS:
            purchases.append(Purchase(node.station_id, node.mile, node.price, buy, buy * node.price, arrival, reason))
            cost_total += buy * node.price
            bought += buy
            fuel += buy
        fuel -= (nxt.mile - node.mile) / mpg
        if fuel < -EPS:
            raise InfeasibleRoute(node.mile, nxt.mile, range_miles)
    return Plan(purchases, bought, total_miles / mpg, max(fuel, 0.0), cost_total)
