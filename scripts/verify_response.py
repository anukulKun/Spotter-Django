"""Independent response checker: python scripts/verify_response.py response.json"""
import csv,json,sys
from pathlib import Path
TOL=.01
def fail(name,msg): print(f'FAIL {name}: {msg}'); return False
def main(path):
 b=json.loads(Path(path).read_text(encoding='utf-8-sig')); rows={int(r['opis_id']):r for r in csv.DictReader(open(Path(__file__).parents[1]/'data/stations_geocoded.csv',newline='',encoding='utf-8-sig'))}; ok=True; stops=sorted(b.get('fuel_stops',[]),key=lambda x:x['mile_marker']); total=b['route']['distance_miles']; rng=b['vehicle']['range_miles']; mpg=b['vehicle']['mpg']; tank=b['vehicle']['tank_gallons']; fuel=b['vehicle']['starting_fuel_gallons']; prev=0
 ok &= not stops or all(stops[i]['mile_marker']<=stops[i+1]['mile_marker'] for i in range(len(stops)-1)) or fail('sorted','mile markers')
 for s in stops:
  if s['mile_marker']-prev>rng+TOL: ok=fail('range',f'{prev}->{s["mile_marker"]}') and ok
  if int(s['station_id']) not in rows: ok=fail('station',s['station_id']) and ok
  else:
   if abs(float(rows[int(s['station_id'])]['price'])-s['price_per_gallon_usd'])>TOL: ok=fail('price',s['station_id']) and ok
  if s['distance_from_route_miles']>b['meta']['corridor_miles_used']+TOL: ok=fail('corridor',s['station_id']) and ok
  if fuel< -TOL or fuel>tank+TOL: ok=fail('tank','before stop') and ok
  fuel-= (s['mile_marker']-prev)/mpg; fuel+=s['gallons_purchased'];
  if fuel< -TOL or fuel>tank+TOL: ok=fail('tank',s['station_id']) and ok
  prev=s['mile_marker']
 fuel-= (total-prev)/mpg
 if total-prev>rng+TOL: ok=fail('range',f'{prev}->{total}') and ok
 if fuel< -TOL or fuel>tank+TOL: ok=fail('tank','finish') and ok
 s=b['summary']; costs=sum(x['cost_usd'] for x in stops)
 if abs(s['total_fuel_cost_usd']-costs)>TOL: ok=fail('cost',f'{s["total_fuel_cost_usd"]}!={costs}') and ok
 if abs(b['vehicle']['starting_fuel_gallons']+s['gallons_purchased']-s['gallons_consumed']-s['ending_fuel_gallons'])>TOL: ok=fail('conservation','mismatch') and ok
 print('PASS all checks' if ok else 'FAIL one or more checks'); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main(sys.argv[1]))

