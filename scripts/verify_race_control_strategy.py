"""Browser regression of uninterrupted replay, measured animation and race strategy panels."""
import json,time
from datetime import datetime,timezone
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select,WebDriverWait
import requests
ROOT=Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:8090';API='http://127.0.0.1:5000'
def timestamp(s):return datetime.fromisoformat(s).timestamp()
def main():
    options=webdriver.ChromeOptions();options.add_argument('--headless=new');options.add_argument('--window-size=1600,1350');options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
    d=webdriver.Chrome(options=options);checks=[];screen=ROOT/'docs/screenshots'
    def wait(condition,seconds=30):return WebDriverWait(d,seconds).until(condition)
    def load(race,session,at,paused=False):
        d.get(f'{BASE}/race-control/{race}?session={session}&autostart=true&at={at}&paused={str(paused).lower()}')
        wait(lambda x:len(x.find_elements(By.CSS_SELECTOR,'.rc-tower tbody tr'))==22)
        wait(lambda x:x.find_element(By.ID,'play-pause').text!='▶ Play' if not paused else x.find_element(By.ID,'play-pause').text=='▶ Play')
    def elapsed():return sum(int(n)*scale for n,scale in zip(d.find_element(By.ID,'elapsed').text.split(':'),[3600,60,1]))
    try:
        # Actual SQ1 finish is an intermission, not the end of SQ3.
        load(210,'SQ',timestamp('2026-10-09T12:52:10+00:00'))
        before=elapsed();time.sleep(12);after=elapsed()
        assert after-before>=10 and 'Pause' in d.find_element(By.ID,'play-pause').text
        assert d.find_element(By.ID,'phase-label').text=='QUALIFYING INTERMISSION'
        assert not d.find_element(By.ID,'race-transition').is_displayed()
        checks.append({'check':'SQ1_intermission_does_not_stop_or_reveal_final_winner','elapsed_seconds':after-before,'passed':True})
        load(210,'SQ',timestamp('2026-10-09T13:28:20+00:00'))
        Select(d.find_element(By.ID,'favorite-driver')).select_by_value('3');Select(d.find_element(By.ID,'speed')).select_by_value('30')
        before=elapsed();fresh=[];moving=0;last={}
        for _ in range(55):
            current={r.get_attribute('data-driver'):r.get_attribute('transform') for r in d.find_elements(By.CSS_SELECTOR,'.rc-car') if r.get_attribute('style')!='display: none;'}
            moving+=sum(current.get(k)!=v for k,v in last.items() if k in current);last=current
            fresh.append(d.find_element(By.ID,'position-status').text);time.sleep(.15)
        assert elapsed()-before>=230 and 'Pause' in d.find_element(By.ID,'play-pause').text
        assert moving>50 and sum('0 delayed' in x for x in fresh)>=45
        checks.append({'check':'30x_replay_clock_and_position_buffer_remain_continuous','moving_updates':moving,'passed':True})
        d.find_element(By.ID,'play-pause').click();d.save_screenshot(str(screen/'race-control-smooth-map.png'))
        gp=timestamp('2026-10-04T09:14:40+00:00');load(209,'R',gp,paused=True)
        Select(d.find_element(By.ID,'favorite-driver')).select_by_value('16')
        wait(lambda x:x.find_element(By.ID,'driver-code').text=='LEC' and 'COLLISION' in x.find_element(By.ID,'car-incident').text)
        assert d.find_element(By.ID,'health-car').get_attribute('class').endswith('impact-alert')
        assert d.find_element(By.ID,'wear-fl').text!='—'
        assert len(d.find_elements(By.CSS_SELECTOR,'#outlook-rows li'))==6
        assert 'Pit loss now' in d.find_element(By.ID,'outlook-context').text
        assert elapsed()>2400 # requested point after the original scheduled finish must not reset to race start
        checks.append({'check':'actual_incident_wear_and_running_race_forecast_at_requested_time','passed':True})
        d.save_screenshot(str(screen/'race-control-strategy-desktop.png'))
        d.execute_script("document.querySelector('.rc-inspector').scrollIntoView({block:'center'})");time.sleep(.5);d.save_screenshot(str(screen/'race-control-tyres-incident.png'))
        for width in [320,390,768,1440,1920]:
            d.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':width,'height':1100,'deviceScaleFactor':1,'mobile':width<700})
            load(209,'R',gp,paused=True);Select(d.find_element(By.ID,'favorite-driver')).select_by_value('16');wait(lambda x:'COLLISION' in x.find_element(By.ID,'car-incident').text)
            assert d.execute_script('return document.documentElement.scrollWidth<=innerWidth'),width
            assert d.execute_script("const e=document.getElementById('health-car').getBoundingClientRect();return e.width>60 && e.right<=innerWidth"),width
            checks.append({'check':'strategy_layout_no_page_overflow','width':width,'passed':True})
            if width==390:
                d.execute_script("document.querySelector('.rc-inspector').scrollIntoView({block:'center'})");time.sleep(.3);d.save_screenshot(str(screen/'race-control-strategy-mobile.png'))
        # Same replay timestamp is deterministic, with probabilities summing to one.
        frame=requests.get(API+'/race-control/209/11731/frame',params={'mode':'REPLAY','at':gp,'driver':16,'window':240},timeout=20).json()
        assert abs(sum(p['win_probability'] for p in frame['race_forecast']['predictions'])-1.)<1e-10
        assert frame['selected']['condition']['components']['body']=='UNKNOWN'
        assert frame['selected']['condition']['body_alert']
        assert not frame['selected']['tyre_estimate']['per_wheel_measured']
        checks.append({'check':'estimates_and_unknown_component_states_are_explicit','passed':True})
        errors=[e for e in d.get_log('browser') if e['level']=='SEVERE' and 'favicon' not in e['message']]
        assert not errors,errors
        report={'verified_at':datetime.now(timezone.utc).isoformat(),'source':'actual archived Singapore SQ and delayed Malaysian GP sessions','checks':checks,'browser_errors':errors,'limitations':['Tyre wear is a model index for the set; individual wheel wear is unavailable.','Collision reports are not per-component damage measurements.','On-track forecasts are experimental and have not been calibrated or backtested.','Free live source availability and missing position channels are unchanged.']}
        (ROOT/'docs/RACE_STRATEGY_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    finally:d.quit()
if __name__=='__main__':main()
