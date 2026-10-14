"""Explicit real historical integration and isolated fallback/browser experiment.

Never run as a unit test; may access public historical files. Does not overwrite
application replay caches or masquerade as a running session.
"""
import _bootstrap
import argparse,copy,json,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
from database.db import SessionLocal
from models.race import Race
from data_sources.base_provider import ProviderError
from services.race_control_service import RaceControlService,stamp
from data_sources.timing_contract import utc_stamp


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--key',type=int,default=9662);parser.add_argument('--frontend',default='http://127.0.0.1:8090');parser.add_argument('--browser',action='store_true');args=parser.parse_args()
    service=RaceControlService();reference=service.load(args.key)
    if not reference:
        import gzip
        file=service.cache_dir/'backtesting'/f'{args.key}.json.gz'
        reference=json.load(gzip.open(file,'rt')) if file.exists() else None
    if not reference:raise SystemExit('Need a verified OpenF1 catalog/archive for this key first')
    meta={**reference['meta'],'replay_allowed':True,'live_allowed':False,'code':'R'}
    with SessionLocal() as db:
        races=db.query(Race).filter_by(season_year=datetime.fromisoformat(meta['date_start']).year).all()
        race=next(r for r in races if str(r.date)==meta['date_start'][:10]);rid=race.race_id
    service.session=lambda *a:meta;service.datasets={};service.jobs={};service.cache_dir=Path(tempfile.mkdtemp(prefix='f1-fastf1-verification-'))
    class UnavailablePrimary:
        def fetch(self,*a,**k):raise ProviderError('VERIFIED_FIXTURE: primary archive deliberately unavailable')
    service.provider=UnavailablePrimary();began=time.perf_counter();service.prepare(rid,args.key,'REPLAY')
    while service.jobs[f'{args.key}-REPLAY']['status'] in ('RUNNING','QUEUED'):
        if time.perf_counter()-began>300:raise TimeoutError('Historical fallback exceeded 300 seconds')
        time.sleep(.25)
    job=service.jobs[f'{args.key}-REPLAY'];assert job['status']=='SUCCESS',job
    data=service.load(args.key);assert data['historical_provider']=='fastf1_historical'
    at=stamp(meta['date_start'])+(stamp(meta['date_end'])-stamp(meta['date_start']))*.5
    frame=service.frame(rid,args.key,at,data['drivers'][0]['driver_number'],'REPLAY')
    roster={str(d['driver_number']) for d in data['drivers']};assert set(data['locations'])<=roster and set(data['telemetry'])<=roster
    assert all(all(isinstance(v,(int,float)) for v in p) for series in data['locations'].values() for p in series)
    assert all(utc_stamp(r['date']) is not None for r in data['events']['weather']+data['events']['race_control']+data['events']['pit'])
    assert data['track'] and frame['phase']=='RUNNING' and all(len(p)==7 for v in data['telemetry'].values() for p in v)
    ff_winner=next(r['driver_number'] for r in data['events']['session_result'] if r['position']==1)
    open_winner=next(r['driver_number'] for r in reference['events']['session_result'] if r['position']==1);assert ff_winner==open_winner
    comparison={'openf1_session_key':args.key,'same_winner':True,'winner_driver_number':ff_winner,'same_roster':roster=={str(d['driver_number']) for d in reference['drivers']},'fastf1_laps':len(data['events']['laps']),'openf1_laps':len(reference['events']['laps']), 'note':'Sample rates, lap deletion/correction handling, gaps and pit-duration availability differ; sources are not interchangeable.'}
    report={'status':'VERIFIED_HISTORICAL','verified_at':datetime.now(timezone.utc).isoformat(),'session_key':args.key,'race_id':rid,'year':race.season_year,'round':race.round,'session_name':meta['session_name'],'source':'FastF1 measured historical session files','fallback_selection_status':'VERIFIED_FIXTURE','fallback_selection_reason':'Only primary failure injected; fallback loads genuine historical data','elapsed_seconds':time.perf_counter()-began,'drivers':len(roster),'completed_laps':len(data['events']['laps']),'weather_records':len(data['events']['weather']),'race_control_records':len(data['events']['race_control']),'pit_events':len(data['events']['pit']),'position_samples':sum(map(len,data['locations'].values())),'telemetry_samples':sum(map(len,data['telemetry'].values())),'driver_identity_scope_checked':True,'timestamps_checked':True,'track_available':True,'comparison':comparison,'live_tested':False,'replay_rendering':'NOT_TESTED'}
    if args.browser:
        from selenium import webdriver
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.common.by import By
        options=webdriver.ChromeOptions();options.add_argument('--headless=new');options.add_argument('--window-size=1500,1100')
        browser=webdriver.Chrome(options=options)
        try:
            _,circuit=service.race_info(rid);catalog={'race':service.race_info(rid)[0],'circuit':circuit,'sessions':[meta],'live_configured':False}
            payload={'catalog':catalog,'frame':frame}
            script='const sample='+json.dumps(payload,allow_nan=False)+';const original=window.fetch;window.fetch=async function(url,opts){if(String(url).includes("/race-control/api/")){const data=String(url).includes("/catalog")?sample.catalog:String(url).includes("/frame?")?sample.frame:{status:"SUCCESS"};return new Response(JSON.stringify(data),{headers:{"Content-Type":"application/json"}});}return original(url,opts);};'
            browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':script})
            browser.get(args.frontend+f'/race-control/{rid}?session=R&autostart=true&paused=true&at={at}');WebDriverWait(browser,30).until(lambda b:len(b.find_elements(By.CSS_SELECTOR,'#timing-rows tr'))==len(roster))
            WebDriverWait(browser,15).until(lambda b:len(b.find_elements(By.CSS_SELECTOR,'.rc-car'))>=15)
            assert browser.find_element(By.ID,'car-rpm').text!='—'
            browser.save_screenshot(str(_bootstrap.ROOT/'docs/screenshots/fastf1-replay-verified.png'))
            report.update(replay_rendering='VERIFIED_HISTORICAL',render_transport='VERIFIED_FIXTURE: isolated browser response bridge with genuine FastF1 frame, not live data')
        finally:browser.quit()
    path=_bootstrap.ROOT/'docs/FASTF1_ARCHIVE_VERIFICATION.json';path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
