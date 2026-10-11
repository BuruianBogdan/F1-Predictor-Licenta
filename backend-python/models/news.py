from sqlalchemy import Column,Integer,String,Float,ForeignKey,JSON
from database.db import Base

class NewsArticle(Base):
    __tablename__='news_articles'
    id=Column(Integer,primary_key=True)
    source_url=Column(String,nullable=False,unique=True)
    source_title=Column(String,nullable=False)
    title=Column(String,nullable=False)
    summary=Column(String,nullable=False)
    source_excerpt=Column(String,nullable=False)
    image_url=Column(String)
    published_at=Column(String)
    observed_at=Column(String,nullable=False)
    source_hash=Column(String,nullable=False)
    summary_status=Column(String,nullable=False,default='pending')
    summary_model=Column(String)
    language=Column(String,default='en')
    source=Column(String,default='Formula 1')

class NewsSignal(Base):
    __tablename__='news_signals'
    id=Column(Integer,primary_key=True)
    article_id=Column(Integer,ForeignKey('news_articles.id'),nullable=False)
    race_id=Column(Integer,ForeignKey('races.race_id'),nullable=False)
    driver_id=Column(Integer,ForeignKey('drivers.driver_id'))
    constructor_id=Column(Integer,ForeignKey('constructors.constructor_id'))
    kind=Column(String,nullable=False)
    log_weight=Column(Float,nullable=False)
    evidence=Column(String,nullable=False)
    observed_at=Column(String,nullable=False)
    published_at=Column(String,nullable=False)
    expires_at=Column(String,nullable=False)

class NewsCrawlRun(Base):
    __tablename__='news_crawl_runs'
    id=Column(Integer,primary_key=True)
    started_at=Column(String,nullable=False)
    completed_at=Column(String)
    status=Column(String,nullable=False)
    data=Column(JSON)

class NewsAutomation(Base):
    __tablename__='news_automation'
    id=Column(Integer,primary_key=True)
    enabled=Column(Integer,nullable=False,default=1)
    interval_minutes=Column(Integer,nullable=False,default=30)
    next_run_at=Column(String)
