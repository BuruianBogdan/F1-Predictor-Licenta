from datetime import timedelta,date
import numpy as np
import pytest
from database.db import SessionLocal
from models.news import NewsArticle,NewsSignal,NewsCrawlRun
from models.driver import Driver
from models.race import Race
from services.news_service import NewsService
from services.news_impact_service import NewsImpactService
from services.season_service import iso,utcnow,parse_time
from ml.feature_engineering import FeatureEngineeringService
from services.prediction_service import PredictionService
from data_sources.news_provider import parse_article,allowed_article

ARTICLE={'source_url':'https://www.formula1.com/en/latest/article/test.abc','source_title':'Russell takes engine penalty in Singapore','source_excerpt':'Russell will start at the back of the grid.','source_hash':'abc','published_at':'2025-03-01T10:00:00+00:00','image_url':None}
def add_article(**overrides):
    values={**ARTICLE,'title':'Test','summary':'','summary_status':'pending','observed_at':'2025-03-01T11:00:00+00:00',**overrides}
    with SessionLocal.begin() as s:a=NewsArticle(**values);s.add(a);s.flush();return a.id

def test_parser_uses_public_metadata_and_rejects_paid_articles():
    html='''<h1>Unrelated page header</h1><script type="application/ld+json">{"@type":"NewsArticle","headline":"Russell takes grid penalty","datePublished":"2025-03-01T10:00:00Z","description":"Confirmed news","isAccessibleForFree":true}</script><div class="content-rich-text"><p>Driver will start last.</p></div><meta property="og:image" content="https://evil.example/image.jpg">'''
    parsed=parse_article(html,ARTICLE['source_url'])
    assert parsed['source_title']=='Russell takes grid penalty'
    assert 'Driver will start last.' in parsed['source_excerpt'] and parsed['image_url'] is None
    assert parse_article(html.replace('true','false'),ARTICLE['source_url']) is None
    assert not allowed_article('https://www.formula1.com.evil.com/en/latest/article/test')
    assert not allowed_article('https://www.formula1.com/en/subscribe')

def test_crawl_is_idempotent_and_summary_failure_preserves_article():
    class Provider:
        def fetch(self,**kwargs):return {'articles':[ARTICLE],'errors':[],'discovered':1}
    class Editor:
        def ensure_runtime(self):pass
        def rewrite(self,a):raise TimeoutError('LLM offline')
    result=NewsService().crawl(Provider(),Editor())
    assert result['status']=='PARTIAL' and result['added']==1
    assert NewsService().crawl(Provider(),Editor())['added']==0
    feed=NewsService().feed()
    assert len(feed)==1 and feed[0]['summary_status']=='pending'
    assert 'source_excerpt' not in feed[0]
    class Ready(Editor):
        def rewrite(self,a):return {'title':'Titlu','summary':'Rezumat scurt. A doua frază.','summary_status':'rewritten','summary_model':'test','language':'ro'}
    assert NewsService().crawl(Provider(),Ready())['rewritten']==1
    assert NewsService().feed()[0]['summary']=='Rezumat scurt. A doua frază.'

def test_crawler_failure_is_recorded_and_next_run_scheduled():
    class Failed:
        def fetch(self,**kwargs):raise RuntimeError('Network unavailable')
    result=NewsService().crawl(Failed())
    assert result['status']=='FAILED'
    with SessionLocal() as s:assert s.query(NewsCrawlRun).one().completed_at
    assert parse_time(NewsService().settings()['next_run_at'])>utcnow()

def signal_for(frame,article_id,**overrides):
    cutoff=parse_time(frame['feature_cutoff'])
    data={'article_id':article_id,'race_id':frame['race']['race_id'],'driver_id':1,'kind':'confirmed_grid_penalty','log_weight':-.12,'evidence':'Confirmed penalty','observed_at':iso(cutoff-timedelta(hours=1)),'published_at':iso(cutoff-timedelta(hours=2)),'expires_at':iso(cutoff+timedelta(days=3)),**overrides}
    with SessionLocal.begin() as s:s.add(NewsSignal(**data))

def test_news_changes_forecast_preserves_base_and_normalizes(race_field):
    frame=FeatureEngineeringService().build(race_field['target']);service=PredictionService()
    base=service.predict_race(race_field['target'],persist=False)
    signal_for(frame,add_article())
    changed=service.predict_race(race_field['target'],persist=False)
    assert changed['news_factor_used']
    before={p['driver_id']:p['win_probability'] for p in base['predictions']}
    for p in changed['predictions']:assert p['base_model_probability']==before[p['driver_id']]
    assert next(p['win_probability'] for p in changed['predictions'] if p['driver_id']==1)<before[1]
    assert sum(p['win_probability'] for p in changed['predictions'])==pytest.approx(1)
    assert sum(p['news_delta'] for p in changed['predictions'])==pytest.approx(0)

@pytest.mark.parametrize('field',['observed_at','published_at','expires_at'])
def test_future_or_expired_news_cannot_enter_replay(race_field,field):
    frame=FeatureEngineeringService().build(race_field['target']);cutoff=parse_time(frame['feature_cutoff'])
    stamp=iso(cutoff+timedelta(seconds=1)) if field!='expires_at' else iso(cutoff)
    signal_for(frame,add_article(),**{field:stamp})
    probabilities=np.ones(len(frame['rows']))/len(frame['rows'])
    adjusted,_,metadata=NewsImpactService().apply(frame,probabilities)
    np.testing.assert_array_equal(adjusted,probabilities)
    assert not metadata['news_factor_used']

