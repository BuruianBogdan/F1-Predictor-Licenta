"""Explicit local end-to-end smoke check. Persists prediction runs, never changes race facts."""
import argparse,json,math
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backend',default='http://127.0.0.1:5000');parser.add_argument('--frontend',default='http://127.0.0.1:8090');parser.add_argument('--browser',action='store_true');args=parser.parse_args()
    outcomes=[]
    def get(path):
        r=requests.get(args.backend+path,timeout=60);r.raise_for_status();return r.json()
    def post(path,data):
        r=requests.post(args.backend+path,json=data,timeout=60);r.raise_for_status();return r.json()
    health=get('/health');assert health['database']=='ok';outcomes.append({'check':'health','result':health})
    context=get('/season/context');latest=context['latest_completed_race'];upcoming=context['next_race'];assert latest and upcoming
    quality=get('/data/quality');assert quality['healthy'];outcomes.append({'check':'data_quality','passed':True})
    paths=['/','/predictions','/championship','/drivers','/constructors','/circuits','/races','/news','/results','/standings','/data','/model','/history','/simulator','/regulations','/export',f"/races/{latest['race_id']}",f"/races/{upcoming['race_id']}"]
    detail=get(f"/races/{latest['race_id']}/detail");winner=detail['winner'];assert winner
    paths.append(f"/drivers/{winner['driver_id']}")
    for path in paths:
        response=requests.get(args.frontend+path,timeout=60);assert response.status_code==200,(path,response.status_code);assert 'Whitelabel Error Page' not in response.text
    calendar=get('/calendar');assert calendar['next']['race_id']==upcoming['race_id']
    assert all(r['circuit']['layout_available'] for group in ('upcoming','completed') for r in calendar[group])
    assert [r['date'] for r in calendar['upcoming']]==sorted(r['date'] for r in calendar['upcoming'])
    news=get('/news');assert news['status']['enabled'];assert news['articles']
    assert all('source_excerpt' not in a for a in news['articles'])
    outcomes.append({'check':'news_and_circuit_calendar','articles':len(news['articles']),'llm':news['status']['llm'],'next_race':upcoming['race_id']})
    outcomes.append({'check':'frontend_GET_pages','passed':len(paths)})
    base=get(f"/predict/race/{upcoming['race_id']}");assert math.isclose(sum(p['win_probability'] for p in base['predictions']),1,abs_tol=1e-9)
    availability=get('/predict/availability?season='+str(context['active_season']))
    if not availability[str(upcoming['race_id'])]['post_qualifying_available']:
        response=requests.post(args.frontend+'/predictions',data={'raceId':upcoming['race_id'],'season':context['active_season'],'mode':'POST_QUALIFYING'},timeout=60)
        assert response.status_code==200 and 'prediction-validation' in response.text and 'Pre-weekend is selected' in response.text
        assert 'We couldn’t load the data' not in response.text
        outcomes.append({'check':'unavailable_qualifying_keeps_form','passed':True})
    assert all(0<=p['win_probability']<=p['podium_probability']<=p['points_probability']<=1 for p in base['predictions'])
    no_market=post(f"/predict/race/{upcoming['race_id']}/market",{'odds':[]});assert no_market['market_factor_used'] is False
    odds=[{'driver_id':p['driver_id'],'odds':3+i} for i,p in enumerate(base['predictions'][:3])]
    market=post(f"/predict/race/{upcoming['race_id']}/market",{'odds':odds});assert market['market_factor_used'];assert math.isclose(sum(p['final_probability'] for p in market['predictions']),1,abs_tol=1e-9)
    championship=get('/predict/championship?simulations=500');assert math.isclose(sum(d['championship_probability'] for d in championship['drivers']),1,abs_tol=1e-9)
    if base['news_factor_used']:
        assert upcoming['race_id'] in championship['news_adjusted_races']
        assert any(p['news_delta']<0 for p in base['predictions'] if p['news_signals'])
        outcomes.append({'check':'news_adjusts_race_and_championship','signal_ids':base['news_signal_ids'],'passed':True})
    explanation=post('/explanations/prediction/'+base['prediction_run_id'],{});assert explanation['text'];outcomes.append({'check':'llm','source':explanation['source']})
    for path,data in [('/predictions',{'raceId':upcoming['race_id'],'season':context['active_season'],'mode':'PRE_WEEKEND'}),('/predictions',{'raceId':latest['race_id'],'season':context['active_season'],'mode':'POST_QUALIFYING'}),('/championship',{}),(f"/races/{latest['race_id']}/story",{}),('/history/evaluate',{}),('/data/action',{'action':'quality'})]:
        response=requests.post(args.frontend+path,data=data,timeout=120);assert response.status_code==200,(path,response.status_code,response.text[:100]);outcomes.append({'check':'frontend_POST','path':path,'passed':True})
    if args.browser:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        options=webdriver.ChromeOptions();options.add_argument('--headless=new');options.add_argument('--window-size=1440,1100');options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
        driver=webdriver.Chrome(options=options)
        try:
            driver.execute_cdp_cmd('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
            driver.get(args.frontend+'/');WebDriverWait(driver,15).until(EC.presence_of_element_located((By.CSS_SELECTOR,'.winner-hero')))
            assert winner['driver_name'].casefold() in driver.find_element(By.CSS_SELECTOR,'.driver-heading').text.casefold()
            driver.save_screenshot(str(ROOT/'docs/screenshots/dashboard-desktop.png'))
            driver.find_element(By.ID,'theme-toggle').click();assert driver.find_element(By.TAG_NAME,'html').get_attribute('data-theme')=='light'
            driver.save_screenshot(str(ROOT/'docs/screenshots/dashboard-light.png'))
            from selenium.webdriver.support.ui import Select
            Select(driver.find_element(By.ID,'lang-select')).select_by_value('ro');assert driver.find_element(By.CSS_SELECTOR,'[data-i18n="latest.winner"]').text=='CÂȘTIGĂTORUL ULTIMEI CURSE'
            Select(driver.find_element(By.ID,'lang-select')).select_by_value('en');driver.find_element(By.ID,'theme-toggle').click()
            driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True});driver.get(args.frontend+'/')
            assert driver.execute_script('return window.innerWidth')==390
            assert driver.execute_script('return document.documentElement.scrollWidth<=window.innerWidth'), 'Horizontal overflow at mobile viewport'
            driver.save_screenshot(str(ROOT/'docs/screenshots/dashboard-mobile.png'))
            driver.execute_cdp_cmd('Emulation.clearDeviceMetricsOverride',{});driver.set_window_size(1440,1100);driver.get(args.frontend+'/predictions')
            qualifying_option=driver.find_element(By.CSS_SELECTOR,'#mode option[value="POST_QUALIFYING"]')
            if not availability[str(upcoming['race_id'])]['post_qualifying_available']:
                assert not qualifying_option.is_enabled()
                assert driver.find_element(By.ID,'qualifying-note').is_displayed()
                if availability[str(latest['race_id'])]['post_qualifying_available']:
                    Select(driver.find_element(By.ID,'raceId')).select_by_value(str(latest['race_id']))
                    assert qualifying_option.is_enabled()
                    Select(driver.find_element(By.ID,'mode')).select_by_value('POST_QUALIFYING')
                    Select(driver.find_element(By.ID,'raceId')).select_by_value(str(upcoming['race_id']))
                    assert driver.find_element(By.ID,'mode').get_attribute('value')=='PRE_WEEKEND'
                    assert not qualifying_option.is_enabled()
            driver.find_element(By.CSS_SELECTOR,'button[data-i18n="run.prediction"]').click();WebDriverWait(driver,25).until(EC.presence_of_element_located((By.CSS_SELECTOR,'.forecast-card')))
            driver.save_screenshot(str(ROOT/'docs/screenshots/predictions.png'))
            assert len(driver.find_elements(By.CSS_SELECTOR,'.forecast-card'))==3
            errors=[e for e in driver.get_log('browser') if e['level']=='SEVERE' and 'favicon.ico' not in e['message']]
            assert not errors,errors
            outcomes.append({'check':'selenium_UI','passed':True,'screenshots':'docs/screenshots'})
        finally:driver.quit()
    outcomes.append({'check':'forecast_probabilities','passed':True,'drivers':len(base['predictions']),'model':base['model_version'],'championship_simulations':championship['simulations']})
    report={'verified_at':context['as_of'],'context':context,'outcomes':outcomes}
    (ROOT/'docs/E2E_VERIFICATION.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
