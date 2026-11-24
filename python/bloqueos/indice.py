import numpy as np

LATS = np.arange(30, 65.1, 2.5)
LONS = np.arange(-180, 180, 2.5)
DELTAS = [0, -2.5, -5, -7.5, -10]
SECTORS = {"PSW":(-180,-120),"PSE":(-120,-80),"ATL":(-80,10),"IND":(10,100),"OCN":(100,180)}

def diagnose(z):
    z = np.asarray(z, dtype=float)
    if z.shape != (len(LATS),len(LONS)) or not np.isfinite(z).all():
        raise ValueError("Campo Z500 incompleto")
    rows = []
    for j, lon in enumerate(LONS):
        values = []
        for d in DELTAS:
            a,b,c,e = [float(z[int((lat+d-30)/2.5),j]) for lat in (40,55,50,65)]
            n,s = b-a,e-c
            values.append(dict(delta=d,z=[a,b,c,e],ghgn=n,ghgs=s,blocked=n>0 and s<-10))
        rows.append(dict(lon=float(lon),blocked=any(v["blocked"] for v in values),details=values))
    sectors = {}
    for name,(lo,hi) in SECTORS.items():
        flags = [r["blocked"] for r in rows if lo <= r["lon"] < hi]
        sectors[name] = any(all(flags[i:i+3]) for i in range(len(flags)-2))
    return dict(rows=rows,sectors=sectors)
