"""Check real rendered card bounds at desktop, tablet and phone widths."""
import json,time,argparse
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--frontend',default='http://127.0.0.1:8090');a=p.parse_args()
    opt=webdriver.ChromeOptions();opt.add_argument('--headless=new');opt.add_argument('--window-size=1440,1100');d=webdriver.Chrome(options=opt)
    report=[];images=ROOT/'docs/screenshots';images.mkdir(exist_ok=True)
    try:
        for width in [320,390,768,1440,1920]:
            d.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<700})
            for path in ['/','/races','/news','/drivers','/predictions','/championship']:
                d.get(a.frontend+path);WebDriverWait(d,20).until(lambda browser:browser.find_elements(By.CSS_SELECTOR,'main.container,.container'))
                time.sleep(.25)
                if path=='/':d.execute_script('document.querySelector(".home-news").scrollIntoView({block:"center"})');time.sleep(.6)
                result=d.execute_script('''return {viewport:innerWidth,document:document.documentElement.scrollWidth,newsCards:[...document.querySelectorAll('.news-card')].map(e=>{let p=e.querySelector('.news-image'),i=p.querySelector('img'),b=p.getBoundingClientRect(),ib=i.getBoundingClientRect();return {card:e.getBoundingClientRect().width,frame:b.width,image:ib.width,imageHeight:ib.height,frameHeight:b.height}})}''')
                assert result['document']<=width+1,(width,path,result)
                for card in result['newsCards']:
                    assert card['card']<=width and card['image']<=card['frame']+1 and card['imageHeight']<=card['frameHeight']+1,(width,path,card)
                assert "We couldn’t load the data" not in d.find_element(By.TAG_NAME,'body').text,path
                report.append({'width':width,'path':path,'passed':True,'news_card_count':len(result['newsCards'])})
                if width in (390,1440) and path in ('/','/races','/news','/drivers'):
                    if path=='/':
                        d.find_element(By.CSS_SELECTOR,'.home-news').screenshot(str(images/f'news-preview-{width}.png'))
                        d.execute_script('window.scrollTo(0,0)')
                    d.save_screenshot(str(images/f'final-{path.strip("/") or "dashboard"}-{width}.png'))
        d.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
        d.get(a.frontend+'/news');d.find_element(By.ID,'theme-toggle').click();time.sleep(.4)
        d.save_screenshot(str(images/'final-news-light.png'))
        d.find_element(By.ID,'theme-toggle').click()
        print(json.dumps({'checks':len(report),'results':report},indent=2))
        (ROOT/'docs/UI_LAYOUT_VERIFICATION.json').write_text(json.dumps({'checks':len(report),'results':report},indent=2)+'\n')
    finally:d.quit()
if __name__=='__main__':main()
