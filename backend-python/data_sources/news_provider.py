"""Public Formula1.com pages rendered with Selenium. Bounded, attributed ingestion."""
import base64,hashlib,json,time
from urllib.parse import urljoin,urlparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from services.season_service import parse_time,iso
from data_sources.base_provider import ProviderError

BASE='https://www.formula1.com'

def allowed_article(url):
    parsed=urlparse(url)
    return parsed.scheme=='https' and parsed.netloc=='www.formula1.com' and parsed.path.startswith('/en/latest/article/')

def parse_article(html,url):
    soup=BeautifulSoup(html,'html.parser');metadata={}
    for script in soup.select('script[type="application/ld+json"]'):
        try:raw=json.loads(script.string or script.get_text())
        except (ValueError,TypeError):continue
        candidates=raw if isinstance(raw,list) else ([raw]+raw.get('@graph',[]) if isinstance(raw,dict) else [])
        for item in candidates:
            if isinstance(item,dict) and item.get('@type')=='NewsArticle':metadata=item
    if str(metadata.get('isAccessibleForFree','true')).lower()=='false':return None
    title=metadata.get('headline') or (soup.h1.get_text(' ',strip=True) if soup.h1 else None)
    published=metadata.get('datePublished')
    if not title or not published:raise ProviderError('Article title/publication timestamp missing; not ingested')
    description=metadata.get('description','')
    paragraphs=[p.get_text(' ',strip=True) for p in soup.select('.content-rich-text p')]
    # Keep a bounded source context privately; only short rewritten summaries are published.
    excerpt=(' '.join([description]+paragraphs))[:3200]
    image=soup.select_one('meta[property="og:image"]')
    image_url=image.get('content') if image else None
    if not image_url or urlparse(image_url).netloc!='media.formula1.com':image_url=None
    return {'source_url':url,'source_title':title,'published_at':iso(parse_time(published)),'source_excerpt':excerpt,'image_url':image_url,'source_hash':hashlib.sha256(excerpt.encode()).hexdigest()}

def discover_articles(html,known_urls=()):
    """Use public listing metadata to skip gated/live/promotional cards before navigation."""
    soup=BeautifulSoup(html,'html.parser');urls=[];excluded=set()
    for a in soup.select('a[href*="/en/latest/article/"]'):
        url=urljoin(BASE,a['href']).split('?')[0]
        if not allowed_article(url):continue
        try:
            context=json.loads(base64.b64decode(a.get('data-f1rd-a7s-context','')).decode())
            if context.get('is_protected_status') is True or context.get('isLive') is True or context.get('content_primary_tag') in ('Unlocked','Betting'):
                excluded.add(url)
        except (ValueError,UnicodeDecodeError):pass
        if url not in urls and url not in known_urls and 'higher-or-lower' not in url:urls.append(url)
    return [url for url in urls if url not in excluded]

class Formula1NewsProvider:
    def __init__(self,driver_factory=None):self.driver_factory=driver_factory
    def fetch(self,known_urls=(),limit=10):
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        robot=RobotFileParser();response=requests.get(BASE+'/robots.txt',headers={'User-Agent':'F1Predictor/2.0'},timeout=20);response.raise_for_status();robot.parse(response.text.splitlines())
        if not robot.can_fetch('F1Predictor',BASE+'/en/latest'):raise ProviderError('News source does not allow this crawl path')
        options=webdriver.ChromeOptions();options.add_argument('--headless=new');options.add_argument('--window-size=1440,1000');options.page_load_strategy='eager'
        driver=None;articles=[];errors=[]
        try:
            driver=self.driver_factory() if self.driver_factory else webdriver.Chrome(options=options)
            driver.set_page_load_timeout(35);driver.get(BASE+'/en/latest')
            WebDriverWait(driver,25).until(EC.presence_of_element_located((By.CSS_SELECTOR,'a[href*="/en/latest/article/"]')))
            urls=discover_articles(driver.page_source,known_urls)
            for url in urls[:max(limit*2,limit)]:
                if len(articles)>=limit:break
                if not robot.can_fetch('F1Predictor',url):continue
                time.sleep(2)
                try:
                    driver.get(url);WebDriverWait(driver,20).until(EC.presence_of_element_located((By.CSS_SELECTOR,'h1')))
                    if not allowed_article(driver.current_url):continue
                    article=parse_article(driver.page_source,url)
                    if article:articles.append(article)
                except Exception as exc:errors.append({'url':url,'error':type(exc).__name__})
            return {'articles':articles,'errors':errors,'discovered':len(urls)}
        finally:
            if driver is not None:driver.quit()
