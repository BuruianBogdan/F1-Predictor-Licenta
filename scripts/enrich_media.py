import argparse,json,re
import _bootstrap
from data_sources.openf1_provider import OpenF1Provider
from database.db import SessionLocal
from models.driver import Driver
from models.analytics import DriverMedia
from services.season_service import iso,utcnow
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--session-key',type=int,required=True);a=p.parse_args()
    rows=OpenF1Provider().fetch_drivers(a.session_key);count=0
    with SessionLocal.begin() as s:
        for raw in rows:
            d=s.query(Driver).filter_by(code=raw.get('name_acronym')).first()
            if not d: continue
            media=s.get(DriverMedia,d.driver_id) or DriverMedia(driver_id=d.driver_id)
            url=raw.get('headshot_url');color=raw.get('team_colour','')
            if media.source!='formula1_hd':
                media.image_url=url if url and url.startswith('https://') else None
                media.source='openf1'
            media.team_color='#'+color if re.fullmatch('[0-9A-Fa-f]{6}',color or '') else None
            media.updated_at=iso(utcnow());s.add(media);count+=1
    print(json.dumps({'updated':count}))
