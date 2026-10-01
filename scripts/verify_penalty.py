"""Compare the stop-penalty heuristic with a brute-force subset oracle."""
import itertools,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from routing.optimizer import Candidate,InfeasibleRoute,plan_refuelling

def run():
 random.seed(20261001); cases=0; mismatches=0; largest=0.0
 for _ in range(300):
  total=random.choice([300,500,700,900]); c=[Candidate(i,random.randint(1,total-1),round(random.uniform(2.7,4.5),3)) for i in range(random.randint(1,10))]
  # distinct positions make subset semantics unambiguous
  c=list({x.mile:x for x in c}.values())
  for penalty in [0,2,5,15]:
   try: actual=plan_refuelling(c,total,500,10,50,penalty)
   except InfeasibleRoute: continue
   best=1e99
   for mask in range(1<<len(c)):
    subset=[x for i,x in enumerate(c) if mask>>i&1]
    try: p=plan_refuelling(subset,total,500,10,50,0)
    except InfeasibleRoute: continue
    best=min(best,p.total_cost+penalty*len(p.purchases))
   objective=actual.total_cost+penalty*len(actual.purchases); gap=max(0.0,objective-best); cases+=1
   if gap>0.01: mismatches+=1; largest=max(largest,gap)
 print(f'cases={cases} mismatches={mismatches} mismatch_rate={mismatches/cases:.4%} largest_cost_gap=${largest:.2f}')
if __name__=='__main__': run()


