import os
from pathlib import Path
import pytest
from services.odds.providers.selenium.base_selenium_provider import SeleniumOddsProvider,parse_decimal,normalize_name

def test_decimal_parser_and_name_mapping():
    assert parse_decimal(' 4,50 ')==4.5
    assert normalize_name('Sérgio Pérez')=='sergioperez'
    with pytest.raises(ValueError):parse_decimal('5/2')

def test_quit_always_called_on_page_failure():
    class BrokenDriver:
        closed=False
        def set_page_load_timeout(self,n):pass
        def get(self,url):raise RuntimeError('page failed')
        def quit(self):self.closed=True
    driver=BrokenDriver();provider=SeleniumOddsProvider({'url':'https://fixture.invalid','row_selector':'.odds-row'},[],lambda:driver)
    with pytest.raises(RuntimeError):provider.fetch_race_odds({'race_id':1})
    assert driver.closed

@pytest.mark.skipif(os.getenv('RUN_SELENIUM')!='1',reason='Enable RUN_SELENIUM=1 for local Chrome fixture')
def test_real_selenium_fixture():
    from selenium import webdriver
    options=webdriver.ChromeOptions();options.add_argument('--headless=new')
    driver=webdriver.Chrome(options=options);closed=[];original=driver.quit
    def quit():
        closed.append(True);original()
    driver.quit=quit
    provider=SeleniumOddsProvider({'name':'local_fixture','url':Path(__file__).with_name('fixtures').joinpath('odds_page.html').as_uri(),'row_selector':'.odds-row','name_selector':'.name','odds_selector':'.price'},[{'driver_id':1,'driver_name':'Pilot One'},{'driver_id':2,'driver_name':'Pilot Two'}],lambda:driver)
    rows=provider.fetch_race_odds({'race_id':1})
    assert len(rows)==2;assert [r['driver_id'] for r in rows]==[1,2];assert [r['odds'] for r in rows]==[2.5,4];assert closed==[True]