def test_repeated_penalty_reporting_does_not_multiply_effect(race_field):
    frame=FeatureEngineeringService().build(race_field['target']);probabilities=np.ones(len(frame['rows']))/len(frame['rows'])
    signal_for(frame,add_article())
    first,_,_=NewsImpactService().apply(frame,probabilities)
    signal_for(frame,add_article(source_url=ARTICLE['source_url']+'2'))
    second,_,meta=NewsImpactService().apply(frame,probabilities)
    np.testing.assert_array_equal(first,second);assert len(meta['news_signal_ids'])==1

def test_only_confirmed_race_specific_penalty_is_extracted(race_field):
    with SessionLocal.begin() as s:
        r=s.get(Race,race_field['target']);r.race_name='Singapore Grand Prix';r.start_at='2025-03-05T12:00:00+00:00';r.is_completed=0;r.race_status='SCHEDULED'
        s.get(Driver,1).surname='Russell'
    service=NewsImpactService()
    assert service.extract(add_article())==1
    assert service.extract(add_article(source_url=ARTICLE['source_url']+'2',source_title='Russell could take engine penalty in Singapore'))==0
    assert service.extract(add_article(source_url=ARTICLE['source_url']+'3',source_title='Russell avoids grid penalty in Singapore'))==0
    assert service.extract(add_article(source_url=ARTICLE['source_url']+'4',source_title='Russell takes engine penalty in Monaco'))==0

def test_automation_pause_and_interval_validation():
    assert not NewsService().configure(False)['enabled']
    assert NewsService().settings()['next_run_at'] is None
    with pytest.raises(ValueError):NewsService().configure(True,1)
    assert NewsService().configure(True,30)['enabled']

def test_rewriter_rejects_numbers_not_in_source(monkeypatch):
    from services.news_rewriter import NewsRewriter
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'response':'{"title":"Penalizare de 99 de locuri", "summary":"Russell va pleca din spate în Singapore. El speră să avanseze în cursă."}'}
    monkeypatch.setattr('services.news_rewriter.requests.post',lambda *a,**kw:Response())
    with pytest.raises(ValueError,match='unsupported numbers'):NewsRewriter().rewrite(ARTICLE)

def test_rewriter_does_not_claim_unsupported_translation(monkeypatch):
    monkeypatch.setenv("NEWS_LANGUAGE","ro")
    from services.news_rewriter import NewsRewriter
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'response':'{"title":"Penalty confirmed", "summary":"Russell starts at the back of the field. He hopes to recover during the race."}'}
    monkeypatch.setattr('services.news_rewriter.requests.post',lambda *a,**kw:Response())
    with pytest.raises(ValueError,match='English briefs'):NewsRewriter().rewrite(ARTICLE)

def test_listing_excludes_gated_and_promotional_cards_even_with_duplicate_links():
    import base64,json
    from data_sources.news_provider import discover_articles
    gated='/en/latest/article/locked.123';public='/en/latest/article/public.456';ad='/en/latest/article/sponsor.789'
    def metadata(value):return base64.b64encode(json.dumps(value).encode()).decode()
    html=f'<a href="{gated}"><img/></a><a href="{gated}" data-f1rd-a7s-context="{metadata({"is_protected_status":True})}">Locked</a><a href="{public}">Public</a><a href="{ad}" data-f1rd-a7s-context="{metadata({"content_primary_tag":"Betting"})}">Ad</a>'
    assert discover_articles(html)==['https://www.formula1.com'+public]
    assert discover_articles(html,['https://www.formula1.com'+public])==[]

def test_saved_articles_can_be_rewritten_when_source_is_offline():
    add_article()
    class Offline:
        def fetch(self,**kwargs):raise ConnectionError('Source unavailable')
    class Editor:
        def ensure_runtime(self):pass
        def rewrite(self,a):return {'title':'Titlu','summary':'Rezumat bazat pe articolul salvat.','summary_status':'rewritten','summary_model':'test','language':'ro'}
    result=NewsService().crawl(Offline(),Editor())
    assert result['status']=='PARTIAL' and result['rewritten']==1
    assert NewsService().feed()[0]['summary_status']=='rewritten'

def test_rewriter_does_not_publish_a_failed_consistency_check(monkeypatch):
    from services.news_rewriter import NewsRewriter
    editor=NewsRewriter();outputs=iter([{'title':'Russell to start last','summary':'Russell will start from the back of the field.'},{'supported':False,'reason':'Unsupported wording'}])
    monkeypatch.setattr(editor,'_generate',lambda *args:next(outputs))
    with pytest.raises(ValueError,match='consistency check'):editor.rewrite(ARTICLE)

def test_strong_performance_cannot_be_rewritten_as_a_race_win(monkeypatch):
    from services.news_rewriter import NewsRewriter
    editor=NewsRewriter()
    monkeypatch.setattr(editor,'_generate',lambda *args:{'title':'Alonso wins Bahrain','summary':'Aston Martin hopes to build on Alonso winning in Bahrain.'})
    article={**ARTICLE,'source_title':'Aston Martin hopes for another strong weekend','source_excerpt':'Aston Martin hopes to build on an impressive performance by Fernando Alonso.'}
    with pytest.raises(ValueError,match='unsupported result'):editor.rewrite(article)

def test_unspecified_upgrades_cannot_become_engine_upgrades(monkeypatch):
    from services.news_rewriter import NewsRewriter
    editor=NewsRewriter()
    monkeypatch.setattr(editor,'_generate',lambda *args:{'title':'Mercedes introduces engine upgrades','summary':'Mercedes aims to extract more from its new engine.'})
    article={**ARTICLE,'source_title':'Mercedes explores its upgrade package','source_excerpt':'Mercedes is continuing to improve its latest upgrade package.'}
    with pytest.raises(ValueError,match='unsupported result'):editor.rewrite(article)
