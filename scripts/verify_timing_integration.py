"""Real local browser/API regression, layout evidence and measured HTTP timings."""
import argparse,json,time,math,statistics
from datetime import datetime,timezone
from pathlib import Path
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select,WebDriverWait

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--frontend',default='http://127.0.0.1:8090');parser.add_argument('--backend',default='http://127.0.0.1:5000')
    args=parser.parse_args();checks=[];screens=ROOT/'docs/screenshots';screens.mkdir(exist_ok=True)
    options=webdriver.ChromeOptions();options.add_argument('--headless=new');options.add_argument('--window-size=1600,1250');options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
    browser=webdriver.Chrome(options=options);wait=WebDriverWait(browser,40)
    at=datetime.fromisoformat('2026-10-04T09:14:40+00:00').timestamp()
    url=args.frontend+f'/race-control/209?session=R&autostart=true&paused=true&at={at}'
    try:
        browser.get(url);wait.until(lambda b:len(b.find_elements(By.CSS_SELECTOR,'#timing-rows tr'))==22)
        wait.until(lambda b:len(b.find_elements(By.CSS_SELECTOR,'#projection-rows tr'))>=22)
        assert 'Full-distance' in browser.find_element(By.ID,'projection-note').text
        assert 'UNVERIFIED_BASELINE' in browser.find_element(By.ID,'projection-source').get_attribute('textContent')
        assert 'HISTORICAL REPLAY' in browser.find_element(By.ID,'connection-badge').text
        Select(browser.find_element(By.ID,'projection-kind')).select_by_value('constructors')
        assert len(browser.find_elements(By.CSS_SELECTOR,'#projection-rows tr'))==11
        Select(browser.find_element(By.ID,'projection-scoring')).select_by_value('STOPPED_NOW')
        wait.until(lambda b:'needs scheduled laps' in b.find_element(By.ID,'projection-note').text)
        assert all(r.find_elements(By.TAG_NAME,'td')[-1].text=='—' for r in browser.find_elements(By.CSS_SELECTOR,'#projection-rows tr'))
        Select(browser.find_element(By.ID,'projection-scoring')).select_by_value('FULL_DISTANCE')
        checks.append({'check':'provisional_drivers_constructors_and_unknown_stopped_now_eligibility','passed':True})
        browser.execute_script('window.scrollTo(0,0)')
        browser.find_element(By.ID,'diagnostics-open').click();wait.until(lambda b:b.find_element(By.ID,'feed-diagnostics').is_displayed())
        assert 'HISTORICAL_REPLAY' in browser.find_element(By.ID,'diagnostics-context').text
        assert len(browser.find_elements(By.CSS_SELECTOR,'#diagnostics-rows tr'))>=6
        browser.save_screenshot(str(screens/'timing-diagnostics-desktop.png'))
        browser.find_element(By.ID,'diagnostics-close').click();assert not browser.find_element(By.ID,'feed-diagnostics').is_displayed()
        checks.append({'check':'diagnostics_dialog_observed_archive_channels_and_close','passed':True})
        Select(browser.find_element(By.ID,'favorite-driver')).select_by_value('16');wait.until(lambda b:b.find_element(By.ID,'driver-code').text=='LEC')
        assert browser.find_element(By.ID,'car-rpm') is not None
        browser.execute_script("document.querySelector('.rc-championship').scrollIntoView({block:'center'})")
        browser.save_screenshot(str(screens/'timing-projection-desktop.png'))
        for width in (320,390,768,1440,1920):
            browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':width,'height':1100,'deviceScaleFactor':1,'mobile':width<700})
            assert browser.execute_script('return document.documentElement.scrollWidth<=innerWidth'),width
            browser.execute_script("document.getElementById('diagnostics-open').click()")
            assert browser.execute_script("const r=document.getElementById('feed-diagnostics').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.height<=innerHeight"),width
            if width==390:browser.save_screenshot(str(screens/'timing-diagnostics-mobile.png'))
            browser.find_element(By.ID,'diagnostics-close').click()
            checks.append({'check':'new_controls_fit_without_page_overflow','width':width,'passed':True})
        errors=[e for e in browser.get_log('browser') if e['level']=='SEVERE' and 'favicon' not in e['message']]
        assert not errors,errors
        latencies=[];payloads=[]
        for _ in range(20):
            began=time.perf_counter();response=requests.get(args.backend+'/race-control/209/11731/frame',params={'mode':'REPLAY','at':at,'driver':16,'window':30},timeout=20)
            response.raise_for_status();latencies.append((time.perf_counter()-began)*1000);payloads.append(len(response.content))
        for endpoint in ('/race-control/providers','/race-control/health','/race-control/209/11731/diagnostics?mode=REPLAY','/race-control/209/11731/capabilities?mode=REPLAY'):
            assert requests.get(args.backend+endpoint,timeout=20).status_code==200
        assert requests.get(args.frontend+'/live-timing',timeout=20).status_code==404
        assert requests.get(args.frontend+'/screen-timing',timeout=20).status_code==404
        assert requests.get(args.frontend+'/race-control/api/sessions/refresh',timeout=20).status_code==200
        checks.append({'check':'new_api_and_kept_refresh_action_removed_extensions_remain_absent','passed':True})
        report={'verified_at':datetime.now(timezone.utc).isoformat(),'checks':checks,'browser_errors':errors,
                'performance':{'http_frames':len(latencies),'http_frame_ms_p50':statistics.median(latencies),
                    'http_frame_ms_p95':sorted(latencies)[math.ceil(len(latencies)*.95)-1], 'payload_bytes_p50':statistics.median(payloads)},
                'live_session_tested':False}
        (ROOT/'docs/LIVE_BROWSER_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    finally:browser.quit()


if __name__=='__main__':main()
