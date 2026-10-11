"""Rebuild bundled circuit SVG paths from the attributed public GeoJSON dataset.
Run from the repository root. Downloads only the source geometry and MIT license.
"""
from pathlib import Path
import json,sqlite3,math,shutil
import requests
cache=Path("backend-python/data/cache/design");cache.mkdir(parents=True,exist_ok=True)
for name,url in [("circuits.txt","https://raw.githubusercontent.com/bacinger/f1-circuits/master/f1-circuits.geojson"),("circuit-license.txt","https://raw.githubusercontent.com/bacinger/f1-circuits/master/LICENSE.md")]:
    if not (cache/name).exists():
        response=requests.get(url,timeout=30);response.raise_for_status();(cache/name).write_text(response.text)
root=Path.cwd();source=json.loads((root/'backend-python/data/cache/design/circuits.txt').read_text())
with sqlite3.connect(root/'database/f1.db') as c:circuits=c.execute('SELECT circuit_ref,name,lat,lng FROM circuits').fetchall()
assets={}
for ref,name,lat,lon in circuits:
    def distance(feature):
        pts=feature['geometry']['coordinates'];cx=sum(p[0] for p in pts)/len(pts);cy=sum(p[1] for p in pts)/len(pts)
        return math.hypot((lon-cx)*math.cos(math.radians(lat)),lat-cy)*111
    f=min(source['features'],key=distance)
    if distance(f)>10:print('UNMATCHED',ref,distance(f));continue
    pts=f['geometry']['coordinates'];cos=math.cos(math.radians(lat));xy=[(p[0]*cos,-p[1]) for p in pts]
    minx=min(p[0] for p in xy);miny=min(p[1] for p in xy);width=max(p[0] for p in xy)-minx;height=max(p[1] for p in xy)-miny
    scale=min(440/width,240/height);dx=(500-width*scale)/2;dy=(300-height*scale)/2
    coords=[(round((x-minx)*scale+dx,2),round((y-miny)*scale+dy,2)) for x,y in xy]
    path='M'+' L'.join(f'{x},{y}' for x,y in coords)
    props=f['properties'];assets[ref]={'path':path,'length_km':round(props['length']/1000,3),'opened':props.get('opened'),'layout_id':props['id'],'source':'bacinger/f1-circuits (MIT)','source_url':'https://github.com/bacinger/f1-circuits','start_x':coords[0][0],'start_y':coords[0][1]}
target=root/'backend-python/resources';target.mkdir(exist_ok=True);(target/'circuit_layouts.json').write_text(json.dumps(assets,indent=2)+'\n')
shutil.copy2(root/'backend-python/data/cache/design/circuit-license.txt',target/'CIRCUIT_LICENSE.txt')
print('Generated exact vector outlines:',len(assets))
