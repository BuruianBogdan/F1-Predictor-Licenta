"""Twenty browser scenarios with explicitly isolated protocol fault fixtures.

Real replay/window regression lives in verify_race_control.py. This harness uses
genuine historical frame shape plus synthetic transport states; VERIFIED_FIXTURE
is not evidence of a public live race. No fixtures enter the application DB.
"""
import _bootstrap
import argparse,copy,json,time
from datetime import datetime,timezone
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait,Select


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--frontend',default='http://127.0.0.1:8090');ap.add_argument('--backend',default='http://127.0.0.1:5000');args=ap.parse_args()
    at=datetime.fromisoformat('2026-10-04T09:14:40+00:00').timestamp()
    real=requests.get(args.backend+'/race-control/209/11731/frame',params={'mode':'REPLAY','at':at,'driver':16},timeout=30);real.raise_for_status();real=real.json()
    catalog=requests.get(args.backend+'/race-control/209/catalog',timeout=20).json();session=next(s for s in catalog['sessions'] if s['code']=='R')
    requests.get(args.frontend+'/race-control/209',timeout=20).raise_for_status()
    options=webdriver.ChromeOptions();options.add_argument('--headless=new');options.add_argument('--window-size=1500,1100');options.set_capability('goog:loggingPrefs',{'browser':'ALL'});browser=webdriver.Chrome(options=options);checks=[];scriptid=None
    bridge='''const original=window.fetch;window.fetch=async function(url,options){if(String(url).includes('/race-control/api/')){window.__requests.push(String(url));if(String(url).includes('/catalog'))return new Response(JSON.stringify(window.__test.catalog));if(String(url).includes('/frame?')){if(window.__test.hang)await new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(options.signal.reason),{once:true}));if(window.__test.error)return new Response(JSON.stringify({error:{message:'VERIFIED_FIXTURE: backend interrupted'}}),{status:503});if(window.__test.delay){const captured=JSON.stringify(window.__test.frame);await new Promise(r=>setTimeout(r,window.__test.delay));return new Response(captured);}return new Response(JSON.stringify(window.__test.frame));}return new Response(JSON.stringify({status:'SUCCESS'}));}return original(url,options);};'''
    def launch(frame=None,changes=None,empty=False,upcoming=False):
        nonlocal scriptid
        c=copy.deepcopy(catalog);s=copy.deepcopy(session);f=copy.deepcopy(frame or real)
        if upcoming:s.update(date_start=datetime.fromtimestamp(time.time()+3600,timezone.utc).isoformat(),date_end=datetime.fromtimestamp(time.time()+7200,timezone.utc).isoformat(),archive_at=datetime.fromtimestamp(time.time()+9000,timezone.utc).isoformat(),state='UPCOMING')
        c['sessions']=[] if empty else [s];c['live_configured']=True
        if changes:f.update(changes)
        if scriptid:browser.execute_cdp_cmd('Page.removeScriptToEvaluateOnNewDocument',{'identifier':scriptid})
        scriptid=browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':'window.__test='+json.dumps({'catalog':c,'frame':f})+';window.__requests=[];'+bridge})['identifier']
        browser.get(args.frontend+'/race-control/209?session=R&autostart=true&paused=true&at='+str(at));time.sleep(.3)
        if not empty and not upcoming:WebDriverWait(browser,20).until(lambda b:b.find_element(By.ID,'connection-badge').text not in ('NOT CONNECTED','CONNECTING'))
    def check(name,assertion):
        assert assertion,name;checks.append({'scenario':name,'status':'VERIFIED_FIXTURE'})
    try:
        launch(empty=True);check('1_no_selected_session',not browser.find_element(By.ID,'connect').is_enabled())
        launch(upcoming=True);check('2_upcoming_session_start_gate',not browser.find_element(By.ID,'connect').is_enabled() and 'Starts' in browser.find_element(By.ID,'availability-title').text)
        def live(state,rows=True):
            f=copy.deepcopy(real);now=time.time();f.update(mode='LIVE',at=now,locations={},telemetry=[],positions_available=False,telemetry_available=False,connection={'status':state,'error':None},track=None,result_confirmation={'status':'LIVE_LEADER'},winner=None)
            if not rows:f.update(rows=[],selected=None,laps=[],race_forecast={'status':'INSUFFICIENT_TIMING','note':'Waiting for observed timing.'},championship_projection={'status':'INSUFFICIENT_TIMING','note':'Waiting for an observed classification.'})
            f['diagnostics']={'provider_id':'VERIFIED_FIXTURE','state':state,'transport_state':'CONNECTED','session_key':session['session_key'],'meeting_key':session['meeting_key'],'identity':'VERIFIED','attempts':2,'recovered':False,'last_valid_observation_utc':datetime.fromtimestamp(now,timezone.utc).isoformat() if state=='LIVE' else None,'data_age_seconds':0 if state=='LIVE' else None,'channels':{topic:{'requested':True,'state':'AVAILABLE' if topic=='TimingData' and state=='LIVE' else 'MISSING','valid_events':1 if state=='LIVE' else 0,'explanation':'Synthetic protocol fault fixture'} for topic in ('SessionInfo','SessionStatus','DriverList','Position.z','CarData.z','TimingData','TimingAppData','TimingStats','RaceControlMessages','WeatherData','TrackStatus','LapCount')},'capabilities':{'timing':'AVAILABLE' if state=='LIVE' else 'MISSING','positions':'MISSING','telemetry':'MISSING'}}
            return f
        # Force a live scheduling window, not a claim about the historic session.
        def launch_live(state,rows=True):
            f=live(state,rows);launch(f)
            browser.execute_script('window.__test.catalog.sessions[0].archive_at=new Date(Date.now()+3600000).toISOString()')
            browser.find_element(By.ID,'refresh-sessions').click();WebDriverWait(browser,10).until(lambda b:b.find_element(By.ID,'connection-badge').text==('● LIVE' if state=='LIVE' else state))
            if browser.find_element(By.ID,'race-transition').is_displayed():
                browser.find_element(By.ID,'dismiss-transition').click();WebDriverWait(browser,5).until(lambda b:not b.find_element(By.ID,'race-transition').is_displayed())
        launch_live('WAITING',False);check('3_live_transport_without_timing','WAITING' in browser.find_element(By.ID,'connection-badge').text)
        launch_live('LIVE');check('4_live_with_valid_fixture_timing','LIVE' in browser.find_element(By.ID,'connection-badge').text)
        browser.execute_script("window.__test.frame.connection.status='STALE';window.__test.frame.diagnostics.state='STALE'");WebDriverWait(browser,8).until(lambda b:b.find_element(By.ID,'connection-badge').text=='STALE');check('5_delayed_feed',True)
        browser.execute_script("window.__test.frame.connection.status='DISCONNECTED'");WebDriverWait(browser,8).until(lambda b:b.find_element(By.ID,'connection-badge').text=='DISCONNECTED');WebDriverWait(browser,3).until(lambda b:b.find_element(By.ID,'connect').is_enabled());check('6_disconnected_feed',True)
        browser.find_element(By.ID,'diagnostics-open').click();check('7_missing_position_channel', 'timing can work without map motion' in browser.find_element(By.ID,'diagnostics-limits').text)
        check('8_missing_car_channel', 'telemetry charts require measured data' in browser.find_element(By.ID,'diagnostics-limits').text)
        check('diagnostics_all_twelve_requested_topics',len(browser.find_elements(By.CSS_SELECTOR,'#diagnostics-rows tr'))==12 and 'Reconnect attempts' in browser.find_element(By.ID,'diagnostics-summary').text)
        browser.find_element(By.ID,'diagnostics-close').click()
        launch();check('9_replay_loaded','HISTORICAL REPLAY' in browser.find_element(By.ID,'connection-badge').text)
        f=copy.deepcopy(real);d=next(d for d in f['rows'] if d['code']=='RUS');f['selected']=d
        browser.execute_script('window.__test.frame=arguments[0]',f);Select(browser.find_element(By.ID,'favorite-driver')).select_by_value(str(d['driver_number']));WebDriverWait(browser,8).until(lambda b:b.find_element(By.ID,'driver-code').text=='RUS');check('10_driver_switch',True)
        # Return an old delayed frame after a session reset. Generation must reject it.
        browser.execute_script('window.__test.delay=1500');Select(browser.find_element(By.ID,'favorite-driver')).select_by_value('16')
        browser.execute_script("document.getElementById('stream-session').dispatchEvent(new Event('change'))");time.sleep(2);check('11_old_frame_discarded_on_session_switch',browser.find_element(By.ID,'driver-code').text=='—')
        launch();first=browser.current_window_handle;browser.find_element(By.ID,'popout').click();WebDriverWait(browser,10).until(lambda b:len(b.window_handles)==2);child=next(h for h in browser.window_handles if h!=first);browser.switch_to.window(child);WebDriverWait(browser,20).until(lambda b:len(b.find_elements(By.CSS_SELECTOR,'#timing-rows tr'))>10);check('12_multiple_windows',True);browser.close();browser.switch_to.window(first)
        p=copy.deepcopy(real['championship_projection']);p.update(status='PROVISIONAL',baseline_note=None)
        for kind in ('drivers','constructors'):
            for r in p[kind]:r.update(official_points=10,session_points=5,projected_points=15,position_change=1)
        browser.execute_script('window.__test.frame.championship_projection=arguments[0]',p);Select(browser.find_element(By.ID,'projection-scoring')).select_by_value('STOPPED_NOW');WebDriverWait(browser,8).until(lambda b:b.find_element(By.ID,'projection-status').text=='PROVISIONAL')
        check('13_drivers_projection', '↑ 1' in browser.find_element(By.ID,'projection-rows').text and 'Provisional — based' in browser.find_element(By.CSS_SELECTOR,'.rc-championship').text)
        Select(browser.find_element(By.ID,'projection-kind')).select_by_value('constructors');check('14_constructors_projection',len(browser.find_elements(By.CSS_SELECTOR,'#projection-rows tr'))==11)
        check('single_frame_request_no_duplicate_diagnostics_or_projection',browser.execute_script("return !window.__requests.some(u=>u.includes('/championship-projection')||u.includes('/diagnostics'))"))
        browser.execute_script("window.__test.frame.championship_projection.status='PARTIAL'");Select(browser.find_element(By.ID,'projection-scoring')).select_by_value('FULL_DISTANCE');WebDriverWait(browser,8).until(lambda b:b.find_element(By.ID,'projection-status').text=='PARTIAL');check('15_mapping_missing',True)
        provisional=copy.deepcopy(real);provisional.update(phase='FINISHED',winner=None,result_confirmation={'status':'PROVISIONAL_P1'});launch(provisional);check('16_provisional_finish_without_winner_hero',not browser.find_element(By.ID,'race-transition').is_displayed() and 'PROVISIONAL P1' in browser.find_element(By.ID,'phase-label').text)
        verified=copy.deepcopy(real);winner=next(d for d in verified['rows'] if d['position']==1);verified.update(phase='FINISHED',winner=winner,result_confirmation={'status':'OFFICIAL_WINNER_CONFIRMED','verification_scope':'HISTORICAL_LATEST'});launch(verified);check('17_verified_historical_result',browser.find_element(By.ID,'transition-title').text=='RACE WINNER' and 'VERIFIED HISTORICAL' in browser.find_element(By.ID,'transition-kicker').text)
        launch_live('LIVE');browser.execute_script('window.__test.error=true');WebDriverWait(browser,8).until(lambda b:'backend interrupted' in b.find_element(By.ID,'rc-notice').text);check('18_backend_interruption_visible',True)
        browser.execute_script('window.__test.error=false');WebDriverWait(browser,8).until(lambda b:b.find_element(By.ID,'connection-badge').text=='● LIVE');check('19_frontend_recovers_after_backend_returns',True)
        browser.execute_script('window.__test.hang=true');WebDriverWait(browser,24).until(lambda b:'within 20 seconds' in b.find_element(By.ID,'rc-notice').text);check('bounded_request_timeout_without_backend_response',browser.find_element(By.ID,'projection-status').text=='STALE_INPUTS')
        browser.execute_script('window.__test.hang=false');Select(browser.find_element(By.ID,'projection-scoring')).select_by_value('STOPPED_NOW');WebDriverWait(browser,8).until(lambda b:b.find_element(By.ID,'connection-badge').text=='● LIVE')
        browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':390,'height':950,'deviceScaleFactor':1,'mobile':True});check('20_mobile_no_page_overflow',browser.execute_script('return document.documentElement.scrollWidth<=innerWidth'))
        browser.execute_script("document.getElementById('diagnostics-open').click()");browser.find_element(By.ID,'diagnostics-close').send_keys('\ue00c');check('accessible_dialog_escape',not browser.find_element(By.ID,'feed-diagnostics').is_displayed())
        browser.execute_cdp_cmd('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]});check('reduced_motion_preference',browser.execute_script("return matchMedia('(prefers-reduced-motion:reduce)').matches"))
        browser.execute_script("window.dispatchEvent(new PageTransitionEvent('pagehide'))");count=browser.execute_script('return window.__requests.length');time.sleep(2);check('pagehide_stops_frontend_requests',browser.execute_script('return window.__requests.length')==count)
        errors=[e for e in browser.get_log('browser') if e['level']=='SEVERE' and 'favicon' not in e['message']];assert not errors,errors
        report={'verified_at':datetime.now(timezone.utc).isoformat(),'status':'VERIFIED_FIXTURE','real_live_session_tested':False,'scenarios':checks,'browser_errors':errors,'limits':['Backend restart simulated as bounded HTTP failure/return; real checkpoint restart is separately verified by backend tests.','Live states and scoring fixtures test UI contracts, not upstream availability.']}
        (_bootstrap.ROOT/'docs/LIVE_COMPLETION_BROWSER.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    except Exception:
        print(json.dumps(browser.execute_script("return {badge:document.getElementById('connection-badge').textContent,notice:document.getElementById('rc-notice').textContent,availability:document.getElementById('availability-title').textContent,requests:window.__requests,catalog:window.__test.catalog.sessions}"),indent=2));raise
    finally:browser.quit()


if __name__=='__main__':main()
