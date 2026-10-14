"""Reproducible source evidence; no subscription/token/browser automation.

Use --public-probe only for the selected current session. A post-session snapshot
is never recorded as VERIFIED_LIVE, even if negotiation and subscription succeed.
"""
import _bootstrap
import argparse,json,time
import requests
from datetime import datetime,timezone
from pathlib import Path
from services.race_control_service import RaceControlService,stamp
from data_sources.public_timing_provider import PublicTimingFeed
from data_sources.timing_contract import FeedHealth,utc_stamp
from data_sources.race_control_sources import provider_catalog


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--race-id',type=int,default=210)
    parser.add_argument('--session',default='R');parser.add_argument('--public-probe',action='store_true')
    parser.add_argument('--seconds',type=int,default=20);parser.add_argument('--output',default='docs/LIVE_SOURCE_VERIFICATION.json')
    parser.add_argument('--compare-public-hosts',action='store_true')
    args=parser.parse_args();service=RaceControlService();catalog=service.catalog(args.race_id)
    meta=next((s for s in catalog['sessions'] if s['code']==args.session or str(s['session_key'])==args.session),None)
    if not meta:raise SystemExit('Selected session is absent from the verified catalog')
    key=meta['session_key'];data=service.load(key);historical=[]
    for session in catalog['sessions']:
        archived=service.load(session['session_key'])
        if archived:
            historical.append({'session_key':session['session_key'],'status':'VERIFIED_HISTORICAL',
                'session_name':session['session_name'],'drivers':len(archived['drivers']),
                'position_samples':sum(map(len,archived['locations'].values())),
                'car_samples_loaded':sum(map(len,archived['telemetry'].values())),
                'source':archived.get('historical_provider','openf1_historical')})
    public={'status':'NOT_TESTED','reason':'A real active-session observation test is pending','session_key':key}
    if args.public_probe:
        try:
            app_health=requests.get('http://127.0.0.1:5000/race-control/health',timeout=2).json()
        except (requests.RequestException,ValueError):app_health={}
        if app_health.get('active_connections',0):raise SystemExit('Stop the application live feed before a separate command-line probe')
        health=FeedHealth(key);events=[]
        # Probe uses the real ingestion/decoder/identity logic, not a second app
        # connection. Stop the app's live connection before a command-line probe.
        if service.live.get(key,{}).get('client'):raise SystemExit('Stop the shared live connection before probing')
        service.live_datasets[key]={'meta':meta,'drivers':[],'events':{},'locations':{},'telemetry':{},'track':None,
                                  'public_state':{},'public_laps':{},'complete_archive':False,'downloaded_at':datetime.now(timezone.utc).isoformat()}
        service.live[key]={'status':'CONNECTING','last_message':None,'health':health}
        feed=PublicTimingFeed(key,lambda topic,patch,date:service.ingest_public(key,topic,patch,date),
                              lambda state,error:service.live[key].update(status=state,error=error),expected=meta,health=health)
        try:
            feed.start();deadline=time.monotonic()+max(1,min(60,args.seconds))
            while time.monotonic()<deadline and health.state!='ACCESS_DENIED':time.sleep(.2)
            snapshot=health.snapshot();observed=service.live_data(key);phase=observed['public_state'].get('SessionStatus',{}).get('Status')
            active=phase=='Started' and snapshot['state']=='LIVE' and meta['live_allowed']
            public={'status':'VERIFIED_LIVE' if active else 'ACCESS_NOT_PERMITTED' if snapshot['state']=='ACCESS_DENIED' else 'NOT_TESTED',
                    'reason':'Actual dated observations received during the selected running session' if active else 'No running, matching session with fresh dated timing was observed',
                    'session_key':key,'phase':phase,'diagnostics':snapshot,
                    'live_xy_received':bool(active and observed['locations']),
                    'live_car_data_received':bool(active and observed['telemetry'])}
        except Exception as exc:public.update(status='UNAVAILABLE',reason=type(exc).__name__)
        finally:feed.stop();service.checkpoint(key,force=True)
    report={'verified_at':datetime.now(timezone.utc).isoformat(),'selected_session':meta,
            'providers':provider_catalog()['providers'],'historical_checks':historical,'public_probe':public,
            'fixture_tests':{'status':'NOT_TESTED','command':'backend-python/.venv/bin/python -m pytest backend-python/tests/test_timing_integration.py -q',
                             'note':'Run protocol fixtures separately; this source probe does not execute pytest or prove upstream live access'},
            'credentials_used':False,'live_validation_pending':public['status']!='VERIFIED_LIVE','live_validation_status':'VERIFIED_LIVE' if public['status']=='VERIFIED_LIVE' else 'PENDING_LIVE_SESSION'}
    if args.compare_public_hosts:
        checks=[]
        for source,url in [('harsh_host','https://f1-live-api.onrender.com/health'),('f1api_results','https://f1api.dev/api/2026/16/race'),('f1api_results_site','https://live.f1api.dev')]:
            try:
                response=requests.get(url,timeout=(5,25));status='VERIFIED_HISTORICAL' if response.status_code==200 and source=='f1api_results' else 'NOT_TESTED' if response.status_code==200 else 'UNAVAILABLE'
                checks.append({'provider_id':source,'url':url,'http_status':response.status_code,'status':status,
                    'reason':'Published results, not live coordinates/CarData' if source=='f1api_results' else 'Public results website, not verified streaming transport' if source=='f1api_results_site' else 'Hosted health probe; no active timing verified'})
            except requests.RequestException:checks.append({'provider_id':source,'url':url,'status':'UNAVAILABLE','reason':'Bounded request failed'})
        report['alternative_public_host_checks']=checks
    verification=_bootstrap.ROOT/'docs/FASTF1_ARCHIVE_VERIFICATION.json'
    if verification.exists():report['fastf1_historical_check']=json.loads(verification.read_text())
    output=_bootstrap.ROOT/args.output;output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'report':str(output),'public_status':public['status'],'historical_sessions':len(historical)},indent=2))


if __name__=='__main__':main()
