"""Discover current driver portraits on the official public driver directory."""
import json,re,unicodedata
import requests
from bs4 import BeautifulSoup
import _bootstrap
from database.db import SessionLocal
from models.driver import Driver
from models.analytics import DriverMedia
from services.season_service import iso,utcnow

def normalized(text):return ''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if c.isalnum())
def enrich():
    response=requests.get('https://www.formula1.com/en/drivers',timeout=30);response.raise_for_status()
    soup=BeautifulSoup(response.text,'html.parser');updated=[]
    with SessionLocal.begin() as s:
        drivers=s.query(Driver).all()
        for a in soup.select('a[href^="/en/drivers/"]'):
            img=a.select_one('img[alt][src]')
            if not img or not img['src'].startswith('https://media.formula1.com/'):continue
            name=normalized(img['alt']);matches=[d for d in drivers if name.endswith(normalized(d.surname or '')) and d.surname]
            exact=[d for d in matches if normalized((d.forename or '')+' '+d.surname)==name]
            if len(exact)==1:matches=exact
            if len(matches)!=1:continue
            d=matches[0]
            match=re.search(r'/v\d+/(common/f1/[^?#]+)',img['src'])
            if not match:continue
            # Reference the original asset, rather than upscaling OpenF1's thumbnail.
            url='https://media.formula1.com/image/upload/'+match.group(0).lstrip('/')
            media=s.get(DriverMedia,d.driver_id) or DriverMedia(driver_id=d.driver_id)
            media.image_url=url;media.source='formula1_hd';media.updated_at=iso(utcnow());s.add(media)
            updated.append({'driver_id':d.driver_id,'name':img['alt'],'url':url})
    return updated
if __name__=='__main__':print(json.dumps(enrich(),indent=2))
