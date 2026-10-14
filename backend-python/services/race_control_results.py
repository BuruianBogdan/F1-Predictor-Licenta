"""Published result evidence shared by winner confirmation and projections.

The existing versioned weekend table records our observation time, not an
invented upstream publication time. Legacy results can describe a verified
historical outcome but cannot establish a contemporaneous replay baseline.
"""
from data_sources.timing_contract import utc_stamp,utc_iso
from models.weekend import WeekendSessionSnapshot
from models.race import Race
from models.race_result import RaceResult
from models.analytics import SprintResult
from models.driver import Driver
from database.db import SessionLocal

TRUSTED={'formula1_official','jolpica','jolpica_f1'}


def published_at(db,race_id,session,at):
    records=db.query(WeekendSessionSnapshot).filter_by(race_id=race_id,session=session).order_by(WeekendSessionSnapshot.id.desc()).all()
    eligible=[r for r in records if r.source in TRUSTED and utc_stamp(r.observed_at) is not None and utc_stamp(r.observed_at)<=at and utc_stamp(r.session_end_at) is not None and utc_stamp(r.session_end_at)<=at]
    return (eligible[0] if eligible else None),bool(records)


def confirm_result(race_id,frame,mode):
    leader=next((r for r in frame['rows'] if r.get('position')==1),None)
    finished=frame['phase']=='FINISHED'
    evidence={'status':'PROVISIONAL_P1' if finished and leader else 'SESSION_FINISHED' if finished else 'LIVE_LEADER' if leader else 'WAITING',
              'leader':leader,'source':None,'observed_at':None,'winner_confirmed':False,
              'session_finished':finished,'result_published':False,'result_verified':False}
    frame['winner']=None
    if not finished:return evidence
    code='SPRINT' if frame['racing'] and frame['meta']['session_name']=='Sprint' else 'R' if frame['racing'] else frame['meta'].get('code')
    with SessionLocal() as db:
        race=db.get(Race,race_id)
        if not race or race.race_status=='CANCELLED':
            evidence.update(status='SESSION_CANCELLED',leader=None);return evidence
        observation,has_versions=published_at(db,race_id,code,frame['at'])
        published=observation.data if observation else None
        legacy=False
        if published is None and has_versions and mode=='REPLAY':
            # The final replay transition is an outcome view, not a temporal feature.
            latest=db.query(WeekendSessionSnapshot).filter_by(race_id=race_id,session=code).order_by(WeekendSessionSnapshot.id.desc()).first()
            if latest.source in TRUSTED:published=latest.data;observation=latest;legacy=True
        if published is None and not has_versions and mode=='REPLAY':
            # Explicitly historical latest-result view, never a replay-time feature.
            if code=='R' and race.results_verified:
                results=db.query(RaceResult).filter_by(race_id=race_id).all()
                if results and all(r.source in TRUSTED for r in results):
                    published=[{'driver_id':r.driver_id,'position':r.position} for r in results];legacy=True
            elif code=='SPRINT':
                results=db.query(SprintResult).filter_by(race_id=race_id).all()
                if results and all(utc_stamp(r.available_at) is not None and utc_stamp(r.available_at)<=frame['at'] for r in results):
                    published=[{'driver_id':r.driver_id,'position':r.position} for r in results];legacy=True
        if published is None:return evidence
        evidence.update(status='RESULT_PUBLISHED',result_published=True,source=observation.source_url if observation else 'Verified local published classification',
                        observed_at=observation.observed_at if observation else None,verification_scope='HISTORICAL_LATEST' if legacy else 'OBSERVED_AT_CUTOFF',
                        note='Verified historical result; latest published outcome, not evidence of availability at the replay cutoff.' if legacy else 'Published classification observed at or before the selected cutoff.')
        first=[r for r in published if r.get('position')==1]
        if len(first)!=1:return evidence
        result=first[0];driver=db.get(Driver,result.get('driver_id')) if result.get('driver_id') else None
        code_value=(driver.code if driver else result.get('driver_code'))
        candidates=[r for r in frame['rows'] if r.get('code')==code_value]
        if driver:
            from services.race_control_projection_service import normalized
            candidates=[r for r in candidates if normalized(r.get('name'))==normalized(f'{driver.forename} {driver.surname}')]
        if len(candidates)!=1:return evidence
        winner={**candidates[0],'position':1}
        frame['winner']=winner
        evidence.update(status='OFFICIAL_WINNER_CONFIRMED' if frame['racing'] else 'RESULT_VERIFIED',winner=winner,result_verified=True,winner_confirmed=True)
        return evidence
