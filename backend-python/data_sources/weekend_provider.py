"""Current published official classifications. No paid in-session timing feed required."""
import hashlib,json,re,time,unicodedata
from datetime import timedelta
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from data_sources.base_provider import ProviderError
from services.season_service import iso,parse_time,utcnow
BASE='https://www.formula1.com'
PATHS={'FP1':'practice/1','FP2':'practice/2','FP3':'practice/3','SQ':'sprint-qualifying','SPRINT':'sprint','Q':'qualifying','R':'race-result','SPRINT_GRID':'sprint-grid','RACE_GRID':'starting-grid'}
NAMES={'Practice 1':'FP1','Practice 2':'FP2','Practice 3':'FP3','Sprint Qualifying':'SQ','Sprint Shootout':'SQ','Sprint':'SPRINT','Qualifying':'Q','Race':'R'}

def normalized(text):return ''.join(c for c in unicodedata.normalize('NFKD',text or '').lower() if c.isalnum())
def seconds(text):
    text=(text or '').strip().replace('s','')
    if not re.fullmatch(r'\d+(?::\d+)?(?:\.\d+)?',text):return None
    pieces=text.split(':');return float(pieces[-1])+ (60*float(pieces[0]) if len(pieces)==2 else 0)
def number(text):
    try:return int(text)
    except (ValueError,TypeError):return None

def parse_schedule(html):
    soup=BeautifulSoup(html,'html.parser')
    for node in soup.select('script[type="application/ld+json"]'):
        try:data=json.loads(node.get_text())
        except ValueError:continue
        if not isinstance(data,dict) or data.get('@type')!='SportsEvent':continue
        sessions=[]
        for item in data.get('subEvent',[]):
            name=item.get('name','').split(' - ')[0];code=NAMES.get(name)
            if code and item.get('startDate'):
                start=parse_time(item['startDate']);end=parse_time(item.get('endDate')) or start+timedelta(hours=2)
                sessions.append({'code':code,'name':name,'start_at':iso(start),'end_at':iso(end)})
        if not any(x['code']=='R' for x in sessions):raise ProviderError('Official weekend schedule lacks a Grand Prix start')
        return {'name':data.get('name'), 'sessions':sessions}
    raise ProviderError('Official weekend schedule is unavailable')

def parse_classification(html,code):
    soup=BeautifulSoup(html,'html.parser');table=soup.find('table')
    if not table:return []
    heading=soup.h1.get_text(' ',strip=True).upper() if soup.h1 else ''
    label={'FP1':'PRACTICE 1','FP2':'PRACTICE 2','FP3':'PRACTICE 3','SQ':'SPRINT QUALIFYING','Q':'QUALIFYING','SPRINT':'SPRINT','R':'RACE RESULT','SPRINT_GRID':'SPRINT GRID','RACE_GRID':'STARTING GRID'}[code]
    if not heading.endswith(' - '+label):return []
    headers=[th.get_text(' ',strip=True).lower() for th in table.select('thead th')]
    if 'driver' not in headers or not any(h.startswith('pos') for h in headers):return []
    rows=[];leader_time=None
    for tr in table.select('tbody tr'):
        cells=[td.get_text(' ',strip=True) for td in tr.select('td')]
        if len(cells)!=len(headers):raise ProviderError('Incomplete official result row')
        raw=dict(zip(headers,cells));driver=raw['driver'];match=re.search(r'\b([A-Z]{3})\s*$',driver)
        if not match:raise ProviderError('Driver identity missing from official classification')
        position=number(next(v for k,v in raw.items() if k.startswith('pos')))
        row={'position':position,'driver_code':match.group(1),'source_driver_name':driver[:match.start()].strip(),'driver_number':number(raw.get('no.')),'team':raw.get('team'),'laps':number(raw.get('laps')),'best_lap_seconds':None,'time_text':None,'points':None,'status':'classified' if position else 'unclassified'}
        if code.startswith('FP'):
            value=raw.get('time / gap',raw.get('time',''));row['time_text']=value
            if value.startswith('+') and leader_time is not None:row['best_lap_seconds']=leader_time+(seconds(value[1:]) or 0) if seconds(value[1:]) is not None else None
            else:row['best_lap_seconds']=seconds(value)
            if position==1:leader_time=row['best_lap_seconds']
        elif code in ('Q','SQ'):
            values=[raw.get(k,'') for k in ('q1','q2','q3')];valid=[v for v in values if seconds(v) is not None]
            row['segments']=dict(zip(('q1','q2','q3'),values));row['time_text']=valid[-1] if valid else None;row['best_lap_seconds']=seconds(row['time_text'])
        elif code in ('SPRINT','R'):
            row['time_text']=raw.get('time / retired',raw.get('time / gap',raw.get('time')))
            try:row['points']=float(raw.get('pts',raw.get('points','')))
            except ValueError:raise ProviderError('Official race classification has no points field')
            if row['time_text'] in ('DNF','DSQ','DNS','NC'):row['status']=row['time_text']
        rows.append(row)
    positions=[r['position'] for r in rows if r['position']]
    if len(positions)!=len(set(positions)) or len({r['driver_code'] for r in rows})!=len(rows):raise ProviderError('Duplicate classification positions or driver identities')
    return rows

