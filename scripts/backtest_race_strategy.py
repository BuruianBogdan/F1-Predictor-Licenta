"""Chronological multi-cutoff evaluation of the unchanged experimental strategy.

No model fitting/tuning occurs here. Downloaded timing-only evaluation datasets
are separate from the application's complete position archives.
"""
import _bootstrap
import argparse,gzip,json,math,statistics,time
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
from database.db import SessionLocal
from models.race import Race
from models.analytics import PredictionRun
from data_sources.timing_contract import utc_stamp
from data_sources.race_control_provider import RaceControlProvider
from services.race_control_service import RaceControlService,TimingTimeline,time_extent,stamp
from services.race_strategy_service import RaceStrategyService
from services.prediction_service import PredictionService
from services.season_service import parse_time
from config import DATA_DIR

CUTOFFS=(.10,.25,.50,.75,.90)


def download(key):
    provider=RaceControlProvider();meta=next(iter(provider.fetch('sessions',{'session_key':key})),None)
    if not meta or meta['session_type']!='Race':raise ValueError('Historical race session required')
    meta['circuit_length_km']=5.
    data={'meta':meta,'drivers':RaceControlService().enrich_drivers(provider.fetch('drivers',{'session_key':key})),
          'events':{},'locations':{},'telemetry':{},'track':None,'complete_archive':True,'downloaded_at':datetime.now(timezone.utc).isoformat()}
    for endpoint in ('laps','position','intervals','stints','weather','race_control','pit','session_result'):
        print(f'{key}: {endpoint}',flush=True);data['events'][endpoint]=provider.fetch(endpoint,{'session_key':key})
    time_extent(data);data['coverage_end']=stamp(data['meta']['timeline_end'])+300
    directory=DATA_DIR/'cache/race-control/backtesting';directory.mkdir(parents=True,exist_ok=True)
    with gzip.open(directory/f'{key}.json.gz','wt') as stream:json.dump(data,stream,separators=(',',':'))
    return data


