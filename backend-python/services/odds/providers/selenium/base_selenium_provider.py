"""Read-only configurable page object. No login, CAPTCHA bypass or evasion."""
import os,re,unicodedata
from services.odds.base import OddsProvider
from services.season_service import iso,utcnow

def normalize_name(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.lower()) if not unicodedata.combining(c) and c.isalnum())
def parse_decimal(text):
    value=text.strip().replace(',','.')
    if not re.fullmatch(r'\d+(?:\.\d+)?',value):raise ValueError('Not decimal odds')
    return float(value)

class SeleniumOddsProvider(OddsProvider):
    def __init__(self,source,drivers,driver_factory=None):
        self.source=source;self.name=source.get('name','selenium');self.drivers=drivers;self.driver_factory=driver_factory
    def is_available(self):return bool(self.source.get('url') and self.source.get('row_selector'))
    def fetch_race_odds(self,race):
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        if not self.is_available():return []
        options=webdriver.ChromeOptions()
        if os.getenv('SELENIUM_HEADLESS','true').lower()=='true':options.add_argument('--headless=new')
        options.add_argument('--window-size=1280,800')
        driver=None
        try:
            driver=self.driver_factory() if self.driver_factory else webdriver.Chrome(options=options)
            driver.set_page_load_timeout(int(os.getenv('SELENIUM_TIMEOUT_SECONDS','15')))
            driver.get(self.source['url'])
            elements=WebDriverWait(driver,int(os.getenv('SELENIUM_TIMEOUT_SECONDS','15'))).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR,self.source['row_selector'])))
            aliases={}
            for d in self.drivers:
                for value in (d['driver_name'],d.get('driver_ref',''),d.get('driver_code','')):
                    if value:aliases[normalize_name(value)]=d['driver_id']
            aliases.update({normalize_name(k):int(v) for k,v in self.source.get('aliases',{}).items()})
            rows=[];captured=iso(utcnow())
            for element in elements:
                name=element.find_element(By.CSS_SELECTOR,self.source['name_selector']).text
                raw=element.find_element(By.CSS_SELECTOR,self.source['odds_selector']).text
                mapped=aliases.get(normalize_name(name))
                if mapped is None:raise ValueError(f'Unmapped driver name: {name}')
                rows.append({'provider':self.name,'race_id':race['race_id'],'driver_id':mapped,'driver_name':name,'odds':parse_decimal(raw),'captured_at':captured,'source_url':self.source['url'],'raw_text':raw,'parsing_status':'parsed'})
            return rows
        finally:
            if driver is not None:driver.quit()
