import json,uuid,logging
from config import DATA_DIR
from database.db import SessionLocal
from models.analytics import PredictionRun,SprintResult
from models.race import Race
from models.race_result import RaceResult
from services.season_service import utcnow,iso,parse_time,race_start

class HistoryService:
    def record(self,kind,race_id,predictions,meta=None):
        meta=meta or {};run_id=uuid.uuid4().hex
        with SessionLocal.begin() as s:
            run=PredictionRun(id=run_id,kind=kind,race_id=race_id,created_at=iso(utcnow()),predictions=predictions,meta=meta,
                model_version=meta.get('model_version'),training_cutoff=meta.get('training_cutoff'),feature_cutoff=meta.get('feature_cutoff'),feature_mode=meta.get('mode'),
                market_enabled=int(meta.get('market_factor_used',False)),odds_snapshot_id=meta.get('odds_snapshot_id'),replay=int(meta.get('historical_replay',False)))
            s.add(run)
        return run_id
    def list_history(self,limit=200):
        with SessionLocal() as s:
            rows=s.query(PredictionRun).order_by(PredictionRun.created_at.desc()).limit(limit).all()
            out=[{'id':r.id,'kind':r.kind,'race_id':r.race_id,'created_at':r.created_at,'predictions':r.predictions,'meta':r.meta,'accuracy':r.accuracy,'model_version':r.model_version,'historical_replay':bool(r.replay),'valid_for_prospective_accuracy':not bool(r.replay)} for r in rows]
        path=DATA_DIR/'prediction_history.json'
        if path.exists() and len(out)<limit:
            try:
                legacy=json.loads(path.read_text())
                for r in reversed(legacy):
                    r={**r,'kind':'legacy_unvalidated','accuracy':None,'historical_replay':True,'valid_for_prospective_accuracy':False,'meta':{'warning':'Original engine used target and future outcomes; excluded from accuracy'}}
                    out.append(r)
                    if len(out)>=limit:break
            except (OSError,ValueError):logging.getLogger(__name__).exception('Legacy history unreadable')
        return out
    def evaluate_all(self):
        evaluated=0;skipped=0
        with SessionLocal.begin() as s:
            for run in s.query(PredictionRun).all():
                race=s.get(Race,run.race_id) if run.race_id else None
                target_start=parse_time(race.sprint_at) if race and run.kind=='sprint' else race_start(race) if race else None
                if not race or not target_start or target_start>utcnow() or not run.predictions or run.kind in ('champion','scenario'):skipped+=1;continue
                if run.kind=='sprint':results=s.query(SprintResult).filter_by(race_id=race.race_id).all()
                elif race.results_verified:results=s.query(RaceResult).filter_by(race_id=race.race_id).all()
                else:skipped+=1;continue
                actual={r.driver_id:r.position for r in results if r.position}
                preds=run.predictions;errors=[abs(actual[p['driver_id']]-p['predicted_position']) for p in preds if p['driver_id'] in actual]
                if not errors:skipped+=1;continue
                ordered=sorted(preds,key=lambda p:p['predicted_position']);podium={d for d,p in actual.items() if p<=3}
                prospective=not run.replay and parse_time(run.created_at)<target_start
                run.accuracy={'target':'SPRINT' if run.kind=='sprint' else 'RACE','top1_hit':actual.get(ordered[0]['driver_id'])==1,'top3_hit':len({p['driver_id'] for p in ordered[:3]}&podium),'average_position_error':sum(errors)/len(errors),
                    'prospective':prospective,'evaluation_type':'prospective' if prospective else 'historical_replay','evaluated_at':iso(utcnow())};evaluated+=1
        return {'message':f'Evaluated {evaluated} runs; historical replays are labelled separately.','evaluated':evaluated,'skipped':skipped}
