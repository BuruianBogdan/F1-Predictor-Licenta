"""Explicit experimental news adjustments, not fitted or backtested model features."""
import re,math
from datetime import timedelta
import numpy as np
from database.db import SessionLocal
from models.news import NewsArticle,NewsSignal
from models.race import Race
from models.circuit import Circuit
from models.driver import Driver
from models.analytics import RaceEntry
from services.season_service import utcnow,parse_time,iso,race_start

class NewsImpactService:
    def extract(self,article_id):
        # Only a confirmed penalty in a race-specific headline is currently supported.
        # Opinion, upgrades, sentiment and LLM prose never become numerical evidence.
        with SessionLocal.begin() as s:
            a=s.get(NewsArticle,article_id)
            if s.query(NewsSignal).filter_by(article_id=article_id).first():return 0
            headline=a.source_title.lower()
            if re.search(r'\b(no|not|avoids?|avoid|could|may|might|rumou?r|potential|possible|risk|escapes?|overturned|appeal)\b',headline):return 0
            if not re.search(r'\b(?:engine|grid|place)\s+(?:\w+\s+){0,2}penalt(?:y|ies)\b',headline):return 0
            races=s.query(Race,Circuit).join(Circuit,Circuit.circuit_id==Race.circuit_id).filter(Race.is_completed==0,Race.race_status=='SCHEDULED').all()
            matches=[]
            for race,circuit in races:
                if not race.date or not parse_time(a.observed_at)<race_start(race)<=parse_time(a.observed_at)+timedelta(days=14):continue
                names=[race.race_name.lower().replace('grand prix','').strip(),(circuit.location or '').lower(),(circuit.country or '').lower()]
                if any(len(name)>=4 and re.search(r'\b'+re.escape(name)+r'\b',headline) for name in names):matches.append(race)
            if len(matches)!=1:return 0
            race=matches[0]
            # Prefer explicit entries; future grids otherwise use latest known season entrants.
            roster=s.query(Driver).join(RaceEntry,Driver.driver_id==RaceEntry.driver_id).join(Race,Race.race_id==RaceEntry.race_id).filter(Race.season_year==race.season_year).distinct().all()
            subjects=[d for d in roster if len(d.surname or '')>=3 and re.search(r'\b'+re.escape(d.surname.lower())+r'\b',headline)]
            if len(subjects)!=1:return 0
            s.add(NewsSignal(article_id=a.id,race_id=race.race_id,driver_id=subjects[0].driver_id,kind='confirmed_grid_penalty',log_weight=-.12,evidence=a.source_title,observed_at=a.observed_at,published_at=a.published_at,expires_at=iso(race_start(race))))
            return 1
    def apply(self,frame,probabilities):
        cutoff=parse_time(frame['feature_cutoff']);race_id=frame['race']['race_id']
        with SessionLocal() as s:
            records=s.query(NewsSignal,NewsArticle).join(NewsArticle,NewsArticle.id==NewsSignal.article_id).filter(NewsSignal.race_id==race_id).all()
        unique={}
        for signal,article in records:
            if not parse_time(signal.observed_at)<=cutoff or not parse_time(signal.published_at)<=cutoff or cutoff>=parse_time(signal.expires_at):continue
            key=(signal.driver_id,signal.constructor_id,signal.kind)
            if key not in unique or signal.observed_at>unique[key][0].observed_at:unique[key]=(signal,article)
        changes=[];used={};weights=[]
        for row,prob in zip(frame['rows'],probabilities):
            relevant=[(x,a) for x,a in unique.values() if (x.driver_id is not None and x.driver_id==row['driver_id']) or (x.constructor_id is not None and x.constructor_id==row['constructor_id'])]
            shift=max(-.12,min(.12,sum(x.log_weight for x,_ in relevant)))
            changes.append([{'id':x.id,'article_id':a.id,'kind':x.kind,'evidence':x.evidence,'source_url':a.source_url,'log_weight':x.log_weight} for x,a in relevant])
            used.update({x.id:a.id for x,a in relevant});weights.append(float(prob)*math.exp(shift))
        adjusted=np.asarray(weights)/sum(weights) if used else probabilities.copy()
        return adjusted,changes,{'news_factor_used':bool(used),'news_signal_ids':sorted(used),'news_cutoff':frame['feature_cutoff'],'news_note':'Experimental adjustment: confirmed grid penalties only; driver log-weight capped at ±0.12 then normalized. Not trained or backtested. Official standings are unchanged.'}
