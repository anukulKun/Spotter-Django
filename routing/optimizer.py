"""Pure refuelling optimizers; no Django or network dependencies."""
from __future__ import annotations
from dataclasses import dataclass
EPS=1e-6
class InfeasibleRoute(Exception):
    def __init__(self,gap_start_mile,gap_end_mile,range_miles):
        self.gap_start_mile=gap_start_mile; self.gap_end_mile=gap_end_mile; self.range_miles=range_miles
        super().__init__(f"No fuel station reachable between mile {gap_start_mile:.0f} and mile {gap_end_mile:.0f} (gap {gap_end_mile-gap_start_mile:.0f} mi > range {range_miles:.0f} mi)")
@dataclass(frozen=True)
class Candidate: station_id:int; mile:float; price:float
@dataclass(frozen=True)
class Purchase: station_id:int; mile:float; price:float; gallons:float; cost:float; arrival_gallons:float; reason:str
@dataclass(frozen=True)
class Plan: purchases:list; gallons_purchased:float; gallons_consumed:float; ending_gallons:float; total_cost:float

def _greedy(candidates,total_miles,range_miles=500.0,mpg=10.0,start_gallons=None):
    tank=range_miles/mpg; fuel=tank if start_gallons is None else min(float(start_gallons),tank)
    stops=sorted((c for c in candidates if -EPS<=c.mile<=total_miles+EPS),key=lambda c:c.mile); nodes=stops+[Candidate(-1,total_miles,0.0)]
    first_leg=nodes[0].mile
    if first_leg>fuel*mpg+EPS: raise InfeasibleRoute(0.0,first_leg,fuel*mpg)
    fuel-=first_leg/mpg; purchases=[]; cost_total=0.0; bought=0.0
    for i,node in enumerate(nodes[:-1]):
        nxt=nodes[i+1]
        if nxt.mile-node.mile>range_miles+EPS: raise InfeasibleRoute(node.mile,nxt.mile,range_miles)
        arrival=fuel; cheaper=None
        for ahead in nodes[i+1:]:
            if ahead.mile-node.mile>range_miles+EPS: break
            if ahead.price<=node.price+EPS: cheaper=ahead; break
        if cheaper is not None:
            need=(cheaper.mile-node.mile)/mpg; buy=max(0.0,need-fuel)
            reason="buy just enough to reach a cheaper stop ahead" if cheaper.station_id!=-1 else "buy just enough to reach destination"
        else:
            buy=tank-fuel; reason="lowest price within range ahead: top up to full"
        buy=min(max(buy,(nxt.mile-node.mile)/mpg-fuel,0.0),tank-fuel)
        if buy>EPS:
            purchases.append(Purchase(node.station_id,node.mile,node.price,buy,buy*node.price,arrival,reason)); cost_total+=buy*node.price; bought+=buy; fuel+=buy
        fuel-=(nxt.mile-node.mile)/mpg
        if fuel<-EPS: raise InfeasibleRoute(node.mile,nxt.mile,range_miles)
    return Plan(purchases,bought,total_miles/mpg,max(fuel,0.0),cost_total)

def _penalty_dp(candidates,total_miles,range_miles,mpg,start_gallons,penalty):
    """Exact finite-breakpoint DP for fuel cost plus a per-purchase penalty."""
    tank=range_miles/mpg; start=tank if start_gallons is None else min(float(start_gallons),tank)
    stops=sorted((c for c in candidates if -EPS<=c.mile<=total_miles+EPS),key=lambda c:c.mile)
    dest=len(stops); nodes=stops+[Candidate(-1,total_miles,0.0)]
    states=[{} for _ in stops]; best_dest=None
    def key(x): return round(float(x),10)
    def consider(j,arrival,obj,prev_i,prev_fuel,q):
        k=key(arrival)
        if j==dest:
            nonlocal best_dest
            if best_dest is None or obj<best_dest[0]-EPS: best_dest=(obj,prev_i,prev_fuel,q,arrival)
        elif arrival>=-EPS and arrival<=tank+EPS:
            old=states[j].get(k)
            if old is None or obj<old[0]-EPS: states[j][k]=(obj,prev_i,prev_fuel,q)
    # Leaving the origin has one fixed fuel level and no purchase.
    for j,node in enumerate(nodes):
        d=node.mile
        if d<=start*mpg+EPS: consider(j,start-d/mpg,0.0,None,None,start)
    for i,node in enumerate(stops):
        if not states[i]: continue
        later=nodes[i+1:]
        breakpoints={tank}
        for nxt in later:
            d=nxt.mile-node.mile
            if d<=range_miles+EPS: breakpoints.add(max(0.0,d/mpg))
        for arrival,entry in list(states[i].items()):
            arrival=float(arrival); base=entry[0]
            choices=breakpoints|{arrival}
            for depart in choices:
                if depart+EPS<arrival or depart>tank+EPS: continue
                for j,nxt in enumerate(nodes[i+1:],start=i+1):
                    d=nxt.mile-node.mile
                    if d>range_miles+EPS: break
                    after=depart-d/mpg
                    if after<-EPS: continue
                    bought=max(0.0,depart-arrival)
                    obj=base+(bought*node.price)+(penalty if bought>EPS else 0.0)
                    consider(j,after,obj,i,arrival,depart)
    if best_dest is None: return _greedy(stops,total_miles,range_miles,mpg,start_gallons)
    transitions=[]; i=best_dest[1]; arrival=best_dest[2]; depart=best_dest[3]; ending=best_dest[4]
    while i is not None:
        transitions.append((i,float(arrival),float(depart)))
        entry=states[i][key(arrival)]; prev_i=entry[1]; prev_arrival=entry[2]; prev_depart=entry[3]
        i=prev_i; arrival=prev_arrival; depart=prev_depart
    transitions.reverse(); purchases=[]; bought_total=0.0; fuel_cost=0.0
    for pos,(i,arrival,depart) in enumerate(transitions):
        gallons=max(0.0,depart-arrival)
        if gallons<=EPS: continue
        node=stops[i]; next_mile=total_miles if pos+1==len(transitions) else stops[transitions[pos+1][0]].mile
        if abs(depart-tank)<=EPS: reason="lowest price within range ahead: top up to full"
        elif abs(depart-(next_mile-node.mile)/mpg)<=1e-5 and next_mile>=total_miles-EPS: reason="buy just enough to reach destination"
        else: reason="buy just enough to reach a cheaper stop ahead"
        purchases.append(Purchase(node.station_id,node.mile,node.price,gallons,gallons*node.price,arrival,reason)); bought_total+=gallons; fuel_cost+=gallons*node.price
    return Plan(purchases,bought_total,total_miles/mpg,max(ending,0.0),fuel_cost)

def plan_refuelling(candidates,total_miles,range_miles=500.0,mpg=10.0,start_gallons=None,stop_penalty_usd=0.0):
    candidates=list(candidates)
    if stop_penalty_usd<=EPS: return _greedy(candidates,total_miles,range_miles,mpg,start_gallons)
    return _penalty_dp(candidates,total_miles,range_miles,mpg,start_gallons,float(stop_penalty_usd))
