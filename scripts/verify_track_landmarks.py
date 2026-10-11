"""Real-browser verification of labels attached to dots and measured circuit landmarks."""
import json, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8090'
API = 'http://127.0.0.1:5000'
def epoch(value): return datetime.fromisoformat(value).timestamp()

def main():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new'); options.add_argument('--window-size=1600,1250')
    options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
    d = webdriver.Chrome(options=options); checks = []
    def load(race, code, at, paused=True):
        d.get(f'{BASE}/race-control/{race}?session={code}&autostart=true&at={at}&paused={str(paused).lower()}')
        WebDriverWait(d, 40).until(lambda b: len(b.find_elements(By.CSS_SELECTOR, '#timing-rows tr')) == 22)
        WebDriverWait(d, 20).until(lambda b: b.find_elements(By.CSS_SELECTOR, '.rc-start-line') and b.find_elements(By.CSS_SELECTOR, '.rc-pit-path'))
    snapshot = """return [...document.querySelectorAll('.rc-driver-label')].filter(e=>e.style.display!=='none').map(e=>{
      const dot=document.querySelector('.rc-car[data-driver="'+e.dataset.driver+'"]'),a=dot.transform.baseVal.consolidate().matrix,b=e.transform.baseVal.consolidate().matrix,w=Number(e.querySelector('rect').getAttribute('width'));
      return {id:e.dataset.driver,x:a.e,y:a.f,lx:b.e,ly:b.f,cx:b.e+w/2,cy:b.f+11,w};});"""
    try:
        for race, code, key, at in [(210, 'FP1', 11378, epoch('2026-10-09T08:54:36+00:00')),
                                    (210, 'SQ', 11379, epoch('2026-10-09T13:30:20+00:00')),
                                    (209, 'R', 11731, epoch('2026-10-04T09:56:30+00:00'))]:
            load(race, code, at)
            frame = requests.get(f'{API}/race-control/{race}/{key}/frame', params={'mode': 'REPLAY', 'at': at, 'driver': 63}, timeout=20).json()
            assert frame['track']['start_finish']['approximate']
            assert frame['track']['pit_lane']['points'][0] != frame['track']['pit_lane']['points'][-1]
            assert not d.find_element(By.CSS_SELECTOR, '.rc-pit-path').get_attribute('d').endswith('Z')
            assert len(d.find_elements(By.CSS_SELECTOR, '.rc-pit-marker')) == 2
            if code == 'R':
                assert next(r for r in frame['rows'] if r['driver_number'] == 63)['in_pit']
            checks.append({'check': 'measured_start_finish_and_distinct_entry_exit_pit_path', 'session_key': key, 'passed': True})
        sq_at = epoch('2026-10-09T13:30:20+00:00'); load(210, 'SQ', sq_at, paused=False)
        moving = 0; before = {}; max_distance = 0
        for _ in range(22):
            rows = d.execute_script(snapshot)
            for r in rows:
                # Constant close attachment, with at most 8 px of forward direction adjustment.
                assert abs(r['cx'] - r['x']) <= 8.01, r
                assert -35.01 <= r['cy'] - r['y'] <= -18.99, r
                assert 8 <= r['lx'] and r['lx'] + r['w'] <= 792
                if r['id'] in before and abs(r['x'] - before[r['id']]['x']) > .05:
                    moving += 1
                max_distance = max(max_distance, ((r['cx'] - r['x'])**2 + (r['cy'] - r['y'])**2)**.5)
            before = {r['id']: r for r in rows}; time.sleep(.2)
        assert moving > 30
        d.find_element(By.ID, 'play-pause').click()
        # Find an exposed chip and click its actual screen coordinates.
        target = d.execute_script("""for(const e of document.querySelectorAll('.rc-driver-label')){
          if(e.style.display==='none')continue;const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;
          if(document.elementFromPoint(x,y)?.closest('.rc-driver-label')===e)return {id:e.dataset.driver,x,y};}return null;""")
        assert target
        d.execute_cdp_cmd('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': target['x'], 'y': target['y'], 'button': 'left', 'clickCount': 1})
        d.execute_cdp_cmd('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': target['x'], 'y': target['y'], 'button': 'left', 'clickCount': 1})
        WebDriverWait(d, 15).until(lambda b: b.find_element(By.ID, 'favorite-driver').get_attribute('value') == target['id'])
        checks.append({'check': 'readable_clickable_labels_stay_close_to_their_own_moving_dot', 'moving_updates': moving, 'maximum_anchor_distance_svg_px': round(max_distance, 2), 'passed': True})
        d.execute_script("document.querySelector('.rc-track-panel').scrollIntoView({block:'start'})"); time.sleep(.3)
        d.save_screenshot(str(ROOT / 'docs/screenshots/race-control-attached-labels.png'))
        for width in [320, 390, 768, 1440, 1920]:
            d.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': width < 700})
            assert d.execute_script('return document.documentElement.scrollWidth<=innerWidth'), width
            assert d.find_element(By.CSS_SELECTOR, '.rc-pit-path').is_displayed()
            checks.append({'check': 'circuit_landmarks_and_labels_fit_viewport', 'width': width, 'passed': True})
            if width == 390:
                d.execute_script("document.querySelector('.rc-track-panel').scrollIntoView({block:'start'})"); time.sleep(.3)
                d.find_element(By.CSS_SELECTOR, '.rc-track-panel').screenshot(str(ROOT / 'docs/screenshots/race-control-landmarks-mobile.png'))
        errors = [e for e in d.get_log('browser') if e['level'] == 'SEVERE' and 'favicon' not in e['message']]
        assert not errors, errors
        report = {'verified_at': datetime.now(timezone.utc).isoformat(), 'source': 'Actual cached Singapore FP1/SQ and Malaysian GP position data', 'checks': checks,
                  'browser_errors': errors, 'limitations': ['Landmarks follow approximate measured trajectories and flying-lap timing boundaries, not a surveyed FIA map.',
                  'A pit path is unavailable when the source has no complete, distinguishable pit-lane trajectory.', 'Overlapping labels are intentionally accepted; no neighbour-based repositioning.']}
        (ROOT / 'docs/TRACK_MAP_VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        d.quit()

if __name__ == '__main__': main()
