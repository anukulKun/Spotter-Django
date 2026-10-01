import numpy as np
from routing.geo import densify

def test_densify_vectorized_matches_reference():
    lat=np.array([32.8,35.0,38.9]); lon=np.array([-96.8,-90.0,-87.6])
    old_lat=[lat[0]]; old_lon=[lon[0]]
    from routing.geo import haversine_miles
    import math
    for i in range(1,len(lat)):
        n=max(1,int(math.ceil(float(haversine_miles(lat[i-1],lon[i-1],lat[i],lon[i])))))
        for k in range(1,n+1):
            t=k/n; old_lat.append(lat[i-1]+t*(lat[i]-lat[i-1])); old_lon.append(lon[i-1]+t*(lon[i]-lon[i-1]))
    new_lat,new_lon=densify(lat,lon,1)
    assert np.allclose(new_lat,old_lat,atol=1e-6) and np.allclose(new_lon,old_lon,atol=1e-6)
