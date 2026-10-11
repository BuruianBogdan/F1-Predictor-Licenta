import os,json
from collections import defaultdict
from datetime import timedelta
from config import MARKET_ENABLED,MARKET_ODDS_WEIGHT,USE_SELENIUM_ODDS
from database.db import SessionLocal
from models.analytics import OddsSnapshot
from models.race import Race
from services.odds.normalization import normalize
from services.odds.providers.manual_provider import ManualOddsProvider
from services.season_service import utcnow,iso,parse_time,race_start

class OddsService:
    def store(self,race_id,rows,captured_at=None):
        if not rows:return []
        by_provider=defaultdict(list)
        for row in rows:by_provider[row.get('provider','manual')].append(row)
        ids=[]
        with SessionLocal.begin() as s:
            for provider,values in by_provider.items():
                latest=max((parse_time(v.get('captured_at')) or parse_time(captured_at) or utcnow()) for v in values)
                snapshot=OddsSnapshot(race_id=race_id,provider=provider,captured_at=iso(latest),source_url=values[0].get('source_url'),data=values);s.add(snapshot);s.flush();ids.append(snapshot.id)
        return ids
    def adjust(self,response,rows,captured_at=None):
        if not MARKET_ENABLED or not rows:
            response['market_factor_used']=False;response['market_note']='No market data; model probabilities unchanged';return response
        rows=ManualOddsProvider(rows).fetch_race_odds(response)
        fair=normalize(rows,{p['driver_id'] for p in response['predictions']})
        with SessionLocal() as s:race=s.get(Race,response['race_id'])
        deadline=(parse_time(race.weekend_at) or race_start(race)-timedelta(days=2)) if response['mode']=='PRE_WEEKEND' else race_start(race)
        captured=parse_time(captured_at) if captured_at else utcnow()
        cutoff=min(utcnow(),deadline,parse_time(response['feature_cutoff']))
        timestamps=[parse_time(row.get('captured_at')) or captured for row in rows]
        if any(stamp>cutoff for stamp in timestamps):raise ValueError('Odds were captured after the prediction-mode cutoff; supply a genuine pre-race snapshot')
        # Never hide a later quote behind an older batch timestamp.
        rows=[{**row,'captured_at':iso(stamp)} for row,stamp in zip(rows,timestamps)]
        captured=max(timestamps)
        ids=self.store(race.race_id,rows)
        mass=sum(p['win_probability'] for p in response['predictions'] if p['driver_id'] in fair)
        for p in response['predictions']:
            market=fair.get(p['driver_id']);model=p['win_probability']
            p['market_probability']=market*mass if market is not None else None
            p['final_probability']=(1-MARKET_ODDS_WEIGHT)*model+MARKET_ODDS_WEIGHT*market*mass if market is not None else model
            p['score_breakdown']['market']=p['final_probability']-model
        total=sum(p['final_probability'] for p in response['predictions'])
        response['predictions'].sort(key=lambda p:-p['final_probability'])
        for rank,p in enumerate(response['predictions'],1):
            p['final_probability']/=total;p['predicted_position_with_market']=rank;p['model_rank']=p['predicted_position'];p['predicted_position']=rank;p['rank']=rank
        response.update(market_factor_used=True,market_weight=MARKET_ODDS_WEIGHT,odds_snapshot_id=ids[0],odds_snapshot_ids=ids,market_data_cutoff=iso(captured),market_note='Partial books retain the model mass of unquoted drivers; supplied timestamps are user assertions, not independently verified.')
        return response
    def get(self,race_id):
        with SessionLocal() as s:rows=s.query(OddsSnapshot).filter_by(race_id=race_id).order_by(OddsSnapshot.id.desc()).all()
        latest={}
        for row in rows:
            if row.provider not in latest:latest[row.provider]=row
        ttl=int(os.getenv('ODDS_REFRESH_MINUTES','10'))*60
        snapshots=[{'id':r.id,'provider':r.provider,'captured_at':r.captured_at,'source_url':r.source_url,'odds':r.data,'stale':(utcnow()-parse_time(r.captured_at)).total_seconds()>ttl} for r in latest.values()]
        return {'race_id':race_id,'snapshots':snapshots,'last_refresh':rows[0].captured_at if rows else None,'stale':not snapshots or all(r['stale'] for r in snapshots)}
    def status(self):
        sources=json.loads(os.getenv('ODDS_SOURCES','[]'))
        return {'selenium_enabled':USE_SELENIUM_ODDS,'providers':[s.get('name') for s in sources],'manual':'available','real_providers_verified':[]}
    def refresh(self,race_id):
        cached=self.get(race_id)
        if not USE_SELENIUM_ODDS:return {**cached,'enabled':False,'providers_successful':[],'providers_failed':[]}
        if not cached['stale']:return {**cached,'cached':True}
        from services.odds.providers.selenium.base_selenium_provider import SeleniumOddsProvider
        from ml.feature_engineering import FeatureEngineeringService
        frame=FeatureEngineeringService().build(race_id)
        if parse_time(frame['race']['start_at'] or frame['race']['date'])<=utcnow():raise ValueError('Refresh is only available for future races')
        successful=[];failed=[]
        for source in json.loads(os.getenv('ODDS_SOURCES','[]')):
            try:
                odds=SeleniumOddsProvider(source,frame['rows']).fetch_race_odds(frame['race'])
                normalize(odds,{r['driver_id'] for r in frame['rows']})
                if not odds:raise ValueError('No public odds found')
                self.store(race_id,odds);successful.append(source['name'])
            except Exception as exc:failed.append({'provider':source.get('name'),'error':type(exc).__name__})
        return {**self.get(race_id),'providers_successful':successful,'providers_failed':failed}
