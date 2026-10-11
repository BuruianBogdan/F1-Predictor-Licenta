"""Persistent, attributed news with a single local crawler worker."""
import logging,os,threading,fcntl
from datetime import timedelta
from sqlalchemy import or_
from config import DATA_DIR
from database.db import SessionLocal
from models.news import NewsArticle,NewsSignal,NewsCrawlRun,NewsAutomation
from services.season_service import utcnow,iso,parse_time
from services.news_rewriter import NewsRewriter

log=logging.getLogger(__name__)
class NewsService:
    def settings(self):
        with SessionLocal.begin() as s:
            cfg=s.get(NewsAutomation,1)
            if not cfg:
                cfg=NewsAutomation(id=1,enabled=1,interval_minutes=30);s.add(cfg);s.flush()
            return {'enabled':bool(cfg.enabled) and os.getenv('NEWS_AUTO_ENABLED','true').lower()=='true','interval_minutes':cfg.interval_minutes,'next_run_at':cfg.next_run_at}
    def configure(self,enabled,interval=30):
        if not isinstance(enabled,bool) or not 15<=interval<=1440:raise ValueError('Use a boolean enabled flag and a 15–1440 minute interval')
        self.settings()
        with SessionLocal.begin() as s:
            cfg=s.get(NewsAutomation,1);cfg.enabled=int(enabled);cfg.interval_minutes=interval;cfg.next_run_at=iso(utcnow()) if enabled else None
        return self.settings()
    def status(self):
        cfg=self.settings()
        with SessionLocal() as s:
            runs=s.query(NewsCrawlRun).order_by(NewsCrawlRun.id.desc()).limit(5).all()
            count=s.query(NewsArticle).count();pending=s.query(NewsArticle).filter_by(summary_status='pending').count()
        return {**cfg,'source':'Formula 1','source_url':'https://www.formula1.com/en/latest','llm':NewsRewriter().status(),'article_count':count,'pending_summaries':pending,'runs':[{'id':r.id,'status':r.status,'started_at':r.started_at,'completed_at':r.completed_at,'data':r.data} for r in runs]}
    def feed(self,limit=24):
        with SessionLocal() as s:
            articles=s.query(NewsArticle).order_by(NewsArticle.published_at.desc(),NewsArticle.id.desc()).limit(limit).all()
            signals=s.query(NewsSignal).filter(NewsSignal.article_id.in_([a.id for a in articles])).all()
        return [{k:getattr(a,k) for k in ('id','source_url','source_title','title','summary','image_url','published_at','observed_at','summary_status','summary_model','language','source')} | {'signals':[{'kind':x.kind,'race_id':x.race_id,'driver_id':x.driver_id,'log_weight':x.log_weight,'evidence':x.evidence} for x in signals if x.article_id==a.id]} for a in articles]
    def crawl(self,provider=None,rewriter=None):
        # An OS lock also protects against another Flask process or a simultaneous CLI refresh.
        DATA_DIR.mkdir(parents=True,exist_ok=True)
        with (DATA_DIR/'news-crawler.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return {'status':'ALREADY_RUNNING'}
            return self._crawl(provider,rewriter)
    def _crawl(self,provider,rewriter):
        from data_sources.news_provider import Formula1NewsProvider
        from services.news_impact_service import NewsImpactService
        cfg=self.settings();now=iso(utcnow());summary={'added':0,'rewritten':0,'signals':0,'errors':[]}
        with SessionLocal.begin() as s:
            # A process may have stopped in the middle of a previous run.
            for old in s.query(NewsCrawlRun).filter_by(status='RUNNING'):old.status='INTERRUPTED';old.completed_at=now
            run=NewsCrawlRun(started_at=now,status='RUNNING',data=summary);s.add(run);s.flush();run_id=run.id
            known=[url for (url,) in s.query(NewsArticle.source_url).all()]
        status='SUCCESS'
        try:
            try:
                fetched=(provider or Formula1NewsProvider()).fetch(known_urls=known,limit=10)
            except Exception as exc:
                log.warning('News source unavailable: %s',type(exc).__name__)
                fetched={'articles':[],'errors':[{'stage':'crawl','error':type(exc).__name__}],'discovered':0}
                status='FAILED'
            summary['errors'].extend(fetched['errors']);summary['discovered']=fetched['discovered']
            for raw in fetched['articles']:
                observed=utcnow()
                if parse_time(raw['published_at'])>observed:continue
                with SessionLocal.begin() as s:
                    if s.query(NewsArticle).filter_by(source_url=raw['source_url']).first():continue
                    article=NewsArticle(**raw,title=raw['source_title'],summary='',observed_at=iso(observed),summary_status='pending')
                    s.add(article);s.flush();article_id=article.id
                summary['added']+=1
                summary['signals']+=NewsImpactService().extract(article_id)
            editor=rewriter or NewsRewriter();editor.ensure_runtime()
            with SessionLocal() as s:
                refresh=NewsArticle.summary_status=='pending'
                if hasattr(editor,'model'):
                    refresh=or_(refresh,NewsArticle.summary_model!=editor.model,NewsArticle.language!=os.getenv('NEWS_LANGUAGE','en'))
                pending=s.query(NewsArticle).filter(refresh).order_by(NewsArticle.id.desc()).limit(12).all()
            for article in pending:
                try:
                    rewritten=editor.rewrite({'source_title':article.source_title,'source_excerpt':article.source_excerpt})
                    with SessionLocal.begin() as s:
                        saved=s.get(NewsArticle,article.id)
                        for key,value in rewritten.items():setattr(saved,key,value)
                    summary['rewritten']+=1
                except Exception as exc:
                    log.warning('News summary %s: %s',article.id,type(exc).__name__)
                    summary['errors'].append({'article_id':article.id,'stage':'summary','error':type(exc).__name__})
            if summary['errors'] and (status!='FAILED' or summary['rewritten']):status='PARTIAL'
        except Exception as exc:
            log.exception('News crawl failed');status='FAILED';summary['errors'].append({'stage':'crawl','error':type(exc).__name__})
        finally:
            with SessionLocal.begin() as s:
                run=s.get(NewsCrawlRun,run_id);run.status=status;run.completed_at=iso(utcnow());run.data=summary
                cfg=s.get(NewsAutomation,1);cfg.next_run_at=iso(utcnow()+timedelta(minutes=cfg.interval_minutes)) if cfg.enabled else None
        return {'id':run_id,'status':status,**summary}

class NewsScheduler:
    _thread=None
    @classmethod
    def start(cls):
        if cls._thread and cls._thread.is_alive():return
        if os.getenv('NEWS_AUTO_ENABLED','true').lower()!='true':return
        def work():
            stop=threading.Event();stop.wait(5)
            while True:
                try:
                    service=NewsService();cfg=service.settings()
                    if cfg['enabled'] and (not cfg['next_run_at'] or parse_time(cfg['next_run_at'])<=utcnow()):service.crawl()
                except Exception:log.exception('News scheduler cycle failed')
                stop.wait(15)
        cls._thread=threading.Thread(target=work,name='f1-news',daemon=True);cls._thread.start()