class OfficialWeekendProvider:
    name='formula1_official'
    def __init__(self,http=None):self.http=http or requests.Session()
    def get(self,url):
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.netloc!='www.formula1.com':raise ValueError('Only official Formula 1 pages are supported')
        time.sleep(.25)
        try:
            response=self.http.get(url,headers={'User-Agent':'F1Predictor/2.0 (university research)'},timeout=(5,25));response.raise_for_status();return response.text
        except requests.RequestException as exc:raise ProviderError('Official results could not be reached; previous observations retained') from exc
    def resolve(self,race,circuit):
        soup=BeautifulSoup(self.get(f'{BASE}/en/results/{race.season_year}/races'),'html.parser');candidates={}
        for a in soup.select('a[href]'):
            match=re.fullmatch(r'/en/results/'+str(race.season_year)+r'/races/\d+/([^/]+)/[^?]+',a['href'])
            if match:candidates[match.group(1)]=BASE+a['href'].rsplit('/',1)[0]
        key=normalized(race.race_name);country=normalized(circuit.country if circuit else '')
        aliases={'silverstone':'great-britain','catalunya':'barcelona-catalunya','interlagos':'brazil','imola':'emilia-romagna','americas':'united-states','vegas':'las-vegas'}
        circuit_alias=aliases.get(circuit.circuit_ref if circuit else '')
        scored=[((100+len(normalized(slug))) if key.startswith(normalized(slug)) else (90 if slug==circuit_alias else (len(normalized(slug)) if normalized(slug) in key else (1 if normalized(slug)==country else 0))),slug,base) for slug,base in candidates.items()]
        best=sorted(scored,reverse=True)
        if not best or not best[0][0] or (len(best)>1 and best[0][0]==best[1][0]):raise ProviderError('Could not uniquely match the official event to this local race')
        _,slug,base=best[0];schedule=parse_schedule(self.get(f'{BASE}/en/racing/{race.season_year}/{slug}'))
        race_session=next(x for x in schedule['sessions'] if x['code']=='R')
        if parse_time(race_session['start_at']).date()!=race.date:raise ProviderError('Official event date differs from the selected race; synchronization required')
        schedule.update(source_url=f'{BASE}/en/racing/{race.season_year}/{slug}',results_base=base)
        return schedule
    def fetch(self,race,circuit,now=None):
        now=now or utcnow();schedule=self.resolve(race,circuit);collected=[];waiting=[];errors=[]
        for session in schedule['sessions']:
            code=session['code']
            if code=='R' or parse_time(session['end_at'])>now:
                waiting.append({'session':code,'reason':'not_finished'});continue
            url=schedule['results_base']+'/'+PATHS[code]
            try:
                rows=parse_classification(self.get(url),code)
                if not rows:waiting.append({'session':code,'reason':'not_published'});continue
                collected.append({**session,'source_url':url,'source':self.name,'rows':rows})
            except ProviderError as exc:errors.append({'session':code,'message':str(exc)})
        for qualifying,grid,target in [('SQ','SPRINT_GRID','SPRINT'),('Q','RACE_GRID','R')]:
            if not any(x['code']==qualifying for x in collected):continue
            race_session=next((x for x in schedule['sessions'] if x['code']==target),None)
            if not race_session:continue
            url=schedule['results_base']+'/'+PATHS[grid]
            try:
                rows=parse_classification(self.get(url),grid)
                if rows:collected.append({'code':grid,'name':grid.replace('_',' ').title(),'start_at':next(x['start_at'] for x in schedule['sessions'] if x['code']==qualifying),'end_at':next(x['end_at'] for x in schedule['sessions'] if x['code']==qualifying),'source_url':url,'source':self.name,'rows':rows})
            except ProviderError:pass # Grid may be published later; qualifying remains explicitly provisional.
        return {'schedule':schedule,'sessions':collected,'waiting':waiting,'errors':errors}