def metrics(samples):
    if not samples:return {'samples':0}
    top1=top3=0;brier=[];loss=[];bins=defaultdict(list)
    for probabilities,winner in samples:
        # Zero-probability ties do not become a fabricated second/third pick
        # for a one-hot leader/pace baseline.
        ranked=sorted((n for n,p in probabilities.items() if p>0),key=lambda n:-probabilities[n]);top1+=ranked[0]==winner;top3+=winner in ranked[:3]
        brier.append(sum((p-float(n==winner))**2 for n,p in probabilities.items()))
        loss.append(-math.log(max(1e-12,probabilities.get(winner,0))))
        confidence=probabilities[ranked[0]];bins[min(9,int(confidence*10))].append((confidence,float(ranked[0]==winner)))
    ece=sum(len(values)/len(samples)*abs(statistics.mean(x[0] for x in values)-statistics.mean(x[1] for x in values)) for values in bins.values())
    return {'samples':len(samples),'top1':top1/len(samples),'top3':top3/len(samples),
            'multiclass_brier':statistics.mean(brier),'log_loss':statistics.mean(loss),'top_label_ece_10_bins':ece}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--keys',default='11731,11383,9644,9662');parser.add_argument('--download',action='store_true')
    parser.add_argument('--output',default='docs/evaluation/LIVE_BACKTEST_RESULTS.json');args=parser.parse_args()
    methods=defaultdict(list);changes=defaultdict(list);records=[];latencies=[];payloads=[];issues=[]
    for key in map(int,args.keys.split(',')):
        data=RaceControlService().load(key);file=DATA_DIR/'cache/race-control/backtesting'/f'{key}.json.gz'
        if not data and file.exists():data=json.load(gzip.open(file,'rt'))
        if not data and args.download:data=download(key)
        if not data:issues.append({'session_key':key,'status':'NOT_TESTED','reason':'No cached evaluation data; use --download'});continue
        meta=data['meta'];results=data['events'].get('session_result',[]);winner=next((int(r['driver_number']) for r in results if r.get('position')==1),None)
        if winner is None:issues.append({'session_key':key,'reason':'No published winner'});continue
        start,end=time_extent(data);prior={};pre=None;race_id=None;saved_pre=None
        day=parse_time(meta['date_start']).date()
        with SessionLocal() as db:
            candidates=db.query(Race).filter(Race.season_year==day.year,Race.date>=day-timedelta(days=1),Race.date<=day+timedelta(days=1)).all()
            if len(candidates)==1:
                race=candidates[0];race_id=race.race_id
                # Session-specific length is a static input, not a final outcome.
                _,circuit=RaceControlService().race_info(race_id);meta['circuit_length_km']=circuit.get('length_km') or 5.
        if race_id and meta.get('session_name')!='Sprint':
            with SessionLocal() as db:
                candidates=db.query(PredictionRun).filter(PredictionRun.race_id==race_id,PredictionRun.kind.in_(['race','live_race'])).all()
                eligible=[r for r in candidates if utc_stamp(r.created_at) is not None and utc_stamp(r.created_at)<start and utc_stamp(r.feature_cutoff) is not None and utc_stamp(r.feature_cutoff)<start and utc_stamp(r.training_cutoff) is not None and utc_stamp(r.training_cutoff)<start and not r.replay]
                if eligible:
                    chosen=max(eligible,key=lambda r:utc_stamp(r.created_at));pre={'predictions':chosen.predictions,'training_cutoff':chosen.training_cutoff,'feature_cutoff':chosen.feature_cutoff};saved_pre=chosen.id
        for fraction in CUTOFFS:
            at=start+(end-start)*fraction;began=time.perf_counter()
            frame=TimingTimeline.frame(data,at,data['drivers'][0]['driver_number']);base=frame
            strategy=RaceStrategyService();strategy.build_flags(base.get('_controls',[]))
            paces={r['driver_number']:strategy.tyre_estimate(base,r,meta.get('circuit_length_km',5))['recent_pace_s'] for r in frame['rows']}
            forecast=strategy.enrich(frame,data,meta.get('circuit_length_km',5))['race_forecast']
            latencies.append((time.perf_counter()-began)*1000)
            numbers=[d['driver_number'] for d in data['drivers']];n=len(numbers)
            def favourite(number):return {driver:float(driver==number) for driver in numbers}
            estimates={}
            leader=next((r['driver_number'] for r in frame['rows'] if r.get('position')==1),None)
            if leader is not None:estimates['current_leader']=favourite(leader)
            known={driver:p for driver,p in paces.items() if p is not None}
            if known:estimates['observed_pace']=favourite(min(known,key=known.get))
            if pre:
                # Names are scoped to the archived roster; permanent numbers are not used.
                from services.race_control_projection_service import normalized
                by_name={normalized(p['driver_name']):p['win_probability'] for p in pre['predictions']}
                values={d['driver_number']:by_name.get(normalized(d['name']),0) for d in data['drivers']}
                total=sum(values.values())
                if total:estimates['pre_race_favorite']=favourite(max(values,key=values.get))
            if forecast['status']=='ESTIMATE':estimates['strategy_v1']={p['driver_number']:p['win_probability'] for p in forecast['predictions']}
            payloads.append(len(json.dumps(frame,separators=(',',':'))))
            for name,values in estimates.items():
                methods[name].append((values,winner));ranked=tuple(sorted(values,key=lambda n:-values[n])[:3])
                if name in prior:changes[name].append(sum(abs(values.get(n,0)-prior[name].get(n,0)) for n in set(values)|set(prior[name])))
                prior[name]=values
            records.append({'session_key':key,'session_name':meta.get('session_name'),'race_id':race_id,'fraction':fraction,'cutoff_utc':datetime.fromtimestamp(at,timezone.utc).isoformat(),
                'winner':winner,'strategy_status':forecast['status'],'coverage':forecast.get('coverage'),
                'predictions':{name:sorted(values,key=lambda n:-values[n])[:3] for name,values in estimates.items()},
                'probabilities':{name:{str(n):p for n,p in values.items()} for name,values in estimates.items()},'pre_race_prediction_run':saved_pre,'pre_race_training_cutoff':pre.get('training_cutoff') if pre else None,'pre_race_feature_cutoff':pre.get('feature_cutoff') if pre else None})
    summary={name:{**metrics(samples),'successive_probability_l1_change':statistics.mean(changes[name]) if changes[name] else None,
                   'cutoff_coverage':len(samples)/(len(set(args.keys.split(',')))*len(CUTOFFS)),'races_with_sufficient_data':len({r['session_key'] for r in records if name in r['predictions']}),'race_coverage':len({r['session_key'] for r in records if name in r['predictions']})/len(set(args.keys.split(',')))} for name,samples in methods.items()}
    report={'verified_at':datetime.now(timezone.utc).isoformat(),'model_version':RaceStrategyService.version,'training_performed':False,'requested_sessions':len(set(args.keys.split(','))),'evaluated_sessions':len({r['session_key'] for r in records}),'cutoffs':CUTOFFS,'evaluations':records,'metrics':summary,'unavailable':issues,
            'pre_race_baseline_status':'AVAILABLE' if methods.get('pre_race_favorite') else 'NOT_AVAILABLE: no saved forecast with verified creation/training/feature cutoff before session start','performance':{'frames':len(latencies),'frame_ms_p50':statistics.median(latencies) if latencies else None,'frame_ms_p95':sorted(latencies)[max(0,math.ceil(len(latencies)*.95)-1)] if latencies else None,'payload_bytes_p50':statistics.median(payloads) if payloads else None},
            'limitations':['Small archived evaluation sample; not an independent held-out calibration study.','Historical archives include final corrections; their original publication latency is unknown.',
                'Leader/pace baselines are deterministic one-hot forecasts; log loss penalizes wrong confident predictions.','Within-race cutoff samples are correlated; metrics are descriptive only.','No final classifications, future laps, future actual pit durations or future messages enter model inputs.','Evaluation-only caches contain no coordinates and are not labelled complete UI replay.']}
    path=_bootstrap.ROOT/args.output;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2)+'\n');(_bootstrap.ROOT/'docs/LIVE_BACKTEST_RESULTS.json').write_text(path.read_text());print(json.dumps({'report':str(path),'metrics':summary},indent=2))


if __name__=='__main__':main()
