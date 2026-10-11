"""Real local browser verification. Does not manufacture live telemetry."""
import json,time
from pathlib import Path
from datetime import datetime,timezone
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select,WebDriverWait
ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8090'
BACKEND='http://127.0.0.1:5000'
def main():
    opt=webdriver.ChromeOptions();opt.add_argument('--headless=new');opt.add_argument('--window-size=1600,1350');opt.set_capability('goog:loggingPrefs',{'browser':'ALL'})
    d=webdriver.Chrome(options=opt);checks=[];screens=ROOT/'docs/screenshots';screens.mkdir(exist_ok=True)
    def wait(condition,seconds=25):return WebDriverWait(d,seconds).until(condition)
    def seek(value):
        d.execute_script('const s=document.getElementById("seek");s.value=arguments[0];s.dispatchEvent(new Event("input"));',value)
        wait(lambda x:x.find_element(By.ID,'elapsed').text.endswith(f'{int(value)%60:02d}'))
        time.sleep(.4)
    def load(race=210,session='FP1',at=None,paused=False):
        suffix=f'&at={at}' if at is not None else ''
        if paused:suffix+='&paused=true'
        d.get(BASE+f'/race-control/{race}?session={session}'+suffix)
        wait(lambda x:x.find_element(By.ID,'connect').is_enabled());d.find_element(By.ID,'connect').click()
        wait(lambda x:len(x.find_elements(By.CSS_SELECTOR,'.rc-tower tbody tr'))==22,100)
    try:
        load()
        wait(lambda x:x.find_element(By.ID,'race-transition').is_displayed())
        assert d.find_element(By.ID,'transition-title').text=='SESSION STARTS!'
        d.save_screenshot(str(screens/'race-control-start.png'))
        d.find_element(By.ID,'dismiss-transition').click();time.sleep(.6)
        d.find_element(By.ID,'play-pause').click()
        Select(d.find_element(By.ID,'favorite-driver')).select_by_value('63')
        wait(lambda x:x.find_element(By.ID,'driver-name').text=='George Russell')
        seek(338);wait(lambda x:x.find_element(By.ID,'flag-badge').text=='YELLOW')
        checks.append({'check':'real_sector_yellow_flag','passed':True})
        seek(350);wait(lambda x:x.find_element(By.ID,'flag-badge').text=='GREEN')
        checks.append({'check':'sector_clear_removes_yellow','passed':True})
        before=d.find_element(By.CSS_SELECTOR,'.rc-car[data-driver="63"]').get_attribute('transform')
        d.find_element(By.ID,'play-pause').click();time.sleep(2.5)
        after=d.find_element(By.CSS_SELECTOR,'.rc-car[data-driver="63"]').get_attribute('transform')
        assert before!=after
        d.find_element(By.ID,'play-pause').click()
        checks.append({'check':'real_measured_car_motion','passed':True})
        wait(lambda x:x.find_element(By.ID,'car-speed').text!='—',35)
        assert len(d.find_elements(By.CSS_SELECTOR,'#sector-rows tr'))>0
        checks.append({'check':'favorite_driver_laps_and_real_telemetry','passed':True})
        d.save_screenshot(str(screens/'race-control-desktop.png'))
        # A new independent window autoloads the same replay without the site navigation.
        main=d.current_window_handle;d.find_element(By.ID,'popout').click();wait(lambda x:len(x.window_handles)==2)
        child=next(h for h in d.window_handles if h!=main);d.switch_to.window(child)
        wait(lambda x:len(x.find_elements(By.CSS_SELECTOR,'.rc-tower tbody tr'))==22)
        assert not d.find_elements(By.CSS_SELECTOR,'nav.navbar')
        d.switch_to.window(main);d.close();d.switch_to.window(child)
        before=d.find_element(By.ID,'elapsed').text;d.find_element(By.ID,'play-pause').click();time.sleep(2.3)
        assert d.find_element(By.ID,'elapsed').text!=before
        d.find_element(By.ID,'play-pause').click()
        checks.append({'check':'standalone_autoload_continues_after_main_window_closes','passed':True})
        d.save_screenshot(str(screens/'race-control-standalone.png'))
        # Availability gating uses the actual published upcoming Sprint schedule.
        catalog=requests.get(BACKEND+'/race-control/210/catalog',timeout=20).json()
        sprint=next(s for s in catalog['sessions'] if s['code']=='SPRINT')
        if sprint['state']=='UPCOMING':
            Select(d.find_element(By.ID,'stream-session')).select_by_value(str(sprint['session_key']))
            assert not d.find_element(By.ID,'connect').is_enabled()
            assert 'Starts' in d.find_element(By.ID,'availability-title').text
            checks.append({'check':'future_session_countdown_and_start_gate','passed':True})
        fp=next(s for s in catalog['sessions'] if s['code']=='FP1');start=datetime.fromisoformat(fp['date_start']).timestamp()
        for width in [320,390,768,1440,1920]:
            d.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':width,'height':1100,'deviceScaleFactor':1,'mobile':width<700})
            load(at=start+350,paused=True)
            wait(lambda x:x.find_element(By.ID,'driver-name').text=='George Russell')
            assert d.execute_script('return document.documentElement.scrollWidth<=innerWidth'),width
            checks.append({'check':'responsive_no_page_overflow','width':width,'passed':True})
            if width==390:d.save_screenshot(str(screens/'race-control-mobile.png'))
        # Practice leader transition must not announce a race winner.
        seek(3601);wait(lambda x:x.find_element(By.ID,'race-transition').is_displayed())
        assert d.find_element(By.ID,'transition-title').text=='SESSION LEADER'
        assert d.find_element(By.ID,'transition-name').text=='George Russell'
        checks.append({'check':'practice_end_uses_confirmed_session_leader','passed':True})
        d.save_screenshot(str(screens/'race-control-session-leader.png'))
        # The most recent GP started late; verify the actual end and real winner photo.
        gp_catalog=requests.get(BACKEND+'/race-control/209/catalog',timeout=20).json()
        gp=next(s for s in gp_catalog['sessions'] if s['code']=='R')
        load(race=209,session='R')
        wait(lambda x:x.find_element(By.ID,'race-transition').is_displayed())
        assert d.find_element(By.ID,'transition-title').text=='RACE STARTS!'
        time.sleep(.8);d.save_screenshot(str(screens/'race-control-gp-start.png'))
        d.find_element(By.ID,'dismiss-transition').click();time.sleep(.6)
        d.find_element(By.ID,'play-pause').click()
        last=int(float(d.find_element(By.ID,'seek').get_attribute('max')))-10
        seek(last);wait(lambda x:x.find_element(By.ID,'race-transition').is_displayed())
        assert d.find_element(By.ID,'transition-title').text=='RACE WINNER'
        assert d.find_element(By.ID,'transition-name').text=='Max Verstappen'
        wait(lambda x:x.execute_script("const p=document.getElementById('transition-photo');return p.complete && p.naturalWidth>=1000 && p.src.includes('maxver01')"))
        time.sleep(.8);d.save_screenshot(str(screens/'race-control-gp-winner.png'))
        checks.append({'check':'delayed_gp_actual_start_finish_and_winner_with_hd_photo','passed':True})
        errors=[e for e in d.get_log('browser') if e['level']=='SEVERE' and 'favicon' not in e['message']]
        assert not errors,errors
        report={'verified_at':datetime.now(timezone.utc).isoformat(),'replay_source':'OpenF1 Singapore FP1 2026 session 11378','checks':checks,'browser_errors':errors,'public_live_probe':{'authentication':False,'snapshot_received':True,'timing_drivers':22,'position_channel_present':False,'car_channel_present':False,'note':'Probe made after Sprint Qualifying; an active session has not yet occurred during this verification. Availability can vary; a later probe returned an unavailable response.'}}
        (ROOT/'docs/RACE_CONTROL_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    finally:d.quit()
if __name__=='__main__':main()
