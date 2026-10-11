"""Live local verification: press the refresh button, switch target, inspect real evidence."""
import json,time,argparse
from pathlib import Path
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select,WebDriverWait
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--race-id',type=int,default=210);args=parser.parse_args()
    base='http://127.0.0.1:8090';backend='http://127.0.0.1:5000';rid=args.race_id
    opt=webdriver.ChromeOptions();opt.add_argument('--headless=new');opt.add_argument('--window-size=1440,1100');opt.set_capability('goog:loggingPrefs',{'browser':'ALL'})
    d=webdriver.Chrome(options=opt);checks=[]
    try:
        d.get(base+f'/predictions?raceId={rid}');WebDriverWait(d,20).until(lambda x:x.find_elements(By.CSS_SELECTOR,'.live-weekend'))
        assert len(d.find_elements(By.CSS_SELECTOR,'.session-card'))>=5
        assert 'George Russell' in d.find_element(By.CSS_SELECTOR,'.weekend-session-grid').text
        assert 'Max Verstappen' in d.find_element(By.CSS_SELECTOR,'.weekend-session-grid').text
        before=d.current_url
        d.find_element(By.CSS_SELECTOR,'form[action="/predictions/refresh"] button').click()
        WebDriverWait(d,45).until(lambda x:'mode=LIVE' in x.current_url and 'job=' not in x.current_url and len(x.find_elements(By.CSS_SELECTOR,'.forecast-card'))==3)
        checks.append({'check':'refresh_button_and_automatic_result_reload','passed':True})
        d.save_screenshot(str(ROOT/'docs/screenshots/live-grand-prix-desktop.png'))
        Select(d.find_element(By.ID,'target')).select_by_value('SPRINT')
        Select(d.find_element(By.ID,'mode')).select_by_value('LIVE')
        assert not d.find_element(By.ID,'marketCheck').is_enabled()
        d.find_element(By.CSS_SELECTOR,'button[data-i18n="run.prediction"]').click()
        WebDriverWait(d,20).until(lambda x:'SPRINT' in x.find_element(By.CSS_SELECTOR,'.forecast-heading').text)
        assert 'top 8' in d.find_element(By.CSS_SELECTOR,'.forecast-card').text
        checks.append({'check':'separate_sprint_forecast_and_eight_points_places','passed':True})
        d.execute_script('document.querySelector(".forecast-heading").scrollIntoView({block:"start"})');time.sleep(.3)
        d.save_screenshot(str(ROOT/'docs/screenshots/live-sprint-desktop.png'))
        for width in [320,390,768,1440,1920]:
            d.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<700})
            d.get(base+f'/predictions?raceId={rid}&target=SPRINT&mode=LIVE');time.sleep(.2)
            assert d.execute_script('return document.documentElement.scrollWidth<=innerWidth'),width
            checks.append({'check':'live_layout','width':width,'passed':True})
            if width==390:d.save_screenshot(str(ROOT/'docs/screenshots/live-weekend-mobile.png'))
        errors=[e for e in d.get_log('browser') if e['level']=='SEVERE' and 'favicon' not in e['message']]
        assert not errors,errors
        status=requests.get(backend+f'/weekend/{rid}',timeout=10).json()
        race=status['forecasts']['race'];sprint=status['forecasts']['sprint'];champ=status['forecasts']['championship']
        assert abs(sum(p['win_probability'] for p in race['predictions'])-1)<1e-9
        assert abs(sum(p['win_probability'] for p in sprint['predictions'])-1)<1e-9
        assert rid in champ['weekend_adjusted_races']
        checks.append({'check':'championship_uses_weekend_forecasts','passed':True})
        report={'verified_at':status['last_success_at'],'race_id':rid,'sessions':[{'code':s['code'],'status':s['status'],'leader':s['leader']['driver_name'] if s['leader'] else None} for s in status['sessions']],'snapshot_ids':race['session_snapshot_ids'],'race_favourite':race['predictions'][0]['driver_name'],'sprint_favourite':sprint['predictions'][0]['driver_name'],'championship_simulations':champ['simulations'],'checks':checks}
        (ROOT/'docs/LIVE_WEEKEND_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    finally:d.quit()
if __name__=='__main__':main()
